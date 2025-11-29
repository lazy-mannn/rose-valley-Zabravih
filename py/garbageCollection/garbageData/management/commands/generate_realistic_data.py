from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from datetime import datetime, timedelta
from django.utils import timezone
import random

class Command(BaseCommand):
    help = "Generate realistic training data with proper collection patterns and timing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to simulate (default: 30)'
        )
        parser.add_argument(
            '--high-fill',
            action='store_true',
            help='Generate more full bins for route testing'
        )

    def handle(self, *args, **options):
        days_to_simulate = options['days']
        high_fill_mode = options['high_fill']
        
        trash_cans = TrashCan.objects.all()
        
        if not trash_cans.exists():
            self.stdout.write(self.style.ERROR("❌ No trash cans found. Run 'python manage.py initialfill' first."))
            return
        
        self.stdout.write(self.style.WARNING(f"\n🔄 Generating realistic data for {trash_cans.count()} bins..."))
        self.stdout.write(f"   Simulating {days_to_simulate} days")
        if high_fill_mode:
            self.stdout.write(self.style.WARNING("   🔥 HIGH FILL MODE: More bins will be near full for route testing"))
        self.stdout.write("")
        
        # Delete old records
        deleted_count = FillRecord.objects.all().delete()[0]
        if deleted_count > 0:
            self.stdout.write(f"   Deleted {deleted_count} old records\n")
        
        total_collections = 0
        
        # Generate data for each bin
        for can in trash_cans:
            # Each bin has different characteristics based on location type
            # Fast-filling: restaurants, busy areas (15-25%/day)
            # Medium-filling: residential, parks (8-15%/day)
            # Slow-filling: quiet areas (5-10%/day)
            
            bin_types = ['fast', 'medium', 'slow']
            weights = [0.3, 0.5, 0.2] if not high_fill_mode else [0.6, 0.3, 0.1]  # More fast bins in high-fill mode
            bin_type = random.choices(bin_types, weights=weights)[0]
            
            if bin_type == 'fast':
                base_daily_rate = random.uniform(15, 25)
                variance = random.uniform(3, 6)
            elif bin_type == 'medium':
                base_daily_rate = random.uniform(8, 15)
                variance = random.uniform(2, 4)
            else:  # slow
                base_daily_rate = random.uniform(5, 10)
                variance = random.uniform(1, 3)
            
            # In high-fill mode, boost all rates by 20-40%
            if high_fill_mode:
                boost = random.uniform(1.2, 1.4)
                base_daily_rate *= boost
            
            # Start simulation from X days ago
            start_time = timezone.now() - timedelta(days=days_to_simulate)
            current_time = start_time
            current_fill = 0  # Start empty
            
            # Set last_emptied to start time
            can.last_emptied = current_time
            can.save()
            
            # Create initial empty record
            FillRecord.objects.create(
                trashcan=can,
                fill_level=0,
                timestamp=current_time,
                source='manual'
            )
            
            self.stdout.write(f"📦 Bin {can.id}: {bin_type.upper()} fill rate ({base_daily_rate:.1f}%/day)")
            
            bin_collections = 0
            last_collection_time = current_time
            
            # Simulate days
            while current_time < timezone.now():
                # Calculate time-based fill increase
                hours_passed = 6  # Check every 6 hours
                daily_rate_with_variance = base_daily_rate + random.uniform(-variance, variance)
                fill_increase = max(0, (daily_rate_with_variance / 24) * hours_passed)
                
                current_fill += fill_increase
                
                # Add random events (people dumping extra trash, wind scatter, etc.)
                if random.random() < 0.1:  # 10% chance of event
                    event_change = random.uniform(-5, 10)  # Usually adds trash
                    current_fill += event_change
                    if abs(event_change) > 3:
                        event_type = "🎉 Extra trash" if event_change > 0 else "🍃 Wind scatter"
                
                current_fill = max(0, current_fill)  # Can't be negative
                
                # Move time forward
                current_time += timedelta(hours=hours_passed)
                
                # Check if bin needs collection (80-110% full)
                if current_fill >= random.uniform(80, 105):
                    # Determine if overflow
                    is_overflow = current_fill > 100
                    recorded_fill = min(round(current_fill), 110)
                    
                    # Simulate collection timing: bins are collected in routes
                    # Collections happen 2-3 minutes apart on average
                    if bin_collections > 0:
                        minutes_since_last = (current_time - last_collection_time).total_seconds() / 60
                        if minutes_since_last < 2:
                            # Adjust time to be 2-3 minutes after last collection
                            current_time = last_collection_time + timedelta(minutes=random.uniform(2, 3))
                    
                    # Record fill level BEFORE collection (what AI sees)
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=recorded_fill,
                        timestamp=current_time,
                        source='ai'
                    )
                    
                    days_since_start = (current_time - start_time).days
                    overflow_marker = " 🚨 OVERFLOW" if is_overflow else ""
                    self.stdout.write(
                        f"   ├─ Day {days_since_start}: Collected at {recorded_fill}%{overflow_marker}"
                    )
                    
                    # Bin is emptied (happens RIGHT after photo)
                    current_fill = 0
                    can.last_emptied = current_time
                    can.save()
                    
                    # Record empty state immediately after collection
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=0,
                        timestamp=current_time + timedelta(seconds=5),  # 5 seconds after photo
                        source='manual'
                    )
                    
                    bin_collections += 1
                    total_collections += 1
                    last_collection_time = current_time
                
                # Occasional monitoring records (not every time)
                elif random.random() < 0.15:  # 15% chance
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=min(round(current_fill), 110),
                        timestamp=current_time,
                        source='predicted'
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"   ✓ Bin {can.id}: {bin_collections} collections over {days_to_simulate} days "
                    f"(avg every {days_to_simulate/max(1, bin_collections):.1f} days)\n"
                )
            )
        
        # Summary statistics
        total_records = FillRecord.objects.count()
        ai_records = FillRecord.objects.filter(source='ai').count()
        
        # Calculate how many bins are currently full for route testing
        full_bins = 0
        near_full_bins = 0
        for can in trash_cans:
            predicted = can.get_predicted_fill_level()
            if predicted >= 80:
                full_bins += 1
            elif predicted >= 60:
                near_full_bins += 1
        
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(f"✅ Data Generation Complete!\n"))
        self.stdout.write(f"📊 Statistics:")
        self.stdout.write(f"   • Total records created: {total_records}")
        self.stdout.write(f"   • AI collection events: {ai_records}")
        self.stdout.write(f"   • Total collections: {total_collections}")
        self.stdout.write(f"   • Days simulated: {days_to_simulate}")
        self.stdout.write(f"   • Avg collections/day: {total_collections/days_to_simulate:.1f}")
        self.stdout.write("")
        self.stdout.write(f"🗑️  Current Status (for route testing):")
        self.stdout.write(self.style.ERROR(f"   • Full bins (≥80%): {full_bins}"))
        self.stdout.write(self.style.WARNING(f"   • Near full (≥60%): {near_full_bins}"))
        self.stdout.write(f"   • Total bins needing collection: {full_bins + near_full_bins}")
        self.stdout.write("")
        
        if high_fill_mode:
            self.stdout.write(self.style.SUCCESS("🔥 High fill mode complete! Routes should be well-populated for testing."))
        else:
            self.stdout.write(self.style.WARNING("💡 Tip: Use --high-fill flag to generate more full bins for route testing"))
        
        self.stdout.write(self.style.SUCCESS("=" * 70))