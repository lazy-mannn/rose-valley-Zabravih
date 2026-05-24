from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import TrashCan, FillRecord, APIKey
import json
from datetime import datetime, timedelta
from django.utils import timezone
import folium
from folium.plugins import HeatMap, MarkerCluster
import openrouteservice
from decouple import config
import pytz

# ── DRF imports (Phase 2) ─────────────────────────────────────────────────────
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count, Q, Subquery, OuterRef, Avg
import hashlib
import math
from collections import defaultdict, Counter

# Sofia timezone for display
SOFIA_TZ = pytz.timezone('Europe/Sofia')

def format_local_time(dt):
    """Convert UTC to Sofia time"""
    if dt:
        return dt.astimezone(SOFIA_TZ).strftime('%Y-%m-%d %H:%M')
    return '-'

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

# --- AUTHENTICATION DECORATOR ---
def require_api_key(view_func):
    """Simple API key check - no rate limiting"""
    def wrapper(request, *args, **kwargs):
        # Get API key from header or query parameter
        api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
        
        if not api_key:
            return JsonResponse({
                'success': False,
                'error': 'Missing API key',
                'hint': 'Include X-API-Key header or ?api_key= parameter'
            }, status=401)
        
        # Check if key exists and is active
        try:
            key_obj = APIKey.objects.get(key=api_key, is_active=True)
            
            # Update last used timestamp
            key_obj.last_used = timezone.now()
            key_obj.save(update_fields=['last_used'])
            
            # Store device name in request for logging
            request.api_device = key_obj.device_name
            
        except APIKey.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or inactive API key'
            }, status=403)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# --- PUBLIC VIEWS (No Auth) ---

# Home view with maps
def pitch(request):
    return render(request, 'pitch.html')


def home(request):
    truck_capacity = int(request.GET.get('truck_capacity', 20))
    week_ago = timezone.now() - timedelta(days=7)

    # ── Counts from DB — single queries, works at 43k scale ──────────────
    total_cans = TrashCan.objects.count()

    # All fill data stats come from FillRecord aggregates, not per-bin loops.
    # Only bins with fill records have meaningful monitored data.
    from django.db.models import Max, FloatField
    from django.db.models.functions import Cast

    # Latest fill level per bin (subquery approach via annotation)
    # We get the most recent non-zero fill record for each bin.
    latest_fills = (
        FillRecord.objects
        .filter(fill_level__gt=0)
        .values('trashcan_id')
        .annotate(latest_fill=Max('fill_level'), latest_ts=Max('timestamp'))
    )

    # Build quick lookup: trashcan_id → latest_fill
    fill_map = {row['trashcan_id']: row['latest_fill'] for row in latest_fills}

    monitored_fills = list(fill_map.values())
    monitored_count = len(monitored_fills)

    if monitored_fills:
        overflow_count       = sum(1 for f in monitored_fills if f >= 100)
        critical_count       = sum(1 for f in monitored_fills if 90 <= f < 100)
        warning_count        = sum(1 for f in monitored_fills if 70 <= f < 90)
        full_cans            = sum(1 for f in monitored_fills if f >= 80)
        needs_collection     = sum(1 for f in monitored_fills if f >= 60)
        avg_fill             = sum(min(f, 100) for f in monitored_fills) / monitored_count
    else:
        overflow_count = critical_count = warning_count = 0
        full_cans = needs_collection = 0
        avg_fill = 0

    # Weekly collections = zero-fill records created in the past 7 days
    total_collections_last_week = FillRecord.objects.filter(
        fill_level=0,
        timestamp__gte=week_ago,
    ).count()

    # Fill rate stats — only meaningful for bins with real AI/manual history
    # Pull rates from the 200 most-recently-active monitored bins to stay fast
    from django.db.models import Subquery, OuterRef
    recent_bin_ids = (
        FillRecord.objects
        .filter(source__in=['ai', 'manual'], timestamp__gte=week_ago)
        .values_list('trashcan_id', flat=True)
        .distinct()[:200]
    )
    rate_samples = []
    for can in TrashCan.objects.filter(id__in=list(recent_bin_ids)).prefetch_related('fill_records'):
        rate = can.get_average_daily_fill_rate()
        if rate != 10.0:  # skip default fallback
            rate_samples.append(rate)

    avg_daily_rate   = round(sum(rate_samples) / len(rate_samples), 1) if rate_samples else 0
    fastest_fill_rate = round(max(rate_samples), 1) if rate_samples else 0
    slowest_fill_rate = round(min(rate_samples), 1) if rate_samples else 0

    context = {
        'total_cans':                total_cans,
        'full_cans':                 full_cans,
        'avg_fill':                  round(avg_fill, 1),
        'needs_collection':          needs_collection,
        'avg_daily_rate':            avg_daily_rate,
        'truck_capacity':            truck_capacity,
        'overflow_count':            overflow_count,
        'critical_count':            critical_count,
        'warning_count':             warning_count,
        'total_collections_last_week': total_collections_last_week,
        'fastest_fill_rate':         fastest_fill_rate,
        'slowest_fill_rate':         slowest_fill_rate,
    }

    return render(request, 'home.html', context)


# Generate heatmap (separate endpoint)
@require_http_methods(["GET"])
def generate_heatmap_view(request):
    # Only show bins that have actual fill data — avoids iterating 43k empty bins
    trash_cans = TrashCan.objects.filter(
        fill_records__isnull=False
    ).prefetch_related('fill_records').distinct()

    latest_records = []
    for can in trash_cans:
        latest = can.fill_records.order_by('-timestamp').first()
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
            <b>Last Emptied:</b> {format_local_time(can.last_emptied)}<br>
            <b>Last Update:</b> {format_local_time(record.timestamp)}<br>
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
    truck_capacity = int(request.GET.get('truck_capacity', 20))
    highlight_route = request.GET.get('highlight', None)
    if highlight_route is not None:
        highlight_route = int(highlight_route)
    
    try:
        ORS_API_KEY = config('API_KEY')
        client = openrouteservice.Client(key=ORS_API_KEY)
    except:
        client = None
    
    # Only consider bins with fill records — the rest have no monitoring data
    monitored_bins = list(
        TrashCan.objects.filter(fill_records__isnull=False)
        .prefetch_related('fill_records')
        .distinct()
    )

    bins_to_collect = []
    for can in monitored_bins:
        predicted_fill = can.get_predicted_fill_level()
        days_until_full = can.get_days_until_full()
        if predicted_fill >= 60 or predicted_fill >= 100 or days_until_full <= 1:
            bins_to_collect.append(can)

    if not bins_to_collect:
        # No urgent bins — show the 20 most-recently filled monitored bins
        bins_to_collect = sorted(
            monitored_bins,
            key=lambda b: b.fill_records.order_by('-timestamp').values_list('timestamp', flat=True).first() or timezone.now(),
            reverse=True,
        )[:20]
    
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


# --- SECURED API ENDPOINTS ---

# API endpoint for Raspberry Pi to update fill level
@csrf_exempt
@require_http_methods(["POST"])
@require_api_key
def api_update_fill_level(request):
    """
    🚨 CORRECT FLOW: NFC Scan = Bin Just Emptied!
    
    The proper collection cycle is:
    1. Bin fills from 0% to X% over time
    2. Truck arrives, AI sees bin at X%
    3. Driver scans NFC tag (bin NOW empty)
    4. We record: "Collected at X%, now empty"
    
    Algorithm then calculates: X% / days_since_last_empty = fill_rate
    """
    try:
        data = json.loads(request.body)
        
        # Find bin by UID or ID
        nfc_uid = data.get('nfc_uid')
        trashcan_id = data.get('trashcan_id')
        
        if not nfc_uid and not trashcan_id:
            return JsonResponse({
                'success': False,
                'error': 'Missing nfc_uid or trashcan_id'
            }, status=400)
        
        # Find bin
        if nfc_uid:
            trashcan = TrashCan.get_by_nfc_uid(str(nfc_uid))
            if not trashcan:
                return JsonResponse({
                    'success': False,
                    'error': f'No bin registered with NFC UID: {nfc_uid}',
                    'hint': 'Register this NFC tag in admin panel first'
                }, status=404)
        else:
            try:
                trashcan = TrashCan.objects.get(id=trashcan_id)
            except TrashCan.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Bin {trashcan_id} not found'
                }, status=404)
        
        # Get AI classification
        category = data.get('category')
        confidence = data.get('confidence', 0)
        
        # Convert AI category to fill level
        if category:
            ai_fill_level = AI_CATEGORY_MAP.get(category.lower(), 50)
        else:
            # If no AI data, use predicted level as fallback
            ai_fill_level = int(trashcan.get_predicted_fill_level())
        
        # ============ CRITICAL FIX: PROPER SEQUENCE ============
        
        # STEP 1: Get current prediction (what we THINK it should be at)
        predicted_before = trashcan.get_predicted_fill_level()
        
        # STEP 2: Record what AI actually saw (pre-collection state)
        # This is the END of the fill cycle (0% → X%)
        collection_record = FillRecord.objects.create(
            trashcan=trashcan,
            fill_level=int(ai_fill_level),
            source='ai',
            timestamp=timezone.now()
        )
        
        # STEP 3: Now mark bin as empty (START of new cycle)
        # This creates a 0% record and updates last_emptied timestamp
        trashcan.mark_as_emptied()
        
        # ============ RESULT: DATABASE SHOWS CORRECT SEQUENCE ============
        # Before: Last record was 0% (previous collection)
        # Now:    New record is X% (AI saw before collection)
        #         Then 0% (just emptied)
        # Algorithm sees: 0% → X% over Y days = rate ✓
        
        # ============ GET UPDATED PREDICTIONS ============
        new_predicted_fill = trashcan.get_predicted_fill_level()  # Should be ~0-5%
        updated_daily_rate = trashcan.get_average_daily_fill_rate()  # Recalculated!
        days_until_full = trashcan.get_days_until_full()
        
        # Calculate accuracy
        prediction_accuracy = 100 - abs(predicted_before - ai_fill_level)
        
        return JsonResponse({
            'success': True,
            'trashcan_id': trashcan.id,
            'nfc_uid': trashcan.nfc_uid,
            'collection_details': {
                'collected_at_fill_level': int(ai_fill_level),
                'ai_category': category,
                'ai_confidence': confidence,
                'predicted_fill_was': round(predicted_before, 1),
                'prediction_accuracy': round(max(0, prediction_accuracy), 1),
                'emptied_at': format_local_time(trashcan.last_emptied),
            },
            'updated_predictions': {
                'current_fill': round(new_predicted_fill, 1),
                'daily_rate': round(updated_daily_rate, 1),
                'days_until_full': round(days_until_full, 1),
            },
            'device': request.api_device,
            'message': f'✅ Bin {trashcan.id} collected at {ai_fill_level}% full'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@require_api_key
def api_mark_emptied(request):
    """SECURED: Mark bin as emptied (manual collection without AI)"""
    try:
        data = json.loads(request.body)
        trashcan_id = data.get('trashcan_id')
        nfc_uid = data.get('nfc_uid')
        
        if not trashcan_id and not nfc_uid:
            return JsonResponse({
                'success': False,
                'error': 'Missing trashcan_id or nfc_uid'
            }, status=400)
        
        # Find bin
        if nfc_uid:
            trashcan = TrashCan.get_by_nfc_uid(str(nfc_uid))
            if not trashcan:
                return JsonResponse({
                    'success': False,
                    'error': f'No bin registered with NFC UID: {nfc_uid}'
                }, status=404)
        else:
            try:
                trashcan = TrashCan.objects.get(id=trashcan_id)
            except TrashCan.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Bin {trashcan_id} not found'
                }, status=404)
        
        # Get predicted fill before emptying
        predicted_before = trashcan.get_predicted_fill_level()
        
        # Record predicted level before collection
        FillRecord.objects.create(
            trashcan=trashcan,
            fill_level=int(predicted_before),
            source='predicted',
            timestamp=timezone.now()
        )
        
        # Mark as emptied
        trashcan.mark_as_emptied()
        
        return JsonResponse({
            'success': True,
            'trashcan_id': trashcan.id,
            'nfc_uid': trashcan.nfc_uid,
            'collected_at_predicted': round(predicted_before, 1),
            'emptied_at': format_local_time(trashcan.last_emptied),
            'device': request.api_device,
            'message': f'Bin {trashcan.id} marked as emptied'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# API endpoint to get trash can status
@require_http_methods(["GET"])
@require_api_key
def api_get_trashcan(request, trashcan_id):
    """SECURED: Get trash can status"""
    try:
        trashcan = TrashCan.objects.get(id=trashcan_id)
        latest_record = FillRecord.objects.filter(trashcan=trashcan).order_by('-timestamp').first()
        
        predicted_fill = trashcan.get_predicted_fill_level()
        daily_rate = trashcan.get_average_daily_fill_rate()
        days_until_full = trashcan.get_days_until_full()
        
        return JsonResponse({
            'success': True,
            'trashcan_id': trashcan.id,
            'latitude': trashcan.latitude,
            'longitude': trashcan.longitude,
            'current_fill_level': latest_record.fill_level if latest_record else 0,
            'predicted_fill_level': predicted_fill,
            'daily_fill_rate': daily_rate,
            'days_until_full': days_until_full,
            'last_emptied': format_local_time(trashcan.last_emptied),
            'last_update': format_local_time(latest_record.timestamp) if latest_record else None
        })
    except TrashCan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trash can not found'}, status=404)


@require_http_methods(["GET"])
@require_api_key
def api_list_trashcans(request):
    """SECURED: Get all trash cans"""
    trash_cans = TrashCan.objects.all()
    
    data = []
    for can in trash_cans:
        latest = FillRecord.objects.filter(trashcan=can).order_by('-timestamp').first()
        predicted_fill = can.get_predicted_fill_level()
        daily_rate = can.get_average_daily_fill_rate()
        
        data.append({
            'id': can.id,
            'latitude': can.latitude,
            'longitude': can.longitude,
            'current_fill': latest.fill_level if latest else 0,
            'predicted_fill': predicted_fill,
            'daily_rate': daily_rate,
            'last_emptied': format_local_time(can.last_emptied),
            'last_update': format_local_time(latest.timestamp) if latest else None
        })
    
    return JsonResponse({'success': True, 'total_bins': len(data), 'trash_cans': data})


# ── Phase 2: Public DRF endpoints ────────────────────────────────────────────

# Degrees per grid cell at each zoom level.
# Chosen so the initial zoom-11 view of Sofia (~0.28°×0.60°) shows ~30-40 clusters.
GRID_SIZE = {
    9:  0.60,   # ~5 clusters city-wide — large areas
    10: 0.30,   # ~8 clusters
    11: 0.15,   # ~12 clusters (initial map zoom)
    12: 0.10,   # ~18 clusters
    13: 0.05,   # ~35 clusters — fine detail before individual bins
}


def _cache_get(key):
    try:
        return cache.get(key)
    except Exception:
        return None


def _cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        pass


def _round_bbox(north, south, east, west, snap):
    """Round bbox outward to nearest 'snap' degrees for better cache hit rate."""
    return (
        math.ceil(north / snap) * snap,
        math.floor(south / snap) * snap,
        math.ceil(east  / snap) * snap,
        math.floor(west  / snap) * snap,
    )


class BinClustersView(APIView):
    """
    GET /api/bins/clusters/
    Returns one cluster per district, positioned at the district's centroid.
    zoom/bbox params accepted but ignored — district view is always global.
    """
    def get(self, request):
        cache_key = 'bins:clusters:districts:v1'
        cached = _cache_get(cache_key)
        if cached is not None:
            return Response(cached)

        rows = (
            TrashCan.objects
            .filter(district_id__isnull=False)
            .values('district_id')
            .annotate(
                count=Count('id'),
                lat=Avg('latitude'),
                lon=Avg('longitude'),
            )
        )

        clusters = [
            {
                'lat': round(r['lat'], 5),
                'lon': round(r['lon'], 5),
                'count': r['count'],
                'district_id': r['district_id'],
            }
            for r in rows
            if r['lat'] is not None and r['lon'] is not None
        ]

        result = {'clusters': clusters}
        _cache_set(cache_key, result, 3600)
        return Response(result)


class BinViewportView(APIView):
    """
    GET /api/bins/viewport/?north=F&south=F&east=F&west=F

    Returns individual bins visible in the bounding box (max 500) as a
    GeoJSON FeatureCollection.  fill_level comes from the latest FillRecord.
    """
    def get(self, request):
        try:
            north = float(request.GET['north'])
            south = float(request.GET['south'])
            east = float(request.GET['east'])
            west = float(request.GET['west'])
        except (KeyError, ValueError, TypeError):
            return Response({'error': 'north, south, east, west are required'}, status=400)

        rn, rs, re, rw = _round_bbox(north, south, east, west, snap=0.002)
        bbox_str = f"{rn:.4f},{rs:.4f},{re:.4f},{rw:.4f}"
        cache_key = f"bins:viewport:v3:{hashlib.md5(bbox_str.encode()).hexdigest()}"

        cached = _cache_get(cache_key)
        if cached is not None:
            return Response(cached)

        latest_fill = (
            FillRecord.objects
            .filter(trashcan=OuterRef('pk'))
            .order_by('-timestamp')
            .values('fill_level')[:1]
        )

        bins = list(
            TrashCan.objects
            .filter(
                latitude__gte=south, latitude__lte=north,
                longitude__gte=west, longitude__lte=east,
            )
            .annotate(fill_level=Subquery(latest_fill))
            .values(
                'id', 'latitude', 'longitude',
                'district_id', 'district_name',
                'waste_type', 'bin_status', 'fill_level',
                'public_number', 'capacity_volume', 'bin_count', 'last_cleaned',
                'container_type',
            )[:500]
        )

        features = [
            {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [b['longitude'], b['latitude']]},
                'properties': {
                    'id': b['id'],
                    'fill_level': b['fill_level'],
                    'district_id': b['district_id'],
                    'district_name': b['district_name'],
                    'waste_type': b['waste_type'],
                    'bin_status': b['bin_status'],
                    'public_number': b['public_number'] or '',
                    'capacity_volume': b['capacity_volume'],
                    'bin_count': b['bin_count'],
                    'last_cleaned': b['last_cleaned'].isoformat() if b['last_cleaned'] else None,
                    'container_type': b['container_type'] or '',
                },
            }
            for b in bins
        ]

        result = {'type': 'FeatureCollection', 'features': features}
        _cache_set(cache_key, result, 300)
        return Response(result)


class DistrictsView(APIView):
    """
    GET /api/districts/

    Returns the 24 official districts (district_id 1-24) with bin counts,
    plus overall totals broken down by waste type.
    Cached for 1 hour.
    """
    def get(self, request):
        cache_key = 'bins:districts:v4'
        cached = _cache_get(cache_key)
        if cached is not None:
            return Response(cached)

        # Only the 24 numbered official districts — excludes coloured bins (district_id=None)
        districts_qs = list(
            TrashCan.objects
            .filter(district_id__isnull=False)
            .values('district_id', 'district_name')
            .annotate(
                bin_count=Count('id'),
                active_count=Count('id', filter=Q(bin_status='active')),
                center_lat=Avg('latitude'),
                center_lon=Avg('longitude'),
            )
            .order_by('district_name')
        )

        monitored_map = {
            d['district_id']: d['monitored_count']
            for d in TrashCan.objects
            .filter(fill_records__isnull=False, district_id__isnull=False)
            .values('district_id')
            .annotate(monitored_count=Count('id', distinct=True))
        }

        districts = [
            {
                'district_id': d['district_id'],
                'district_name': d['district_name'],
                'bin_count': d['bin_count'],
                'active_count': d['active_count'],
                'monitored_count': monitored_map.get(d['district_id'], 0),
                'center_lat': round(d['center_lat'], 5) if d['center_lat'] is not None else None,
                'center_lon': round(d['center_lon'], 5) if d['center_lon'] is not None else None,
            }
            for d in districts_qs
        ]

        grey_bins      = TrashCan.objects.filter(waste_type='general').count()
        coloured_bins  = TrashCan.objects.exclude(waste_type='general').count()
        active_bins    = TrashCan.objects.filter(bin_status='active').count()
        monitored_bins = TrashCan.objects.filter(fill_records__isnull=False).distinct().count()

        result = {
            'districts': districts,
            'totals': {
                'grey_bins':     grey_bins,
                'coloured_bins': coloured_bins,
                'active_bins':   active_bins,
                'monitored_bins': monitored_bins,
            },
        }
        _cache_set(cache_key, result, 3600)
        return Response(result)


class DistrictBoundariesView(APIView):
    """
    GET /api/districts/boundaries/
    Returns a GeoJSON FeatureCollection of convex hulls computed from bin coordinates
    per district. Cached for 24 h — changes only when bins are re-synced.
    """
    def get(self, request):
        cache_key = 'bins:district_boundaries:v1'
        cached = _cache_get(cache_key)
        if cached is not None:
            return Response(cached)

        from scipy.spatial import ConvexHull
        import numpy as np

        qs = (
            TrashCan.objects
            .filter(waste_type='general', district_id__isnull=False)
            .values_list('district_id', 'district_name', 'latitude', 'longitude')
        )

        districts: dict[int, dict] = {}
        for district_id, district_name, lat, lon in qs:
            if district_id not in districts:
                districts[district_id] = {'name': district_name, 'pts': []}
            districts[district_id]['pts'].append([lon, lat])

        features = []
        for district_id, info in sorted(districts.items()):
            pts = np.array(info['pts'])
            if len(pts) < 4:
                continue
            try:
                hull = ConvexHull(pts)
                hull_pts = pts[hull.vertices].tolist()
                hull_pts.append(hull_pts[0])  # close ring
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Polygon', 'coordinates': [hull_pts]},
                    'properties': {
                        'district_id': district_id,
                        'name': info['name'],
                    },
                })
            except Exception:
                continue

        result = {'type': 'FeatureCollection', 'features': features}
        _cache_set(cache_key, result, 86400)
        return Response(result)


class BinDetailView(APIView):
    """
    GET /api/bins/<id>/
    Public: single bin with all fields + last 30 fill records (oldest first).
    """
    def get(self, request, bin_id):
        try:
            b = TrashCan.objects.get(id=bin_id)
        except TrashCan.DoesNotExist:
            return Response({'error': 'Bin not found'}, status=404)

        history = list(
            FillRecord.objects
            .filter(trashcan=b)
            .order_by('-timestamp')
            .values('timestamp', 'fill_level', 'source')[:30]
        )
        history.reverse()

        return Response({
            'id': b.id,
            'latitude': b.latitude,
            'longitude': b.longitude,
            'waste_type': b.waste_type,
            'bin_status': b.bin_status,
            'public_number': b.public_number,
            'district_id': b.district_id,
            'district_name': b.district_name,
            'capacity_volume': b.capacity_volume,
            'bin_count': b.bin_count,
            'last_cleaned': b.last_cleaned.isoformat() if b.last_cleaned else None,
            'container_type': b.container_type or '',
            'fill_history': [
                {
                    'timestamp': r['timestamp'].isoformat(),
                    'fill_level': r['fill_level'],
                    'source': r['source'],
                }
                for r in history
            ],
        })
