# Deploy

Config files for the production server. Edit here, copy to system, reload.

## Services

| Service | Port | Config file |
|---|---|---|
| nginx | 80 / 443 | `nginx.conf` |
| gunicorn (Django API) | 8000 (internal) | `gunicorn.service` |
| Next.js frontend | 3000 (internal) | `next.service` |

## Routing

```
kazan.zabravih.org/static/*  → Django static files (direct)
kazan.zabravih.org/api/*     → gunicorn (Django) :8000
kazan.zabravih.org/admin/*   → gunicorn (Django) :8000
kazan.zabravih.org/*         → Next.js :3000
```

## Deploy commands

```bash
# nginx — after editing nginx.conf
sudo cp deploy/nginx.conf /etc/nginx/sites-available/zabravih
sudo nginx -t && sudo systemctl reload nginx

# gunicorn — after editing gunicorn.service or Django code
sudo cp deploy/gunicorn.service /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload && sudo systemctl restart gunicorn

# Next.js service — first time setup
sudo cp deploy/next.service /etc/systemd/system/next.service
sudo systemctl daemon-reload
sudo systemctl enable next
sudo systemctl start next

# Next.js — after frontend code changes
cd frontend && npm run build && sudo systemctl restart next
```

## Node.js

Installed via nvm. Node binary path used in next.service:
```
/home/main/.nvm/versions/node/v24.16.0/bin/node
```
If you upgrade Node, update the path in `next.service` and redeploy.

## Sync real bin data from Sofia API

```bash
cd py/garbageCollection

# Clear ALL fake data and import all ~43k real bins (takes ~2 min):
python manage.py sync_sofia_bins --clear

# Test with a single district first:
python manage.py sync_sofia_bins --district 1

# Re-sync (upsert, keeps fill history):
python manage.py sync_sofia_bins
```

## Django migrations

```bash
cd py/garbageCollection
source ../env/bin/activate
python manage.py migrate
```
