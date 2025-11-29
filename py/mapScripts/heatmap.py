{"id":"98145","variant":"standard","title":"Scalable Trash Bin Heatmap with Clustering"}
import folium
from folium.plugins import HeatMap, MarkerCluster
import random

# Simulate a large dataset (1000+ trash bins)
# Latitude and longitude are centered around some city coordinates
num_bins = 200
center_lat, center_lon = 42.6181, 25.3954  # Example: Paris

trash_bins = []
for i in range(num_bins):
    lat = center_lat + random.uniform(-0.01, 0.01)
    lon = center_lon + random.uniform(-0.01, 0.01)
    percent_full = random.randint(10, 100)
    frequency = random.randint(1, 12)  # usage per day
    trash_bins.append({
        'name': f'Bin {i+1}',
        'latitude': lat,
        'longitude': lon,
        'percent_full': percent_full,
        'frequency': frequency
    })

# Normalize weight for heatmap
max_frequency = max(bin['frequency'] for bin in trash_bins)
for bin in trash_bins:
    bin['weight'] = (bin['percent_full'] / 100) * (bin['frequency'] / max_frequency)

# Center map
avg_lat = sum([bin['latitude'] for bin in trash_bins]) / len(trash_bins)
avg_lon = sum([bin['longitude'] for bin in trash_bins]) / len(trash_bins)
m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13)

# Add heatmap layer
heat_data = [[bin['latitude'], bin['longitude'], bin['weight']] for bin in trash_bins]
HeatMap(heat_data, radius=20).add_to(m)

# Add marker clustering for detailed info
cluster = MarkerCluster().add_to(m)
for bin in trash_bins:
    folium.Marker(
        location=[bin['latitude'], bin['longitude']],
        popup=(
            f"{bin['name']}<br>"
            f"Full: {bin['percent_full']}%<br>"
            f"Frequency: {bin['frequency']} per day"
        )
    ).add_to(cluster)

# Save map
m.save('scalable_trash_bin_heatmap.html')

print("Scalable trash bin heatmap generated! Open 'scalable_trash_bin_heatmap.html' in your browser.")
