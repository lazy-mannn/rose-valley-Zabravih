"""
Fetch Sofia's 24 district boundaries from OpenStreetMap and save as GeoJSON.
Run once: python scripts/fetch_sofia_districts.py
Output: frontend/public/sofia-districts.json
"""
import json, urllib.request, urllib.parse, sys, os

DISTRICT_IDS = [
    (17759044, "Банкя"),
    (3759447,  "Витоша"),
    (3759448,  "Връбница"),
    (3759446,  "Възраждане"),
    (3759427,  "Искър"),
    (3759426,  "Илинден"),
    (3759428,  "Изгрев"),
    (3759429,  "Красна поляна"),
    (3759430,  "Красно село"),
    (3759431,  "Кремиковци"),
    (3759433,  "Лозенец"),
    (3759432,  "Люлин"),
    (3759434,  "Младост"),
    (3759435,  "Надежда"),
    (17758558, "Нови Искър"),
    (3759437,  "Оборище"),
    (3759438,  "Овча купел"),
    (3759439,  "Панчарево"),
    (3759440,  "Подуяне"),
    (3759441,  "Сердика"),
    (3759442,  "Слатина"),
    (3759443,  "Средец"),
    (3759444,  "Студентски"),
    (3759445,  "Триадица"),
]

ID_STR = ",".join(str(i) for i, _ in DISTRICT_IDS)

query = f"[out:json][timeout:80];rel(id:{ID_STR});out geom;"
data  = urllib.parse.urlencode({"data": query}).encode()
req   = urllib.request.Request(
    "https://overpass-api.de/api/interpreter",
    data=data,
    headers={
        "User-Agent": "SmartKazanCollector/1.0 (kazan.zabravih.org)",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)
print("Fetching from Overpass API…", flush=True)
with urllib.request.urlopen(req, timeout=90) as r:
    raw = json.load(r)

print(f"Got {len(raw['elements'])} relations", flush=True)


EPS = 1e-7  # coordinate snap tolerance

def close_enough(a, b):
    return abs(a[0] - b[0]) < EPS and abs(a[1] - b[1]) < EPS

def assemble_ring(ways):
    """Chain OSM ways (each a list of [lon, lat] coords) into one closed ring."""
    segments = [[[n["lon"], n["lat"]] for n in w["geometry"]] for w in ways if w.get("geometry")]
    if not segments:
        return []

    ring = list(segments[0])
    remaining = segments[1:]
    iters = 0
    max_iters = len(remaining) * 4 + 10

    while remaining and iters < max_iters:
        iters += 1
        last = ring[-1]
        matched = False
        for i, seg in enumerate(remaining):
            if close_enough(seg[0], last):
                ring.extend(seg[1:])
                remaining.pop(i)
                matched = True
                break
            if close_enough(seg[-1], last):
                ring.extend(reversed(seg[:-1]))
                remaining.pop(i)
                matched = True
                break
        if not matched:
            # Gap in ring — just append next segment and continue
            ring.extend(remaining.pop(0))

    if ring and not close_enough(ring[0], ring[-1]):
        ring.append(ring[0])

    return ring


features = []
name_lookup = {osm_id: name for osm_id, name in DISTRICT_IDS}

for rel in raw["elements"]:
    rid   = rel["id"]
    tags  = rel.get("tags", {})
    members = rel.get("members", [])

    outer_ways = [m for m in members if m.get("role") == "outer" and "geometry" in m]
    inner_ways = [m for m in members if m.get("role") == "inner" and "geometry" in m]

    outer_ring = assemble_ring(outer_ways)
    if len(outer_ring) < 4:
        print(f"  SKIP {rid}: outer ring too short ({len(outer_ring)} pts)", flush=True)
        continue

    coords = [outer_ring]
    if inner_ways:
        inner_ring = assemble_ring(inner_ways)
        if len(inner_ring) >= 4:
            coords.append(inner_ring)

    name    = tags.get("name") or name_lookup.get(rid, str(rid))
    name_en = tags.get("name:en") or tags.get("int_name") or name

    features.append({
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": coords},
        "properties": {"osm_id": rid, "name": name, "name_en": name_en},
    })
    print(f"  {name} — {len(outer_ring)} pts", flush=True)

out_path = os.path.join(os.path.dirname(__file__), "../frontend/public/sofia-districts.json")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": features}, f,
              ensure_ascii=False, separators=(",", ":"))

print(f"\nSaved {len(features)} districts → {os.path.abspath(out_path)}", flush=True)
