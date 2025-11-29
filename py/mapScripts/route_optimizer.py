{"id":"32477","variant":"standard","title":"Trash Route Map with Truck Capacity Added"}
import folium
from folium.plugins import MarkerCluster
import random
import openrouteservice
from itertools import islice
import math
from decouple import config


# --- CONFIG ---
NUM_BINS = 200
CITY_CENTER = (42.6181, 25.3954)
FULL_THRESHOLD = 80
ORS_API_KEY = config('API_KEY')
START_POINT = {'lat': 42.6181, 'lon': 25.3954, 'name': 'Depot'}

TRUCK_CAPACITY = 10          # <-- NEW: max bins per truck load
CHUNK_SIZE = 40              # ORS max waypoints per request
ROUTE_COLORS = ['red', 'blue', 'green', 'purple', 'orange', 'brown', 'pink', 'cyan', 'magenta']

# --- ORS CLIENT ---
client = openrouteservice.Client(key=ORS_API_KEY)

# --- SIMULATE TRASH BINS ---
trash_bins = []
for i in range(NUM_BINS):
    percent_full = random.randint(10, 100)
    if percent_full >= FULL_THRESHOLD:
        lat = CITY_CENTER[0] + random.uniform(-0.01, 0.01)
        lon = CITY_CENTER[1] + random.uniform(-0.01, 0.01)
        trash_bins.append({'id': i, 'lat': lat, 'lon': lon, 'percent_full': percent_full})


# --- DISTANCE FUNCTION ---
def haversine(a, b):
    R = 6371
    lat1, lon1 = math.radians(a['lat']), math.radians(a['lon'])
    lat2, lon2 = math.radians(b['lat']), math.radians(b['lon'])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    return 2 * R * math.asin(math.sqrt(math.sin(dlat/2)**2 +
                                       math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2))


# --- NEAREST NEIGHBOR TSP ---
def tsp_nearest_neighbor(start, bins):
    unvisited = bins.copy()
    path = [start]
    current = start
    while unvisited:
        nearest = min(unvisited, key=lambda b: haversine(current, b))
        path.append(nearest)
        unvisited.remove(nearest)
        current = nearest
    path.append(start)  # <-- NEW: return to depot after finishing load
    return path


# --- CHUNK UTILITY ---
def chunked(iterable, size):
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk


# ====================================================================
#          NEW SECTION — TRUCK CAPACITY HANDLING
# ====================================================================

# Split bins into truck loads
loads = [trash_bins[i:i+TRUCK_CAPACITY] for i in range(0, len(trash_bins), TRUCK_CAPACITY)]

# Each load will produce its own small TSP route, then mapped
full_route = []       # a single list of points (no depot duplicates)
load_routes = []      # grouped by load for color coding


for load_idx, load_bins in enumerate(loads):
    sub_route = tsp_nearest_neighbor(START_POINT, load_bins)

    # skip first depot but keep final depot
    load_routes.append(sub_route)
    full_route.extend(sub_route[1:])  # append load without repeating first depot


# ====================================================================
#                            MAP GENERATION
# ====================================================================
m = folium.Map(location=CITY_CENTER, zoom_start=13)
marker_cluster = MarkerCluster(disableClusteringAtZoom=14).add_to(m)

sequence_number = 1

# ORS request per load (not entire trip; avoids API limit)
for load_idx, load_route in enumerate(load_routes):
    color = ROUTE_COLORS[load_idx % len(ROUTE_COLORS)]

    # Convert to ORS coords
    coords = [[p['lon'], p['lat']] for p in load_route]

    # ORS chunking (40 waypoints max)
    for chunk in chunked(coords, CHUNK_SIZE):
        try:
            directions = client.directions(
                coordinates=chunk,
                profile='driving-car',
                format='geojson'
            )
            folium.GeoJson(
                directions,
                style_function=lambda x, col=color: {'color': color, 'weight': 3, 'opacity': 0.7}
            ).add_to(m)
        except Exception as e:
            print(f"ORS failed for load {load_idx}: {e}")

    # Place bin markers
    for point in load_route:
        if point == START_POINT:
            continue

        folium.Marker(
            location=[point['lat'], point['lon']],
            popup=f"Bin {point['id']}<br>{point['percent_full']}%",
            icon=folium.Icon(color='green', icon='trash', prefix='fa')
        ).add_to(marker_cluster)

        # Add number label
        folium.map.Marker(
            [point['lat'] - 0.00015, point['lon']],
            icon=folium.DivIcon(html=f"""
                <div style="
                    font-size:12px;
                    font-weight:bold;
                    color:white;
                    background-color:{color};
                    border-radius:6px;
                    padding:2px 5px;
                    border:1px solid black;
                    display:inline-block;">
                    {sequence_number}
                </div>""")
        ).add_to(marker_cluster)

        sequence_number += 1


# Depot marker
folium.Marker(
    [START_POINT['lat'], START_POINT['lon']],
    popup="Depot",
    icon=folium.Icon(color='black', icon='home')
).add_to(m)

# Save map
m.save("trash_route_chunked_ors.html")
print("🚛 Trash route with truck capacity generated!")
