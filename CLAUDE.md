# Smart Kazan Collector

Django + Next.js smart waste collection platform for Sofia municipality.
Live at `kazan.zabravih.org`. ~42,662 real grey bins + 4,599 coloured bins.

## Stack

| Layer | Tech | Location |
|---|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind v4, App Router | `frontend/` |
| Map | Leaflet (CARTO Dark Matter tiles) | `frontend/app/components/Map.tsx` |
| Backend | Django 5.2, DRF 3.17, gunicorn | `py/garbageCollection/` |
| Cache | Redis (db 1), django-redis | localhost:6379 |
| Database | PostgreSQL (db: `main`) | localhost:5432 |
| Python env | virtualenv | `py/env/` |
| Node | v24.16.0 via nvm | `~/.nvm/versions/node/v24.16.0/` |
| Server | nginx + Cloudflare origin certs | configs in `deploy/` |

## Activate environments

```bash
# Python
source /home/main/rose-valley-Zabravih/py/env/bin/activate
cd /home/main/rose-valley-Zabravih/py/garbageCollection

# Node
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
cd /home/main/rose-valley-Zabravih/frontend
```

## Run dev servers

```bash
# Django
python manage.py runserver

# Next.js
npm run dev   # http://localhost:3000
```

## Key management commands

```bash
# Grey bins — normal nightly upsert (safe to repeat, won't duplicate):
python manage.py sync_sofia_bins

# Grey bins — first-time only (wipes all bins first):
python manage.py sync_sofia_bins --clear

# Test with one district:
python manage.py sync_sofia_bins --district 1

# Coloured bins — reads 3 CSVs from repo root (idempotent):
python manage.py sync_coloured_bins --dry-run
python manage.py sync_coloured_bins
python manage.py sync_coloured_bins --clear  # wipe coloured bins then reimport

# Refresh district boundary GeoJSON from OSM (only needed if district shapes change):
python scripts/fetch_sofia_districts.py

# Create API key for a truck RPi:
python manage.py create_api_key
```

## Git — always use gh

```bash
git add <files>
git commit -m "message"
git push
```

Commit style: short imperative subject line, no period.

## Deploy configs

All server configs live in `deploy/` — edit there, then copy to system:

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/zabravih && sudo nginx -t && sudo systemctl reload nginx
sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn.service && sudo systemctl daemon-reload && sudo systemctl restart gunicorn
sudo cp deploy/next.service /etc/systemd/system/next.service && sudo systemctl daemon-reload && sudo systemctl restart next
```

Use `massiveRestart` **function** (in `~/.bashrc`) to rebuild Next.js and restart all services at once. Run `source ~/.bashrc` first if you get "command not found" after opening a new terminal.

## Architecture rules

- **Django is API-only** — no new Django templates. All UI goes in `frontend/`.
- **Pitch page** (`templates/pitch.html`) is the only allowed Django template — it's static.
- **Never use Folium** for new features — map rendering is Leaflet in Next.js.
- **All Sofia API coordinates** are `[longitude, latitude]` (GeoJSON order) — always swap to `lat, lon` when storing.
- **district_id** on TrashCan is a plain `IntegerField` (1–24), not a FK. Use `filter(district_id=1)`.
- **`ssr: false` in dynamic()** must be inside a `"use client"` component, not a Server Component.
- **Manrope font** via `next/font/google` supports weights up to 800 (not 900).
- **`API_INTERNAL`** (`http://127.0.0.1:8000`) is for server-side fetches only. Client-side map components must use `API_BASE` (public URL). Wrong URL = browser permission prompt.
- **District boundaries** are stored as a static file at `frontend/public/sofia-districts.json` (real OSM polygons, fetched once by `scripts/fetch_sofia_districts.py`). Do not regenerate unless district shapes change.
- **scipy** is installed in the virtualenv (used for convex hull in `DistrictBoundariesView` — now mostly superseded by the static file).
- **Timestamps** — all datetimes stored in UTC, displayed in `Europe/Sofia` timezone using `Intl.DateTimeFormat`.

## Current phase

See `HANDOFF.md` for full detail. Short version:

- **Phase 1 DONE** — model + migration (0007), sync command, 42,662 grey bins in DB
- **Phase 2 DONE** — DRF endpoints: /api/bins/clusters/, /api/bins/viewport/, /api/districts/
- **Phase 3 DONE** — Next.js dashboard: stat cards + Leaflet map, cluster/viewport switching, dark design
- **Phase 4 DONE** — 4,599 coloured bins (paper/recycling/glass) from 3 CSV files; nightly cron
- **Phase 5 DONE** — Bin detail page, fill chart, grey bin fields in popup, district pan, map polish
- **Phase 6 TODO** — Route visualisation, heatmap overlay, truck assignment UI

## Sofia API

Base: `https://your.sofia.bg/api` (PayloadCMS REST)

- Grey bins: `GET /api/waste-containers?where[district][equals]=N&limit=1000`
- `/api/signals/count` returns HTTP 500 — **do not use**
- All bins currently `status: "pending"` — this is normal (Sofia API quirk)
- `capacityVolume` is stored as-is in m³ — 0.11 is a real value, not a typo

## Our API endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/districts/` | None | 24 districts with counts + center lat/lon |
| `GET /api/districts/boundaries/` | None | GeoJSON convex hulls (superseded by static file) |
| `GET /api/bins/clusters/` | None | One cluster per district at district centroid |
| `GET /api/bins/viewport/` | None | Individual bins in bbox (GeoJSON) |
| `GET /api/bins/<id>/` | None | Single bin detail + fill history |
| `GET /api/update/` | X-API-Key | RPi fill level update |
| `GET /api/emptied/` | X-API-Key | RPi mark emptied |
| `GET /api/trashcan/<id>/` | X-API-Key | Single bin status |
| `GET /api/trashcans/` | X-API-Key | All bins list |

## Cache keys

| Key | TTL | Notes |
|---|---|---|
| `bins:clusters:districts:v1` | 1 hr | District-level clusters |
| `bins:viewport:v3:{hash}` | 5 min | Individual bin viewport |
| `bins:districts:v4` | 1 hr | District list + totals |
| `bins:district_boundaries:v1` | 24 hr | Convex hull boundaries (fallback) |

To flush all bin caches: `cache.delete_pattern('bins:*')` in Django shell.

## Do not

- Do not run `python manage.py sync_sofia_bins --clear` unless first-time setup
- Do not commit `.env` files or secrets
- Do not use `sudo` without first telling the user what command to run
- Do not add new Django template views (frontend is Next.js)
- Do not use Mapbox (no token configured) — use Leaflet with CARTO tiles
- Do not call `API_INTERNAL` from client-side (browser) code — use `API_BASE` instead
