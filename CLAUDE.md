# Smart Kazan Collector

Django + Next.js smart waste collection platform for Sofia municipality.
Live at `kazan.zabravih.org`. ~43,511 real grey bins, 76 trucks, 9 companies.

## Stack

| Layer | Tech | Location |
|---|---|---|
| Frontend | Next.js 16, TypeScript, Tailwind v4, App Router | `frontend/` |
| Map | Leaflet + react-leaflet (CARTO Dark Matter tiles) | `frontend/app/components/Map.tsx` |
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
# First-time grey bins import (clears 250 fake bins, loads all 43k real ones):
python manage.py sync_sofia_bins --clear

# Normal nightly update (safe to repeat — upserts, won't duplicate):
python manage.py sync_sofia_bins

# Test with one district:
python manage.py sync_sofia_bins --district 1

# Coloured bins (⚠ update SOURCES in the command with real URLs first):
python manage.py sync_coloured_bins --dry-run

# Create API key for a truck RPi:
python manage.py create_api_key
```

## Git — always use gh

Use `gh` for all git operations. Never use raw `git push` or create PRs manually.

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

Use `massiveRestart` alias to rebuild Next.js and restart all services at once.

## Architecture rules

- **Django is API-only** — no new Django templates. All UI goes in `frontend/`.
- **Pitch page** (`templates/pitch.html`) is the only allowed Django template — it's static.
- **Never use Folium** for new features — map rendering is Leaflet in Next.js.
- **All Sofia API coordinates** are `[longitude, latitude]` (GeoJSON order) — always swap to `lat, lon` when storing.
- **district_id** on TrashCan is a plain `IntegerField` (1–24), not a FK. Use `filter(district_id=1)`.
- **`ssr: false` in dynamic()** must be inside a `"use client"` component, not a Server Component.
- **Manrope font** via `next/font/google` supports weights up to 800 (not 900).

## Current phase

See `HANDOFF.md` for full detail. Short version:

- **Phase 1 DONE** — model + migration (0007), sync command, 42,654 bins in DB
- **Phase 2 DONE** — DRF endpoints: /api/bins/clusters/, /api/bins/viewport/, /api/districts/
- **Phase 3 DONE** — Next.js dashboard: stat cards + Leaflet map with cluster/viewport switching
- **Phase 4 DONE** — Nightly cron set up; sync_coloured_bins command exists (⚠ needs real URLs)
- **Next:** Enable next.service permanently + get coloured bin URLs from urbandata.sofia.bg

## Sofia API

Base: `https://your.sofia.bg/api` (PayloadCMS REST)

- Districts: IDs 1–24
- Grey bins: `GET /api/waste-containers?where[district][equals]=N&limit=1000`
- `/api/signals/count` returns HTTP 500 — **do not use**
- All bins currently `status: "pending"` — this is normal

## Our API endpoints

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/districts/` | None | 24 districts with counts |
| `GET /api/bins/clusters/` | None | Zoom+bbox clusters |
| `GET /api/bins/viewport/` | None | Individual bins in bbox |
| `GET /api/update/` | X-API-Key | RPi fill level update |
| `GET /api/emptied/` | X-API-Key | RPi mark emptied |
| `GET /api/trashcan/<id>/` | X-API-Key | Single bin status |
| `GET /api/trashcans/` | X-API-Key | All bins list |

## Do not

- Do not run `python manage.py sync_sofia_bins --clear` unless first-time setup
- Do not commit `.env` files or secrets
- Do not use `sudo` without first telling the user what command to run
- Do not add new Django template views (frontend is Next.js)
- Do not use Mapbox (no token configured) — use Leaflet with CARTO tiles
