# Smart Kazan Collector — Session Handoff

> Generated 2026-05-24. Use this to resume work in a new session.

---

## Project overview

Django + Next.js web app for smart waste collection in Sofia. Tracks **42,662 grey bins**
+ **4,599 coloured separation bins**, visualises them on a Leaflet map with cluster/viewport
zoom switching, district overlays, and a bin detail page with fill history chart.

**Repo:** `/home/main/rose-valley-Zabravih/`
**Live:** `https://kazan.zabravih.org`

```
rose-valley-Zabravih/
├── deploy/                    ← nginx, gunicorn, next.js systemd configs
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── Map.tsx        ← Leaflet map (all rendering logic)
│   │   │   ├── DashboardClient.tsx ← "use client" wrapper; holds panTarget state
│   │   │   ├── DistrictList.tsx    ← sidebar district list
│   │   │   └── StatCard.tsx
│   │   ├── bin/[id]/
│   │   │   ├── page.tsx       ← Bin detail server component
│   │   │   └── FillChart.tsx  ← SVG fill history chart (client)
│   │   ├── lib/api.ts         ← fetch helpers + TypeScript interfaces
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx           ← Dashboard (server component)
│   └── public/
│       └── sofia-districts.json ← Real OSM district boundary polygons (static)
├── py/garbageCollection/
│   ├── garbageCollection/     ← Django project (settings, urls, wsgi)
│   └── garbageData/
│       ├── models.py          ← TrashCan, FillRecord, APIKey
│       ├── views.py           ← All DRF views
│       ├── urls.py
│       └── management/commands/
│           ├── sync_sofia_bins.py     ← Grey bin upsert from Sofia API
│           └── sync_coloured_bins.py  ← Coloured bin import from 3 CSVs
├── scripts/
│   └── fetch_sofia_districts.py ← Fetch OSM district polygons → public/sofia-districts.json
├── bulecopack_colored-bins.xlsx.csv   ← CSV source files (keep at repo root)
├── ecobulpack_colored-bins.xlsx.csv
└── ecopack_colored-bins.xlsx.csv
```

---

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 16.2.6, React 19, TypeScript, Tailwind v4 | App Router, Manrope font |
| Map | Leaflet (no react-leaflet) | CARTO Dark Matter tiles |
| Backend | Django 5.2, DRF 3.17, gunicorn | Pure API + pitch template |
| Cache | Redis 8 (db 1) | django-redis |
| Database | PostgreSQL (db: `main`) | localhost:5432 |
| Python env | virtualenv | `py/env/` — scipy installed |
| Server | nginx + Cloudflare origin certs | `deploy/nginx.conf` |

---

## Phases — all done through Phase 5

### ✅ Phase 1 — Model + sync
- `TrashCan` model (migrations 0001–0009 all applied)
- `sync_sofia_bins` — bulk upsert from Sofia API, nightly cron at 3 AM
- 42,662 grey bins in DB

### ✅ Phase 2 — DRF API
All endpoints in `garbageData/views.py` and `urls.py`:

| Endpoint | Cache key | TTL |
|---|---|---|
| `GET /api/bins/clusters/` | `bins:clusters:districts:v1` | 1 hr |
| `GET /api/bins/viewport/` | `bins:viewport:v3:{hash}` | 5 min |
| `GET /api/bins/<id>/` | none | — |
| `GET /api/districts/` | `bins:districts:v4` | 1 hr |
| `GET /api/districts/boundaries/` | `bins:district_boundaries:v1` | 24 hr |

### ✅ Phase 3 — Next.js Dashboard
- Server component `page.tsx` fetches districts + totals, renders stat strip + `<DashboardClient>`
- `DashboardClient.tsx` (`"use client"`) holds `panTarget` state; clicking a district pans the map
- `Map.tsx` — all Leaflet logic, no SSR, loaded via `dynamic(..., { ssr: false })`

### ✅ Phase 4 — Coloured bins
- **4,599 coloured bins** in DB (paper: 669, recycling: 2,015, glass: 1,915)
- Source: 3 CSV files at repo root — bulecopack, ecobulpack, ecopack
- Stable hash IDs in 100M–999M range (never collide with grey bin IDs < 100K)
- `sync_coloured_bins --clear` wipes and reimports; `--dry-run` to preview
- Nightly cron at 3:30 AM (idempotent)

### ✅ Phase 5 — Map polish + bin detail
- **Bin detail page** `/bin/[id]` — address, district, capacity, last cleaned, fill history
- **FillChart** — pure SVG, no charting library
- **Map rendering:**
  - Zoom < 13: district-level clusters (one trash can icon per district at centroid, 16px)
  - Zoom 13–15: individual bins as circle/compound dot markers
  - Zoom ≥ 16: grey bins with bin_count > 1 expand to N dots (max 6 + overflow label)
  - Coloured bins grouped by exact coordinate (co-located bins → compound pill of coloured dots)
  - Grey bin bin_count > 1 at zoom < 16 → single dot; at zoom ≥ 16 → expanded dots
- **District boundaries** — real OSM polygon outlines loaded from `/sofia-districts.json`
  (non-interactive, faint blue fill + 2px border, pure background)
- **Colours:**
  - Paper: `#818CF8` (blue-purple)
  - Recycling: `#FBBF24` (yellow)
  - Glass: `#34D399` (green)
  - Grey with fill: green→yellow→orange→red by fill %
- **Atomic marker swap** — old markers stay visible during fetch, replaced only when new data arrives
- **Request deduplication** — `requestId` counter discards stale responses on rapid pan/zoom
- **Timestamps** displayed in `Europe/Sofia` timezone via `Intl.DateTimeFormat`

---

## TrashCan model fields

```python
id              IntegerField   # Sofia API ID for grey; hash-based for coloured
latitude        FloatField
longitude       FloatField
public_number   CharField(120) # Street address
district_id     IntegerField   # 1–24, plain integer NOT a FK
district_name   CharField
waste_type      CharField      # 'general' | 'paper' | 'recycling' | 'glass'
bin_status      CharField      # 'pending' (grey) | 'active' (coloured)
capacity_volume FloatField     # m³ (e.g. 1.1 m³ = 1100 L). 0.11 is a real value.
bin_count       IntegerField   # physical bins at this location
last_cleaned    DateTimeField  # from Sofia API (UTC)
container_type  CharField(20)  # 'iglu' | 'bobar' | '' (grey bins)
```

Migrations applied: 0001–0009 (0009 adds `container_type`).

---

## Map zoom behaviour

| Zoom | Mode | What's shown |
|---|---|---|
| < 13 | Clusters | 24 district trash-can icons at district centroids |
| 13–15 | Viewport | Individual bin markers (single dot or compound pill) |
| ≥ 16 | Viewport (expanded) | Grey multi-bin locations expand from 1 dot to N dots |

`VIEWPORT_ZOOM = 13`, `EXPAND_ZOOM = 16` in `Map.tsx`.

---

## District boundaries — static file

`frontend/public/sofia-districts.json` — GeoJSON FeatureCollection of all 24 Sofia districts.
Fetched from OpenStreetMap Overpass API by `scripts/fetch_sofia_districts.py`.

**OSM relation IDs** (if you need to re-fetch):
```
Банкя=17759044, Витоша=3759447, Връбница=3759448, Възраждане=3759446
Искър=3759427, Илинден=3759426, Изгрев=3759428, Красна поляна=3759429
Красно село=3759430, Кремиковци=3759431, Лозенец=3759433, Люлин=3759432
Младост=3759434, Надежда=3759435, Нови Искър=17758558, Оборище=3759437
Овча купел=3759438, Панчарево=3759439, Подуяне=3759440, Сердика=3759441
Слатина=3759442, Средец=3759443, Студентски=3759444, Триадица=3759445
```

Only re-run the script if OSM district boundaries change (rare).

---

## Cron jobs

```
0  2 * * *  update_predictions   → /var/log/garbage_predictions.log
0  2 * * 0  cleanup_old_records --days 90
0  3 * * *  sync_sofia_bins      → /var/log/sofia-sync.log
30 3 * * *  sync_coloured_bins   → /var/log/sofia-sync.log
```

---

## Services

```bash
systemctl status gunicorn next nginx redis-server

# Rebuild Next.js + restart all (requires sudo, needs source ~/.bashrc first):
massiveRestart
```

---

## What still needs to be done

### Phase 6 (not started)
- [ ] Route visualisation on map (polylines from `/api/route/`)
- [ ] Heatmap overlay toggle
- [ ] Truck assignment / district-company mapping UI
- [ ] Fill rate prediction display

### Known gaps
- `last_emptied` (our RPi field) is never set for grey bins — only meaningful for future monitored bins
- `/api/districts/boundaries/` endpoint (convex hull) still exists but is superseded by the static file
- Sofia API `status: "pending"` for all grey bins is a Sofia API quirk, not a bug

---

## Commands cheat sheet

```bash
# Activate Python env
source /home/main/rose-valley-Zabravih/py/env/bin/activate
cd /home/main/rose-valley-Zabravih/py/garbageCollection

# Sync data
python manage.py sync_sofia_bins                    # nightly upsert
python manage.py sync_coloured_bins --clear         # wipe + reimport coloured

# Flush Redis caches
python manage.py shell -c "from django.core.cache import cache; cache.delete_pattern('bins:*')"

# Re-fetch district boundaries from OSM
python /home/main/rose-valley-Zabravih/scripts/fetch_sofia_districts.py

# Next.js dev
cd /home/main/rose-valley-Zabravih/frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
npm run dev

# Deploy
massiveRestart   # (must source ~/.bashrc first in a new terminal)
```

---

## Known issues / gotchas

1. **`district_id` is NOT a FK** — use `filter(district_id=1)` not `filter(district=1)`
2. **All grey bins are `status: "pending"`** — Sofia API quirk, not a bug
3. **`/api/signals/count`** returns HTTP 500 — don't use it
4. **`capacity_volume = 0.11`** — real value from Sofia API, not a data error
5. **`API_INTERNAL` is server-only** — never call it from client-side code (causes browser permission prompt). Use `API_BASE` in Map.tsx and any client component.
6. **`massiveRestart` needs `source ~/.bashrc`** in a fresh terminal before it's available
7. **`ssr: false` in `dynamic()`** must be inside a `"use client"` component
8. **Manrope font** max weight 800 (not 900)
9. **Coloured bin IDs** in 100M–999M range; grey bin IDs are small integers from Sofia API
10. **`SECURE_SSL_REDIRECT = False`** — nginx handles SSL, gunicorn is HTTP-only; do not change
11. **Cache key versions** — bump suffix when API response schema changes: `bins:viewport:v3`, `bins:districts:v4`
