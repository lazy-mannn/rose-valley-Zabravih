"""
Import coloured (paper/recycling/glass) bins from three static CSV files.

Waste types:
  paper     — blue bins  (sin / iglu_sinyo)
  recycling — yellow bins (zhalt / iglu_zhalto / bobar_zhalt)
  glass     — green bins  (zelen / iglu_zeleno)

CSV files are read from <repo-root>/ by default (or --data-dir):
  bulecopack_colored-bins.xlsx.csv
  ecobulpack_colored-bins.xlsx.csv
  ecopack_colored-bins.xlsx.csv

Usage:
    python manage.py sync_coloured_bins              # import (idempotent)
    python manage.py sync_coloured_bins --dry-run    # count only, no writes
    python manage.py sync_coloured_bins --clear      # wipe coloured bins first
    python manage.py sync_coloured_bins --data-dir /path/to/csvs
"""

import csv
import hashlib
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from garbageData.models import TrashCan

_CMD_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(_CMD_DIR, *(['..'] * 5)))

SOFIA_LAT = (42.4, 43.0)
SOFIA_LON = (22.9, 23.9)


def _stable_id(company: str, lat: float, lon: float,
               waste_type: str, container_type: str, capacity_l: int) -> int:
    """Deterministic integer PK — never collides with Sofia grey bin IDs (< 100 K)."""
    key = f"{company}:{lat:.6f}:{lon:.6f}:{waste_type}:{container_type}:{capacity_l}".encode()
    raw = int.from_bytes(hashlib.md5(key).digest()[:4], "big")
    return raw % 900_000_000 + 100_000_000


def _coord(value: str) -> float | None:
    if not value:
        return None
    try:
        f = float(str(value).replace(",", ".").strip())
        return f if f != 0.0 else None
    except ValueError:
        return None


def _in_sofia(lat: float, lon: float) -> bool:
    return SOFIA_LAT[0] <= lat <= SOFIA_LAT[1] and SOFIA_LON[0] <= lon <= SOFIA_LON[1]


class Command(BaseCommand):
    help = "Import coloured separation bins from local CSV files (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--clear",   action="store_true")
        parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, metavar="DIR")

    def handle(self, *args, **options):
        dry_run  = options["dry_run"]
        data_dir = options["data_dir"]
        self.stdout.write(f"Reading CSVs from: {data_dir}\n")

        if options["clear"] and not dry_run:
            deleted, _ = TrashCan.objects.exclude(waste_type="general").delete()
            self.stdout.write(f"Cleared {deleted} coloured bins\n")

        bins: list[TrashCan] = []
        bins += self._parse_bulecopack(data_dir)
        bins += self._parse_ecobulpack(data_dir)
        bins += self._parse_ecopack(data_dir)

        self.stdout.write(f"\nTotal to import: {len(bins)} bins")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run — nothing written"))
            return

        bins_by_id: dict[int, TrashCan] = {b.id: b for b in bins}
        dupes = len(bins) - len(bins_by_id)
        if dupes:
            self.stdout.write(self.style.WARNING(f"  Dropped {dupes} duplicate entries"))
        unique_bins = list(bins_by_id.values())

        with transaction.atomic():
            TrashCan.objects.bulk_create(
                unique_bins,
                update_conflicts=True,
                unique_fields=["id"],
                update_fields=[
                    "public_number", "district_name", "bin_count",
                    "waste_type", "bin_status", "latitude", "longitude",
                    "container_type", "capacity_volume",
                ],
            )

        self.stdout.write(self.style.SUCCESS(
            f"Done — {len(unique_bins)} bins upserted"
        ))

    # ── bulecopack ────────────────────────────────────────────────────────────
    def _parse_bulecopack(self, data_dir: str) -> list[TrashCan]:
        """
        Each location has exactly 2 bins:
          Yellow (recycling) — iglu, 1700 L
          Green  (glass)     — iglu, 1400 L
        """
        path = os.path.join(data_dir, "bulecopack_colored-bins.xlsx.csv")
        bins: list[TrashCan] = []
        skipped = 0

        try:
            with open(path, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    lat = _coord(row.get("lat", ""))
                    lon = _coord(row.get("long", ""))
                    if lat is None or lon is None or not _in_sofia(lat, lon):
                        skipped += 1
                        continue
                    district = (row.get("rajon") or "").strip()
                    address  = (row.get("adres")  or "").strip()[:120]

                    for waste_type, capacity_l in (("recycling", 1700), ("glass", 1400)):
                        bins.append(TrashCan(
                            id=_stable_id("bulecopack", lat, lon, waste_type, "iglu", capacity_l),
                            latitude=lat, longitude=lon,
                            waste_type=waste_type, bin_status="active",
                            container_type="iglu", capacity_volume=capacity_l / 1000,
                            bin_count=1, district_name=district, public_number=address,
                        ))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(f"  bulecopack: not found at {path}"))
            return bins

        self.stdout.write(
            f"  bulecopack : {len(bins) // 2} locations → {len(bins)} bins  ({skipped} skipped)"
        )
        return bins

    # ── ecobulpack ────────────────────────────────────────────────────────────
    def _parse_ecobulpack(self, data_dir: str) -> list[TrashCan]:
        """
        One DB row per (location, container_type, waste_type, capacity).
        Cell value = physical count of that container at the location.
        """
        path = os.path.join(data_dir, "ecobulpack_colored-bins.xlsx.csv")
        bins: list[TrashCan] = []
        skipped = 0

        # (csv_column, container_type, waste_type, capacity_litres)
        COLUMNS = [
            ("iglu_zhalto_1700l",       "iglu",  "recycling", 1700),
            ("iglu_zeleno_1400l",       "iglu",  "glass",     1400),
            ("bobar_zhalt_1100l",       "bobar", "recycling", 1100),
            ("iglu_zhalto_1100l",       "iglu",  "recycling", 1100),
            ("iglu_sinyo_1100l",        "iglu",  "paper",     1100),
            ("iglu_zeleno_1100l",       "iglu",  "glass",     1100),
            ("iglu_zhalto_siti_1800l",  "iglu",  "recycling", 1800),
        ]

        try:
            with open(path, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    lat = _coord(row.get("latitude", ""))
                    lon = _coord(row.get("longitude", ""))
                    if lat is None or lon is None or not _in_sofia(lat, lon):
                        skipped += 1
                        continue
                    address = (row.get("adres") or "").strip()[:120]

                    for col, ct, wt, cap in COLUMNS:
                        try:
                            count = int(str(row.get(col, "") or "0").strip())
                        except ValueError:
                            count = 0
                        if count > 0:
                            bins.append(TrashCan(
                                id=_stable_id("ecobulpack", lat, lon, wt, ct, cap),
                                latitude=lat, longitude=lon,
                                waste_type=wt, bin_status="active",
                                container_type=ct, capacity_volume=cap / 1000,
                                bin_count=count, public_number=address,
                            ))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(f"  ecobulpack: not found at {path}"))
            return bins

        self.stdout.write(f"  ecobulpack : {len(bins)} bins  ({skipped} skipped)")
        return bins

    # ── ecopack ───────────────────────────────────────────────────────────────
    def _parse_ecopack(self, data_dir: str) -> list[TrashCan]:
        """
        sin  (blue)   → paper     — iglu, 1100 L
        zhalt (yellow)→ recycling — iglu, 1100 L
        zelen (green) → glass     — iglu, 1100 L
        Value "1" = bin is present at this location.
        """
        path = os.path.join(data_dir, "ecopack_colored-bins.xlsx.csv")
        bins: list[TrashCan] = []
        skipped = 0

        TYPE_MAP = [
            ("sin",   "paper",     "iglu", 1100),
            ("zhalt", "recycling", "iglu", 1100),
            ("zelen", "glass",     "iglu", 1100),
        ]

        try:
            with open(path, encoding="utf-8-sig") as fh:
                for row in csv.DictReader(fh):
                    lat = _coord(row.get("lat", ""))
                    lon = _coord(row.get("long", ""))
                    if lat is None or lon is None or not _in_sofia(lat, lon):
                        skipped += 1
                        continue
                    district = (row.get("rajon") or "").strip()
                    address  = (row.get("adres")  or "").strip()[:120]

                    for col, wt, ct, cap in TYPE_MAP:
                        if str(row.get(col, "") or "").strip() == "1":
                            bins.append(TrashCan(
                                id=_stable_id("ecopack", lat, lon, wt, ct, cap),
                                latitude=lat, longitude=lon,
                                waste_type=wt, bin_status="active",
                                container_type=ct, capacity_volume=cap / 1000,
                                bin_count=1, district_name=district, public_number=address,
                            ))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(f"  ecopack: not found at {path}"))
            return bins

        self.stdout.write(f"  ecopack    : {len(bins)} bins  ({skipped} skipped)")
        return bins
