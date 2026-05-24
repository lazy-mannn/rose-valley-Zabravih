# Smart Kazan Collector — Session Handoff

> Generated 2026-05-24. Use this to resume work in a new session.

---

## Project overview

Django + Next.js web app for smart waste collection in Sofia. Tracks ~43,511 real
grey waste bins, visualises fill levels on a map, optimises truck routes, and
connects to Raspberry Pi cameras on trucks via API keys.

**Repo:** `/home/main/rose-valley-Zabravih/`
**Live:** `https://kazan.zabravih.org`

```
rose-valley-Zabravih/
├── deploy/               ← nginx, gunicorn, next.js systemd configs
├── frontend/             ← Next.js 16 (TypeScript, Tailwind v4, App Router)
│   └── app/
│       ├── components/   ← Map, MapWrapper, StatCard, DistrictList
│       ├── lib/          ← api.ts (fetch helpers + types)
│       ├── globals.css   ← Tailwind + Leaflet CSS + CSS variables
│       ├── layout.tsx    ← Root layout (Manrope font, dark bg)
│       └── page.tsx      ← Dashboard (server component)
├── py/
│   └── garbageCollection/
│       ├── garbageCollection/  ← Django project (settings, urls, wsgi)
│       └── garbageData/        ← Main app (models, views, urls, serializers, management)
├── rpi_code/             ← Raspberry Pi camera/NFC code
└── presentation/         ← Pitch materials
```

**Live domain:** `kazan.zabravih.org` (Cloudflare → nginx → gunicorn/Next.js)

---

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 16.2.6, React 19, TypeScript, Tailwind v4 | App Router, Manrope font |
| Map | Leaflet + react-leaflet | Dark tile: CARTO Dark Matter |
| Backend | Django 5.2, DRF 3.17, gunicorn | Pure API |
| Cache | Redis 8 (db 1) | django-redis, TTL 5min–1hr |
| Database | PostgreSQL (db: `main`) | localhost:5432 |
| Node | v24.16.0 via nvm | `/home/main/.nvm/versions/node/v24.16.0/` |
| Python env | virtualenv | `/home/main/rose-valley-Zabravih/py/env/` |
| Server | nginx (Cloudflare origin certs) | Config in `deploy/nginx.conf` |

---

## Sofia API — Key Facts

Base URL: `https://your.sofia.bg/api`
API type: PayloadCMS REST

| Endpoint | Notes |
|---|---|
| `GET /api/city-districts` | 24 districts, IDs 1–24 |
| `GET /api/waste-containers?where[district][equals]=N&limit=1000` | Grey bins by district |
| `GET /api/signals/count` | **Returns HTTP 500 — broken, skip** |

**Critical facts:**
- Total grey containers: **43,511** (42,654 in DB after deduplication)
- `location` field = **`[longitude, latitude]`** (GeoJSON order — swap when storing)
- All containers have `status: "pending"` — this is normal
- `district_id` on TrashCan is a plain `IntegerField` (1–24), **NOT a FK**

---

## What is complete

### ✅ Phase 1 — Model + sync
- `TrashCan` model with 8 Sofia API fields (migration 0007 applied)
- `sync_sofia_bins` management command — bulk upsert, pagination, retries
- DB has **42,654 real Sofia grey bins**
- Next.js scaffolded with Turbopack

### ✅ Phase 2 — DRF REST API
Files: `garbageData/serializers.py`, `garbageData/views.py`, `garbageData/urls.py`

| Endpoint | Purpose | Cache TTL |
|---|---|---|
| `GET /api/bins/clusters/?zoom=N&north=F&south=F&east=F&west=F` | Grid-bucket clusters by zoom | Redis 10min |
| `GET /api/bins/viewport/?north=F&south=F&east=F&west=F` | GeoJSON FeatureCollection, max 500 bins | Redis 5min |
| `GET /api/districts/` | 24 districts with bin/active/monitored counts | Redis 1hr |

Cache uses try/except — endpoints degrade gracefully without Redis.
All existing RPi endpoints (`/api/update/`, `/api/emptied/`, `/api/trashcan/`, `/api/trashcans/`) are unchanged.

### ✅ Phase 3 — Next.js Dashboard
**`/` — Dashboard page** (server component, fetches districts on server)
- Top bar with logo + "Pitch Deck →" link
- Stat strip: Total Bins, Active Bins, Monitored, Districts
- Left sidebar: searchable district list (260px)
- Right: full-height Leaflet map (CARTO Dark Matter tiles)

**Map behaviour:**
- Zoom < 15: fetches `/api/bins/clusters/` — renders circle markers sized by count
- Zoom ≥ 15: fetches `/api/bins/viewport/` — renders individual bin dots
- Click cluster → zoom in by 2
- Click bin → popup with fill level, status, district

**`/pitch/` — Pitch deck** (Django template, served by gunicorn)
- All-dark theme, single blue/sky accent, consistent 16px radius
- 7 slides: Problem, Solution, Market, Why Us, Finance, Ask, Closing

### ✅ Phase 4 — Cron + coloured bins command
Nightly cron jobs (in crontab):
```
0  3 * * *  sync_sofia_bins   → /var/log/sofia-sync.log   (updates grey bins)
30 3 * * *  sync_coloured_bins → /var/log/sofia-sync.log  (⚠ needs real URLs — see below)
```

`sync_coloured_bins` command exists at `garbageData/management/commands/sync_coloured_bins.py`
but the CKAN resource IDs in SOURCES are **placeholder guesses** — needs real URLs from
https://urbandata.sofia.bg/dataset/separate-collection before it will work.

---

## Grey bins sync logic

`sync_sofia_bins` does a **upsert** (create or update) keyed on Sofia bin ID:
- First run: use `--clear` flag to wipe 250 fake bins from initial setup
- Subsequent runs (including nightly cron): run without `--clear`
- Safe to run repeatedly — won't duplicate data
- Updates coordinates, status, district, lastCleaned if the bin already exists

---

## ⚠ Coloured bins — action needed

The `sync_coloured_bins` command needs **real resource IDs** from the Sofia open data portal.

1. Go to https://urbandata.sofia.bg/dataset/separate-collection
2. Find each dataset (blue/yellow recycling bins, green organic bins, etc.)
3. Click "Explore" → copy the CSV download URL or CKAN resource ID
4. Update the `SOURCES` list in `sync_coloured_bins.py`

Until this is done, the command will log "Failed — skipping" for every source.

---

## Services

```bash
# Check status
systemctl status gunicorn next nginx redis-server

# Restart all (use massiveRestart alias — builds Next.js too)
massiveRestart

# Manual service control (needs sudo)
sudo systemctl restart gunicorn
sudo systemctl restart next
sudo systemctl reload nginx
```

**Current process:** Next.js runs as a background `nohup npm start` process because
the systemd `next.service` was copied but never enabled/started. To make it
persistent across reboots:
```bash
sudo systemctl enable next
sudo systemctl start next
```
Then kill the background process and let the service take over.

---

## What still needs to be done

### Immediate
- [ ] Run `sudo systemctl enable next && sudo systemctl start next` to make Next.js
      persistent (currently running as background process PID ~40584)
- [ ] Get real coloured bins CSV URLs from urbandata.sofia.bg and update `sync_coloured_bins.py`

### Phase 4 remaining
- [ ] PostGIS (optional, for polygon queries): `sudo apt-get install postgresql-postgis`,
      then `CREATE EXTENSION postgis;` in psql, then swap lat/lon FloatFields for PointField
- [ ] Import coloured bins once `sync_coloured_bins.py` has real URLs

### Phase 5 (not started)
- Bin detail page: `/bin/[id]` in Next.js
- Fill history chart per bin
- Route visualisation on map (polylines from `/api/route/`)
- Heatmap overlay toggle

---

## Commands cheat sheet

```bash
# Activate virtualenv
source /home/main/rose-valley-Zabravih/py/env/bin/activate
cd /home/main/rose-valley-Zabravih/py/garbageCollection

# Run full data sync (updates/creates, safe to repeat)
python manage.py sync_sofia_bins

# First-time only (wipes 250 fake bins)
python manage.py sync_sofia_bins --clear

# Coloured bins (needs real URLs in SOURCES first)
python manage.py sync_coloured_bins --dry-run
python manage.py sync_coloured_bins

# Django check / runserver
python manage.py check
python manage.py runserver

# Next.js dev
cd /home/main/rose-valley-Zabravih/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
npm run dev    # http://localhost:3000

# Push to git
cd /home/main/rose-valley-Zabravih
git add <files> && git commit -m "message"
git push
```

---

## Known issues / gotchas

1. **`district_id` is NOT a FK** — use `filter(district_id=1)` not `filter(district=1)`
2. **All bins are `status: pending`** — Sofia hasn't activated them; filter by `bin_status`
3. **`/api/signals/count`** returns HTTP 500 — don't use it
4. **`lib/` in .gitignore** — root `.gitignore` has `lib/` which was catching `frontend/app/lib/`.
   Fixed with `!frontend/app/lib/` exception.
5. **`ssr: false` in Server Components** — not allowed in Next.js 16. Always wrap Leaflet
   (or any browser-only dynamic import) in a `"use client"` wrapper component.
6. **`font-weight: 900`** — Manrope via `next/font/google` only supports up to 800.
7. **CSRF** — DRF public GET endpoints use `AllowAny` with no auth. RPi endpoints
   use `X-API-Key` header auth.
8. **Cloudflare** — `real_ip_header CF-Connecting-IP` in nginx; don't change.
9. **gunicorn workers = 17** — tuned for this server; keep unless hardware changes.
