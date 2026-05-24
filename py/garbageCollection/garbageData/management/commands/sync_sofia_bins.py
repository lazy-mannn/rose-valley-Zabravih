"""
Sync grey waste containers from the Sofia city API into the local database.

Usage:
  # Full sync (upsert, keeps fill history):
  python manage.py sync_sofia_bins

  # Clear ALL bins + fill records first, then import fresh:
  python manage.py sync_sofia_bins --clear

  # Sync a single district for testing (district IDs 1–24):
  python manage.py sync_sofia_bins --district 3

API notes:
  - Base URL: https://your.sofia.bg/api
  - Pagination: PayloadCMS REST — uses ?limit=N&page=N
  - location field is [longitude, latitude] (GeoJSON order)
  - All containers currently have status="pending" (auto-imported from GPS)
  - District IDs 1–24 match Sofia municipal districts
"""

import time
from datetime import datetime, timezone as dt_timezone

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from garbageData.models import FillRecord, TrashCan

BASE_URL   = 'https://your.sofia.bg/api'
PAGE_LIMIT = 1000          # request 1000 per page; adjust if the API caps it
TIMEOUT    = 30            # seconds per HTTP request
RETRY_MAX  = 3             # retries on transient failures
RETRY_WAIT = 2             # seconds between retries


def _parse_dt(value):
    """Return a timezone-aware datetime from an ISO-8601 string, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def _get(url, retries=RETRY_MAX):
    """GET with retries and a short back-off."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if attempt == retries:
                raise
            time.sleep(RETRY_WAIT * attempt)


class Command(BaseCommand):
    help = 'Sync grey waste-container locations from the Sofia city API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing bins and fill records before syncing',
        )
        parser.add_argument(
            '--district',
            type=int,
            metavar='N',
            help='Sync only district N (1–24) — useful for testing',
        )

    # ──────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing bins and fill records …')
            with transaction.atomic():
                FillRecord.objects.all().delete()
                TrashCan.objects.all().delete()
            self.stdout.write(self.style.WARNING('  All bins cleared.'))

        districts = [options['district']] if options['district'] else range(1, 25)

        total_created = total_updated = total_skipped = 0

        for district_id in districts:
            try:
                created, updated, skipped = self._sync_district(district_id)
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(f'District {district_id}: FAILED — {exc}')
                )
                continue

            total_created  += created
            total_updated  += updated
            total_skipped  += skipped
            self.stdout.write(
                f'  District {district_id:>2}: '
                f'+{created} created  ~{updated} updated  -{skipped} skipped'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\nDone — {total_created} created, {total_updated} updated, '
            f'{total_skipped} skipped (bad location).'
        ))

    # ──────────────────────────────────────────────────────────────────────
    def _sync_district(self, district_id):
        created = updated = skipped = 0
        page = 1

        while True:
            url = (
                f'{BASE_URL}/waste-containers'
                f'?where[district][equals]={district_id}'
                f'&limit={PAGE_LIMIT}'
                f'&page={page}'
            )

            data = _get(url)
            docs = data.get('docs', [])

            if not docs:
                break

            batch_created, batch_updated, batch_skipped = self._upsert_batch(docs)
            created += batch_created
            updated += batch_updated
            skipped += batch_skipped

            if not data.get('hasNextPage'):
                break
            page += 1

        return created, updated, skipped

    # ──────────────────────────────────────────────────────────────────────
    def _upsert_batch(self, docs):
        bins_to_process = []

        for doc in docs:
            loc = doc.get('location') or []
            if len(loc) < 2:
                # No valid coordinates — skip
                continue

            # Sofia API location = [longitude, latitude] (GeoJSON order)
            lon, lat = float(loc[0]), float(loc[1])

            # Sanity-check: Sofia bounding box roughly 42.4–42.9 N, 23.1–23.9 E
            if not (42.0 <= lat <= 43.5 and 22.5 <= lon <= 24.5):
                continue

            district_obj = doc.get('district') or {}

            bins_to_process.append({
                'id':               doc['id'],
                'latitude':         lat,
                'longitude':        lon,
                'public_number':    doc.get('publicNumber') or '',
                'district_id':      district_obj.get('id'),
                'district_name':    district_obj.get('name') or '',
                'waste_type':       doc.get('wasteType') or 'general',
                'bin_status':       doc.get('status') or 'pending',
                'capacity_volume':  doc.get('capacityVolume'),
                'bin_count':        doc.get('binCount') or 1,
                'last_cleaned':     _parse_dt(doc.get('lastCleaned')),
            })

        if not bins_to_process:
            return 0, 0, len(docs)

        ids = [b['id'] for b in bins_to_process]
        existing_ids = set(
            TrashCan.objects.filter(id__in=ids).values_list('id', flat=True)
        )

        new_objs      = []
        update_objs   = []
        update_fields = [
            'latitude', 'longitude', 'public_number', 'district_id',
            'district_name', 'waste_type', 'bin_status', 'capacity_volume',
            'bin_count', 'last_cleaned',
        ]

        for b in bins_to_process:
            bin_id = b.pop('id')
            if bin_id in existing_ids:
                obj = TrashCan(id=bin_id, **b)
                update_objs.append(obj)
            else:
                obj = TrashCan(id=bin_id, **b)
                new_objs.append(obj)

        with transaction.atomic():
            if new_objs:
                TrashCan.objects.bulk_create(new_objs, ignore_conflicts=True)
            if update_objs:
                TrashCan.objects.bulk_update(update_objs, update_fields)

        skipped = len(docs) - len(bins_to_process)
        return len(new_objs), len(update_objs), skipped
