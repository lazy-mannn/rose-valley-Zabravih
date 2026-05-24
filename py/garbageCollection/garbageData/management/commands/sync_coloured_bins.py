"""
Import coloured (recycling/organic/glass/paper) bins from the Sofia open-data
CSV files published at https://urbandata.sofia.bg/dataset/separate-collection

Usage:
    python manage.py sync_coloured_bins              # fetch all CSVs
    python manage.py sync_coloured_bins --dry-run    # print counts only
"""

import csv
import io
import re
import urllib.request
from django.core.management.base import BaseCommand
from django.db import transaction
from garbageData.models import TrashCan

# CSV download URLs from Sofia open data portal.
# Each row has columns: latitude, longitude, type (plus optional extras).
SOURCES = [
    {
        "url": "https://urbandata.sofia.bg/api/3/action/datastore_search?resource_id=a4c83b78-1a19-4a77-b091-fa8b6765d6bf&limit=50000",
        "waste_type": "recycling",
        "label": "Recycling (blue/yellow bins)",
    },
    {
        "url": "https://urbandata.sofia.bg/api/3/action/datastore_search?resource_id=b6f2b94a-5b2a-4177-9e64-2f5e6e876543&limit=50000",
        "waste_type": "organic",
        "label": "Organic (green bins)",
    },
]

# Fallback: direct CSV export links (try if the datastore API is unavailable)
CSV_FALLBACK = [
    {
        "url": "https://urbandata.sofia.bg/dataset/separate-collection/resource/blue-bins.csv",
        "waste_type": "recycling",
        "label": "Recycling CSV fallback",
    },
]

LAT_ALIASES  = {"latitude", "lat", "y", "geog_lat"}
LON_ALIASES  = {"longitude", "lon", "lng", "x", "geog_lon"}
TYPE_ALIASES = {"type", "tip", "kind", "waste_type"}


def _find_col(header: list[str], aliases: set[str]) -> int | None:
    for i, h in enumerate(header):
        if h.strip().lower() in aliases:
            return i
    return None


def _fetch_csv(url: str) -> list[dict]:
    """Download URL and parse as CSV. Handles both direct CSV and CKAN JSON."""
    req = urllib.request.Request(url, headers={"User-Agent": "SmartKazanBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig", errors="replace")

    # CKAN datastore_search returns JSON — extract the records
    if url.startswith("https://urbandata.sofia.bg/api/"):
        import json
        data = json.loads(raw)
        if not data.get("success"):
            return []
        return data["result"]["records"]

    # Plain CSV
    reader = csv.DictReader(io.StringIO(raw))
    return list(reader)


class Command(BaseCommand):
    help = "Import coloured separation bins from Sofia open-data portal"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Count rows only; do not write to DB")
        parser.add_argument("--clear", action="store_true", help="Delete existing non-general bins first")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        do_clear = options["clear"]

        if do_clear and not dry_run:
            deleted, _ = TrashCan.objects.exclude(waste_type="general").delete()
            self.stdout.write(f"Cleared {deleted} non-general bins")

        total_created = total_skipped = 0

        for source in SOURCES:
            self.stdout.write(f"\n→ {source['label']}")
            try:
                rows = _fetch_csv(source["url"])
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  Failed ({exc}) — skipping"))
                continue

            if not rows:
                self.stdout.write("  No rows returned")
                continue

            # Normalise: rows can be dicts (CSV) or dicts (CKAN JSON)
            created = skipped = 0
            to_create: list[TrashCan] = []

            for row in rows:
                # Handle both plain-dict (CSV) and CKAN record (has _id)
                lat_raw = row.get("latitude") or row.get("lat") or row.get("y") or row.get("geog_lat")
                lon_raw = row.get("longitude") or row.get("lon") or row.get("x") or row.get("geog_lon")

                if not lat_raw or not lon_raw:
                    skipped += 1
                    continue

                try:
                    lat = float(str(lat_raw).replace(",", "."))
                    lon = float(str(lon_raw).replace(",", "."))
                except ValueError:
                    skipped += 1
                    continue

                # Basic sanity for Sofia bounding box
                if not (42.5 <= lat <= 43.0 and 23.0 <= lon <= 23.7):
                    skipped += 1
                    continue

                if not dry_run:
                    to_create.append(TrashCan(
                        latitude=lat,
                        longitude=lon,
                        waste_type=source["waste_type"],
                        bin_status="active",
                        bin_count=1,
                        district_id=None,
                    ))
                created += 1

            if not dry_run and to_create:
                with transaction.atomic():
                    TrashCan.objects.bulk_create(to_create, ignore_conflicts=True)

            self.stdout.write(f"  created={created}  skipped={skipped}")
            total_created += created
            total_skipped += skipped

        action = "Would create" if dry_run else "Created"
        self.stdout.write(self.style.SUCCESS(
            f"\n{action} {total_created} coloured bins  ({total_skipped} skipped)"
        ))
