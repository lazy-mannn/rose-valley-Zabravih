from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import TrashCan, FillRecord
import json
from datetime import datetime, timedelta
from django.utils import timezone
import folium
from folium.plugins import HeatMap, MarkerCluster
import openrouteservice
from decouple import config
import os
from django.conf import settings

# --- CONFIGURABLE LOCATIONS ---
DEPOT_LOCATION = {
    'lat': 42.616416,
    'lon': 25.420107,
    'name': 'Depot (Starting Point)'
}

LANDFILL_LOCATION = {
    'lat': 42.592689,
    'lon': 25.469143,
    'name': 'Landfill (Disposal Site)'
}

ROUTE_COLORS = ['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'cyan']

# Mapping from AI categories to fill levels
# is_scattered = overflowing (trash spilling outside bin)
AI_CATEGORY_MAP = {
    'is_empty': 5,
    'is_half': 50,
    'is_full': 95,
    'is_scattered': 110  # OVERFLOWING - more than 100% full, trash outside bin
}

# Home view with maps
def home(request):
    # Get truck capacity from request or use default
    truck_capacity = int(request.GET.get('truck_capacity', 10))
    
    # Get statistics
    total_cans = TrashCan.objects.count()
    
    # Get latest record for each trash can with predictions
    can_stats = []
    for can in TrashCan.objects.all():
        predicted_fill = can.get_predicted_fill_level()
        days_until_full = can.get_days_until_full()
        daily_rate = can.get_average_daily_fill_rate()
        
        can_stats.append({
            'predicted_fill': predicted_fill,
            'days_until_full': days_until_full,
            'daily_rate': daily_rate
        })
    
    if can_stats:
        # Count bins >=80% OR overflowing as "full"
        full_cans = sum(1 for stat in can_stats if stat['predicted_fill'] >= 80)
        
        # Average fill across all bins
        avg_fill = sum(min(stat['predicted_fill'], 100) for stat in can_stats) / len(can_stats)
        
        # Count bins needing collection (>60% OR <3 days until full)
        needs_collection = sum(1 for stat in can_stats 
                             if stat['predicted_fill'] >= 60 or stat['days_until_full'] <= 3)
        
        # Average daily fill rate across all bins
        avg_daily_rate = sum(stat['daily_rate'] for stat in can_stats) / len(can_stats)
    else:
        full_cans = 0
        avg_fill = 0
        needs_collection = 0
        avg_daily_rate = 0
    
    context = {
        'total_cans': total_cans,
        'full_cans': full_cans,
        'avg_fill': round(avg_fill, 1),
        'needs_collection': needs_collection,
        'avg_daily_rate': round(avg_daily_rate, 1),
        'truck_capacity': truck_capacity,
    }
    
    return render(request, 'home.html', context)


# Generate heatmap (separate endpoint)
@require_http_methods(["GET"])
def generate_heatmap_view(request):
    trash_cans = TrashCan.objects.all()
    
    # Get latest record for each trash can
    latest_records = []
    for can in trash_cans:
        latest = FillRecord.objects.filter(trashcan=can).order_by('-timestamp').first()
        if latest:
            latest_records.append((can, latest))
    
    # Create map
    if trash_cans.exists():
        avg_lat = sum(can.latitude for can in trash_cans) / trash_cans.count()
        avg_lon = sum(can.longitude for can in trash_cans) / trash_cans.count()
    else:
        avg_lat, avg_lon = 42.6181, 25.3954
    
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
    
    # Build heatmap data (cap at 100% for visualization)
    heat_data = []
    for can, record in latest_records:
        heat_data.append([
            can.latitude,
            can.longitude,
            min(record.fill_level, 100) / 100.0
        ])
    
    HeatMap(heat_data, radius=25, blur=20, max_zoom=1).add_to(m)
    
    # Add individual markers with detailed info
    for can, record in latest_records:
        daily_rate = can.get_average_daily_fill_rate()
        predicted_fill = can.get_predicted_fill_level()
        days_until_full = can.get_days_until_full()
        
        # Determine color based on predicted fill level
        if predicted_fill >= 100:  # Overflowing
            color = 'darkred'
            status = '🚨 OVERFLOWING'
        elif predicted_fill >= 80:
            color = 'red'
            status = '⚠️ FULL'
        elif predicted_fill >= 60:
            color = 'orange'
            status = '⚡ HIGH'
        elif predicted_fill >= 40:
            color = 'lightgreen'
            status = '✓ MEDIUM'
        else:
            color = 'green'
            status = '✓ LOW'
        
        # Show actual fill level (may be >100%)
        display_fill = record.fill_level if record.fill_level <= 100 else f"{record.fill_level}% (OVERFLOW)"
        
        popup_html = f"""
        <div style="font-family: Arial; font-size: 12px; width: 240px;">
            <b>🗑️ Bin ID: {can.id}</b><br>
            <div style="background: {'#d32f2f' if predicted_fill >= 100 else '#f44336' if predicted_fill >= 80 else '#ff9800' if predicted_fill >= 60 else '#4caf50'}; 
                        color: white; 
                        padding: 5px; 
                        margin: 5px 0; 
                        border-radius: 3px; 
                        text-align: center;">
                <strong>{status}</strong>
            </div>
            <hr style="margin: 5px 0;">
            <b>Current Fill:</b> {display_fill}<br>
            <b>Predicted Fill:</b> {predicted_fill}%<br>
            <b>Fill Rate:</b> {daily_rate}% per day<br>
            <b>Days Until Full:</b> {days_until_full}<br>
            <b>Last Emptied:</b> {can.last_emptied.strftime('%Y-%m-%d')}<br>
            <b>Last Update:</b> {record.timestamp.strftime('%Y-%m-%d %H:%M')}<br>
            <b>Location:</b> {can.latitude:.4f}, {can.longitude:.4f}
        </div>
        """
        
        folium.Marker(
            location=[can.latitude, can.longitude],
            popup=folium.Popup(popup_html, max_width=260),
            icon=folium.Icon(
                color=color,
                icon='trash',
                prefix='fa'
            ),
            tooltip=f"Bin {can.id}: {predicted_fill:.0f}%"
        ).add_to(m)
    
    # Return HTML response
    return JsonResponse({'html': m._repr_html_()})


# Generate route optimization map (separate endpoint)
@require_http_methods(["GET"])
def generate_route_view(request):
    truck_capacity = int(request.GET.get('truck_capacity', 10))
    highlight_route = request.GET.get('highlight', None)
    if highlight_route is not None:
        highlight_route = int(highlight_route)
    
    try:
        ORS_API_KEY = config('API_KEY')
        client = openrouteservice.Client(key=ORS_API_KEY)
    except:
        client = None
    
    # Get all bins that need collection (>60% OR <3 days until full)
    bins_to_collect = []
    for can in TrashCan.objects.all():
        predicted_fill = can.get_predicted_fill_level()
        days_until_full = can.get_days_until_full()
        
        # Collect if >60% OR overflowing OR will be full soon
        if predicted_fill >= 60 or predicted_fill >= 100 or days_until_full <= 3:
            bins_to_collect.append(can)
    
    if not bins_to_collect:
        # No urgent bins, show top 20 closest to depot
        all_bins = list(TrashCan.objects.all())
        # Sort by distance from depot
        all_bins.sort(key=lambda b: ((b.latitude - DEPOT_LOCATION['lat'])**2 + 
                                     (b.longitude - DEPOT_LOCATION['lon'])**2)**0.5)
        bins_to_collect = all_bins[:20]
    
    # Split bins into routes based on truck capacity
    # Use geographic clustering to minimize distance
    routes = []
    remaining_bins = bins_to_collect.copy()
    
    while remaining_bins:
        current_route = []
        
        # Start route from depot or landfill
        if not routes:
            start_point = (DEPOT_LOCATION['lat'], DEPOT_LOCATION['lon'])
        else:
            start_point = (LANDFILL_LOCATION['lat'], LANDFILL_LOCATION['lon'])
        
        # Greedy nearest-neighbor algorithm for this route
        current_location = start_point
        
        while len(current_route) < truck_capacity and remaining_bins:
            # Find nearest bin to current location
            nearest_bin = min(remaining_bins, 
                            key=lambda b: ((b.latitude - current_location[0])**2 + 
                                         (b.longitude - current_location[1])**2)**0.5)
            
            current_route.append(nearest_bin)
            remaining_bins.remove(nearest_bin)
            current_location = (nearest_bin.latitude, nearest_bin.longitude)
        
        routes.append(current_route)
    
    # Center map
    all_lats = [DEPOT_LOCATION['lat'], LANDFILL_LOCATION['lat']] + [bin.latitude for bin in bins_to_collect]
    all_lons = [DEPOT_LOCATION['lon'], LANDFILL_LOCATION['lon']] + [bin.longitude for bin in bins_to_collect]
    
    avg_lat = sum(all_lats) / len(all_lats) if all_lats else 42.6181
    avg_lon = sum(all_lons) / len(all_lons) if all_lons else 25.3954
    
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14, 
                   tiles='OpenStreetMap',
                   zoom_control=True,
                   scrollWheelZoom=True,
                   dragging=True)
    
    # Add Depot marker
    folium.Marker(
        location=[DEPOT_LOCATION['lat'], DEPOT_LOCATION['lon']],
        popup=f"<b>{DEPOT_LOCATION['name']}</b>",
        icon=folium.Icon(color='green', icon='home', prefix='fa'),
        tooltip=DEPOT_LOCATION['name']
    ).add_to(m)
    
    # Add Landfill marker
    folium.Marker(
        location=[LANDFILL_LOCATION['lat'], LANDFILL_LOCATION['lon']],
        popup=f"<b>{LANDFILL_LOCATION['name']}</b>",
        icon=folium.Icon(color='black', icon='recycle', prefix='fa'),
        tooltip=LANDFILL_LOCATION['name']
    ).add_to(m)
    
    total_distance = 0
    bin_counter = 1
    
    # Store route details for response
    route_details = []
    
    # Draw each route
    for route_idx, route_bins in enumerate(routes):
        route_color = ROUTE_COLORS[route_idx % len(ROUTE_COLORS)]
        
        # Adjust opacity based on highlight
        if highlight_route is not None:
            opacity = 1.0 if route_idx == highlight_route else 0.15
            weight = 7 if route_idx == highlight_route else 2
            show_markers = (route_idx == highlight_route)
        else:
            opacity = 0.7
            weight = 5
            show_markers = True
        
        # Further optimize with ORS optimization API (for exact routing)
        optimized_bins = route_bins
        
        if client and len(route_bins) > 2:
            try:
                if route_idx == 0:
                    start_location = [DEPOT_LOCATION['lon'], DEPOT_LOCATION['lat']]
                else:
                    start_location = [LANDFILL_LOCATION['lon'], LANDFILL_LOCATION['lat']]
                
                end_location = [LANDFILL_LOCATION['lon'], LANDFILL_LOCATION['lat']]
                
                jobs = [{'id': idx, 'location': [bin.longitude, bin.latitude]} 
                       for idx, bin in enumerate(route_bins)]
                
                optimization_result = client.optimization(
                    jobs=jobs,
                    vehicles=[{
                        'id': 0,
                        'start': start_location,
                        'end': end_location,
                        'capacity': [truck_capacity]
                    }],
                    geometry=True
                )
                
                optimized_order = optimization_result['routes'][0]['steps']
                optimized_bins = []
                for step in optimized_order:
                    if step['type'] == 'job':
                        optimized_bins.append(route_bins[step['job']])
                
                if not optimized_bins:
                    optimized_bins = route_bins
                    
            except Exception as e:
                print(f"ORS optimization failed for route {route_idx + 1}: {e}")
                optimized_bins = route_bins
        
        # Add numbered markers
        route_bin_ids = []
        for bin in optimized_bins:
            predicted_fill = bin.get_predicted_fill_level()
            daily_rate = bin.get_average_daily_fill_rate()
            days_until_full = bin.get_days_until_full()
            
            route_bin_ids.append(bin.id)
            
            if show_markers:
                # Determine status
                if predicted_fill >= 100:
                    status = '🚨 OVERFLOWING'
                    status_color = '#d32f2f'
                elif predicted_fill >= 80:
                    status = '⚠️ FULL'
                    status_color = '#f44336'
                elif predicted_fill >= 60:
                    status = '⚡ HIGH'
                    status_color = '#ff9800'
                else:
                    status = '✓ MEDIUM'
                    status_color = '#4caf50'
                
                popup_html = f"""
                <div style="font-family: Arial; font-size: 13px;">
                    <b>🚛 Route {route_idx + 1}, Stop {bin_counter}</b><br>
                    <div style="background: {status_color}; 
                                color: white; 
                                padding: 5px; 
                                margin: 5px 0; 
                                border-radius: 3px; 
                                text-align: center;">
                        <strong>{status}</strong>
                    </div>
                    <hr style="margin: 5px 0;">
                    <b>Bin ID:</b> {bin.id}<br>
                    <b>Predicted Fill:</b> {predicted_fill:.1f}%<br>
                    <b>Fill Rate:</b> {daily_rate:.1f}% /day<br>
                    <b>Days Until Full:</b> {days_until_full:.1f}<br>
                    <b>Last Emptied:</b> {bin.last_emptied.strftime('%Y-%m-%d')}
                </div>
                """
                
                # Use different marker color for overflowing bins
                marker_color = 'darkred' if predicted_fill >= 100 else 'red'
                
                folium.Marker(
                    location=[bin.latitude, bin.longitude],
                    popup=folium.Popup(popup_html, max_width=250),
                    icon=folium.Icon(color=marker_color, icon='trash', prefix='fa'),
                    tooltip=f"Stop {bin_counter}: {predicted_fill:.0f}%"
                ).add_to(m)
                
                # Add number label
                folium.Marker(
                    location=[bin.latitude - 0.0002, bin.longitude],
                    icon=folium.DivIcon(html=f"""
                        <div style="
                            font-size: 14px;
                            font-weight: bold;
                            color: white;
                            background-color: {route_color};
                            border-radius: 50%;
                            width: 32px;
                            height: 32px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            border: 3px solid white;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
                        ">
                            {bin_counter}
                        </div>
                    """)
                ).add_to(m)
            
            bin_counter += 1
        
        # Draw route line
        if client and len(optimized_bins) >= 1:
            try:
                if route_idx == 0:
                    coords = [[DEPOT_LOCATION['lon'], DEPOT_LOCATION['lat']]]
                else:
                    coords = [[LANDFILL_LOCATION['lon'], LANDFILL_LOCATION['lat']]]
                
                coords += [[bin.longitude, bin.latitude] for bin in optimized_bins]
                coords.append([LANDFILL_LOCATION['lon'], LANDFILL_LOCATION['lat']])
                
                directions = client.directions(
                    coordinates=coords,
                    profile='driving-car',
                    format='geojson'
                )
                
                folium.GeoJson(
                    directions,
                    style_function=lambda x, color=route_color, op=opacity, w=weight: {
                        'color': color,
                        'weight': w,
                        'opacity': op
                    },
                    tooltip=f"Route {route_idx + 1}" if show_markers else None
                ).add_to(m)
                
                route_distance = directions['features'][0]['properties']['segments'][0]['distance'] / 1000
                total_distance += route_distance
                
                route_details.append({
                    'route_number': route_idx + 1,
                    'bins': route_bin_ids,
                    'distance': round(route_distance, 1)
                })
                
            except Exception as e:
                print(f"Route drawing failed for route {route_idx + 1}: {e}")
    
    return JsonResponse({
        'html': m._repr_html_(),
        'stats': {
            'total_routes': len(routes),
            'total_bins': len(bins_to_collect),
            'total_distance': round(total_distance, 1),
            'truck_capacity': truck_capacity
        },
        'route_details': route_details
    })


# API endpoint for Raspberry Pi to update fill level
@csrf_exempt
@csrf_exempt
@require_http_methods(["POST"])
def api_update_fill_level(request):
    """
    Raspberry Pi sends data DURING collection.
    
    FLOW:
    1. Raspberry Pi captures image of bin
    2. AI classifies fill level (this is BEFORE emptying)
    3. Sends to Django
    4. Django records this as the "before emptying" level
    5. Django immediately marks bin as emptied (creates 0% record)
    6. Updates last_emptied timestamp
    
    This means: Every AI reading = collection event
    """
    try:
        data = json.loads(request.body)
        trashcan_id = data.get('trashcan_id')
        
        # Accept either fill_level or AI category
        fill_level = data.get('fill_level')
        category = data.get('category')
        
        if not trashcan_id:
            return JsonResponse({'success': False, 'error': 'Missing trashcan_id'}, status=400)
        
        # Convert AI category to fill level
        if category and not fill_level:
            fill_level = AI_CATEGORY_MAP.get(category.lower(), 50)
        
        if fill_level is None:
            return JsonResponse({'success': False, 'error': 'Missing fill_level or category'}, status=400)
        
        if fill_level < 0:
            return JsonResponse({'success': False, 'error': 'fill_level must be >= 0'}, status=400)
        
        trashcan = TrashCan.objects.get(id=trashcan_id)
        
        # Record the fill level BEFORE collection
        before_record = FillRecord.objects.create(
            trashcan=trashcan,
            fill_level=fill_level,
            source='ai'
        )
        
        # Immediately mark as emptied (bin is being collected RIGHT NOW)
        trashcan.mark_as_emptied()
        
        # Get updated prediction data
        predicted_fill = trashcan.get_predicted_fill_level()
        daily_rate = trashcan.get_average_daily_fill_rate()
        days_until_full = trashcan.get_days_until_full()
        
        return JsonResponse({
            'success': True,
            'trashcan_id': trashcan.id,
            'collected_at_fill_level': before_record.fill_level,
            'new_predicted_fill': predicted_fill,
            'updated_daily_rate': daily_rate,
            'days_until_full': days_until_full,
            'emptied_at': trashcan.last_emptied.isoformat(),
            'message': f'Bin collected at {fill_level}% and emptied'
        })
        
    except TrashCan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trash can not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# API endpoint to mark bin as emptied (called by collection crew)
@csrf_exempt
@require_http_methods(["POST"])
def api_mark_emptied(request):
    try:
        data = json.loads(request.body)
        trashcan_id = data.get('trashcan_id')
        
        if not trashcan_id:
            return JsonResponse({'success': False, 'error': 'Missing trashcan_id'}, status=400)
        
        trashcan = TrashCan.objects.get(id=trashcan_id)
        trashcan.mark_as_emptied()
        
        return JsonResponse({
            'success': True,
            'trashcan_id': trashcan.id,
            'emptied_at': trashcan.last_emptied.isoformat(),
            'message': 'Bin marked as emptied'
        })
        
    except TrashCan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trash can not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# API endpoint to get trash can status
@require_http_methods(["GET"])
def api_get_trashcan(request, trashcan_id):
    try:
        trashcan = TrashCan.objects.get(id=trashcan_id)
        latest_record = FillRecord.objects.filter(trashcan=trashcan).order_by('-timestamp').first()
        fill_frequency = trashcan.get_fill_frequency()
        
        return JsonResponse({
            'success': True,
            'trashcan_id': trashcan.id,
            'latitude': trashcan.latitude,
            'longitude': trashcan.longitude,
            'fill_level': latest_record.fill_level if latest_record else 0,
            'fill_frequency': fill_frequency,
            'timestamp': latest_record.timestamp.isoformat() if latest_record else None
        })
    except TrashCan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trash can not found'}, status=404)


# API endpoint to get all trash cans
@require_http_methods(["GET"])
def api_list_trashcans(request):
    trash_cans = TrashCan.objects.all()
    
    data = []
    for can in trash_cans:
        latest = FillRecord.objects.filter(trashcan=can).order_by('-timestamp').first()
        fill_frequency = can.get_fill_frequency()
        
        data.append({
            'id': can.id,
            'latitude': can.latitude,
            'longitude': can.longitude,
            'fill_level': latest.fill_level if latest else 0,
            'fill_frequency': fill_frequency,
            'timestamp': latest.timestamp.isoformat() if latest else None
        })
    
    return JsonResponse({'success': True, 'trash_cans': data})
