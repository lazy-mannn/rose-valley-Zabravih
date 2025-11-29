from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from datetime import datetime, timedelta
from django.utils import timezone
import random

class Command(BaseCommand):
    help = "Create 250 trash cans in Kazanlak city center with truck-accessible locations"

    def handle(self, *args, **options):
        # Kazanlak city center - truck-accessible areas only
        # Center: 42.6197, 25.3954
        
        self.stdout.write(self.style.WARNING("\n🗑️  Generating 250 trash bins in Kazanlak city center..."))
        self.stdout.write("")
        
        # --- Original 50 trash cans (keep exact locations) ---
        trash_cans_data = [
            (1, 42.62157187091345, 25.39428178312431),
            (2, 42.62047193601686, 25.395088604816188),
            (3, 42.62180812323232, 25.393416769763647),
            (4, 42.62234191611349, 25.39648177079153),
            (5, 42.62337715947338, 25.393733907311518),
            (6, 42.624641655959415, 25.392957120001345),
            (7, 42.62089123456789, 25.39512345678901),
            (8, 42.62298765432109, 25.39456789012345),
            (9, 42.62412345678901, 25.39389012345678),
            (10, 42.62156789012345, 25.39567890123456),
            (11, 42.6205, 25.3940),
            (12, 42.6220, 25.3965),
            (13, 42.6235, 25.3945),
            (14, 42.6215, 25.3980),
            (15, 42.6240, 25.3950),
            (16, 42.6210, 25.3925),
            (17, 42.6225, 25.3935),
            (18, 42.6250, 25.3960),
            (19, 42.6195, 25.3955),
            (20, 42.6230, 25.3920),
            (21, 42.6208, 25.3948),
            (22, 42.6245, 25.3938),
            (23, 42.6218, 25.3970),
            (24, 42.6232, 25.3930),
            (25, 42.6212, 25.3943),
            (26, 42.6238, 25.3958),
            (27, 42.6222, 25.3953),
            (28, 42.6248, 25.3968),
            (29, 42.6202, 25.3933),
            (30, 42.6228, 25.3963),
            (31, 42.6214, 25.3928),
            (32, 42.6242, 25.3973),
            (33, 42.6206, 25.3978),
            (34, 42.6236, 25.3923),
            (35, 42.6224, 25.3948),
            (36, 42.6252, 25.3943),
            (37, 42.6198, 25.3938),
            (38, 42.6246, 25.3953),
            (39, 42.6216, 25.3968),
            (40, 42.6234, 25.3933),
            (41, 42.6204, 25.3963),
            (42, 42.6244, 25.3928),
            (43, 42.6226, 25.3958),
            (44, 42.6200, 25.3973),
            (45, 42.6240, 25.3983),
            (46, 42.6220, 25.3918),
            (47, 42.6254, 25.3948),
            (48, 42.6210, 25.3953),
            (49, 42.6230, 25.3938),
            (50, 42.6196, 25.3968),
        ]
        
        # --- Define truck-accessible zones in Kazanlak city center ---
        # These are main streets, residential areas, and commercial zones
        # Excludes: Tyulbeto Park (west), Rose Museum area (center park), hills
        
        accessible_zones = [
            # Zone 1: Northern residential area (near bus station)
            {'lat_min': 42.6250, 'lat_max': 42.6280, 'lon_min': 25.3920, 'lon_max': 25.3980, 'density': 25},
            
            # Zone 2: Central business district (around pl. Sevtopolis)
            {'lat_min': 42.6210, 'lat_max': 42.6245, 'lon_min': 25.3930, 'lon_max': 25.3975, 'density': 35},
            
            # Zone 3: Southern residential (near stadium)
            {'lat_min': 42.6170, 'lat_max': 42.6210, 'lon_min': 25.3925, 'lon_max': 25.3970, 'density': 30},
            
            # Zone 4: Eastern residential area
            {'lat_min': 42.6200, 'lat_max': 42.6250, 'lon_min': 25.3975, 'lon_max': 25.4020, 'density': 25},
            
            # Zone 5: Western commercial area (avoiding Tyulbeto Park)
            {'lat_min': 42.6200, 'lat_max': 42.6240, 'lon_min': 25.3880, 'lon_max': 25.3925, 'density': 20},
            
            # Zone 6: Industrial area (east)
            {'lat_min': 42.6180, 'lat_max': 42.6220, 'lon_min': 25.4020, 'lon_max': 25.4060, 'density': 15},
            
            # Zone 7: Market area (southeast)
            {'lat_min': 42.6150, 'lat_max': 42.6180, 'lon_min': 25.3950, 'lon_max': 25.4000, 'density': 20},
            
            # Zone 8: Hospital area (northwest)
            {'lat_min': 42.6255, 'lat_max': 42.6275, 'lon_min': 25.3880, 'lon_max': 25.3920, 'density': 10},
        ]
        
        # Park exclusion zones (no bins here - trucks can't access)
        park_exclusions = [
            # Tyulbeto Park (west)
            {'lat_min': 42.6190, 'lat_max': 42.6250, 'lon_min': 25.3850, 'lon_max': 25.3885},
            
            # Rose Museum park area (center)
            {'lat_min': 42.6220, 'lat_max': 42.6240, 'lon_min': 25.3955, 'lon_max': 25.3975},
            
            # Rozarium Park (north)
            {'lat_min': 42.6270, 'lat_max': 42.6290, 'lon_min': 25.3940, 'lon_max': 25.3970},
        ]
        
        def is_in_park(lat, lon):
            """Check if coordinates are inside a park exclusion zone"""
            for park in park_exclusions:
                if (park['lat_min'] <= lat <= park['lat_max'] and 
                    park['lon_min'] <= lon <= park['lon_max']):
                    return True
            return False
        
        # --- Generate 200 more bins (51-250) in accessible zones ---
        bin_id = 51
        attempts = 0
        max_attempts = 5000  # Prevent infinite loop
        
        while bin_id <= 250 and attempts < max_attempts:
            attempts += 1
            
            # Select random zone based on density
            zone_weights = [z['density'] for z in accessible_zones]
            zone = random.choices(accessible_zones, weights=zone_weights)[0]
            
            # Generate random position within zone
            lat = random.uniform(zone['lat_min'], zone['lat_max'])
            lon = random.uniform(zone['lon_min'], zone['lon_max'])
            
            # Skip if in park
            if is_in_park(lat, lon):
                continue
            
            # Check if too close to existing bins (minimum 20 meters apart)
            too_close = False
            for existing_id, existing_lat, existing_lon in trash_cans_data:
                # Rough distance check (1 degree ≈ 111km)
                # 20 meters ≈ 0.00018 degrees
                lat_diff = abs(lat - existing_lat)
                lon_diff = abs(lon - existing_lon)
                distance_approx = ((lat_diff ** 2) + (lon_diff ** 2)) ** 0.5
                
                if distance_approx < 0.00018:  # ~20 meters
                    too_close = True
                    break
            
            if too_close:
                continue
            
            # Add bin
            trash_cans_data.append((bin_id, lat, lon))
            bin_id += 1
            
            # Progress indicator
            if bin_id % 50 == 0:
                self.stdout.write(f"   Generated {bin_id} bins...")
        
        if bin_id <= 250:
            self.stdout.write(self.style.WARNING(
                f"   ⚠️  Only generated {bin_id - 1} bins (some zones too dense)"
            ))
        
        # Create all bins
        created_count = 0
        updated_count = 0
        
        for trash_id, lat, lon in trash_cans_data:
            # Create or get TrashCan
            tc, created = TrashCan.objects.get_or_create(
                id=trash_id,
                defaults={
                    'latitude': lat,
                    'longitude': lon,
                    'last_emptied': timezone.now()
                }
            )
            
            if created:
                created_count += 1
                
                # Create initial empty record
                FillRecord.objects.create(
                    trashcan=tc,
                    fill_level=0,
                    timestamp=timezone.now(),
                    source='manual'
                )
            else:
                updated_count += 1
                # Update location if different
                if tc.latitude != lat or tc.longitude != lon:
                    tc.latitude = lat
                    tc.longitude = lon
                    tc.save()
        
        # Summary by zone
        self.stdout.write(self.style.SUCCESS(f"\n✅ Bin Creation Complete!"))
        self.stdout.write(f"   • Created: {created_count} new bins")
        if updated_count > 0:
            self.stdout.write(self.style.WARNING(f"   • Existing: {updated_count} bins already exist"))
        self.stdout.write(f"   • Total: {len(trash_cans_data)} bins in Kazanlak city center")
        
        # Count bins per zone
        self.stdout.write(f"\n📍 Distribution by zone:")
        for idx, zone in enumerate(accessible_zones, 1):
            count = sum(1 for _, lat, lon in trash_cans_data 
                       if zone['lat_min'] <= lat <= zone['lat_max'] and 
                          zone['lon_min'] <= lon <= zone['lon_max'])
            zone_name = [
                "Northern residential (bus station)",
                "Central business district (Sevtopolis)",
                "Southern residential (stadium)",
                "Eastern residential",
                "Western commercial",
                "Industrial area",
                "Market area",
                "Hospital area"
            ][idx - 1]
            self.stdout.write(f"   Zone {idx} ({zone_name}): {count} bins")
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("💡 Next steps:"))
        self.stdout.write("   1. Run: python manage.py generate_realistic_data --high-fill")
        self.stdout.write("   2. Run: python manage.py update_predictions")
        self.stdout.write("")
