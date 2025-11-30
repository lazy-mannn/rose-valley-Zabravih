from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = "Generate realistic historical fill data with proper time progression"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7, help='Days of history (default: 7)')
        parser.add_argument('--fast', action='store_true', help='Faster fill rates (5-7 day cycles)')
        parser.add_argument('--slow', action='store_true', help='Slower fill rates (10-14 day cycles)')
        parser.add_argument('--hourly', action='store_true', help='Generate hourly readings (more data points)')
        parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD), default: 7 days ago')

    def handle(self, *args, **options):
        days = options['days']
        fast_mode = options['fast']
        slow_mode = options['slow']
        hourly_mode = options['hourly']
        start_date_str = options.get('start_date')
        
        # Determine fill speed
        if fast_mode:
            min_cycle, max_cycle = 5, 7
            mode_name = "FAST"
        elif slow_mode:
            min_cycle, max_cycle = 10, 14
            mode_name = "SLOW"
        else:
            min_cycle, max_cycle = 7, 10
            mode_name = "NORMAL"
        
        # Parse start date if provided
        now = timezone.now()
        if start_date_str:
            from datetime import datetime
            try:
                start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
                # Adjust 'now' to be start_date + days
                now = start_date + timedelta(days=days)
            except ValueError:
                self.stdout.write(self.style.ERROR("❌ Invalid date format. Use YYYY-MM-DD"))
                return
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS(f"🗑️  GENERATING REALISTIC DATA ({mode_name} MODE)"))
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))
        self.stdout.write(f"📅 Period: {days} days")
        
        start_time = now - timedelta(days=days)
        self.stdout.write(f"📆 Start: {start_time.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"📆 End:   {now.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"⏱️  Fill cycle: {min_cycle}-{max_cycle} days to reach 85-95%")
        
        if hourly_mode:
            self.stdout.write(f"🕐 Mode: Hourly readings (24 readings/day)")
        else:
            self.stdout.write(f"🕐 Mode: Daily readings with random hours")
        
        self.stdout.write("")
        
        trash_cans = TrashCan.objects.all()
        if not trash_cans:
            self.stdout.write(self.style.ERROR("❌ No bins found. Run: python manage.py initialfill"))
            return
        
        total_records = 0
        total_collections = 0
        
        for idx, can in enumerate(trash_cans):
            # Each bin gets unique cycle duration
            days_to_full = random.uniform(min_cycle, max_cycle)
            fill_rate_per_day = random.uniform(85, 95) / days_to_full
            fill_rate_per_hour = fill_rate_per_day / 24
            
            # Start simulation from X days ago
            current_time = start_time
            current_fill = 0
            bin_collections = 0
            bin_records = 0
            
            # Determine time increment
            if hourly_mode:
                time_increment = timedelta(hours=1)
                increment_fill = fill_rate_per_hour * random.uniform(0.9, 1.1)
            else:
                time_increment = timedelta(days=1)
                increment_fill = fill_rate_per_day * random.uniform(0.8, 1.2)
            
            while current_time < now:
                # Add time-based fill increment
                if hourly_mode:
                    # Hourly: consistent small increases with slight variance
                    daily_increase = fill_rate_per_hour * random.uniform(0.95, 1.05)
                else:
                    # Daily: larger variance, random hour of day
                    daily_increase = fill_rate_per_day * random.uniform(0.8, 1.2)
                
                current_fill += daily_increase
                current_fill = max(0, current_fill)
                
                # Check if needs collection (85-105% threshold)
                if current_fill >= random.uniform(85, 105):
                    # Record "before collection" level at current time
                    collection_hour = random.randint(6, 22)  # Collections happen 6am-10pm
                    collection_minute = random.randint(0, 59)
                    
                    pre_collection_time = current_time.replace(
                        hour=collection_hour, 
                        minute=collection_minute, 
                        second=0
                    )
                    
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=min(int(current_fill), 110),
                        timestamp=pre_collection_time,
                        source='ai'
                    )
                    bin_records += 1
                    
                    # Collection happens 15 minutes to 4 hours later
                    collection_delay = random.uniform(0.25, 4)  # 15min to 4 hours
                    post_collection_time = pre_collection_time + timedelta(hours=collection_delay)
                    
                    # Record "after collection" (empty)
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=0,
                        timestamp=post_collection_time,
                        source='ai'
                    )
                    bin_records += 1
                    bin_collections += 1
                    
                    # Update bin's last_emptied
                    can.last_emptied = post_collection_time
                    can.save()
                    
                    # Reset fill
                    current_fill = 0
                    current_time = post_collection_time
                else:
                    # Occasionally create intermediate readings (sensors check randomly)
                    if hourly_mode:
                        # In hourly mode, record every few hours
                        if random.random() < 0.15:  # 15% of hours
                            FillRecord.objects.create(
                                trashcan=can,
                                fill_level=int(current_fill),
                                timestamp=current_time,
                                source='ai'
                            )
                            bin_records += 1
                    else:
                        # In daily mode, add some readings with random hours
                        if random.random() < 0.25:  # 25% of days
                            random_hour = random.randint(0, 23)
                            random_minute = random.randint(0, 59)
                            reading_time = current_time.replace(
                                hour=random_hour,
                                minute=random_minute,
                                second=0
                            )
                            
                            FillRecord.objects.create(
                                trashcan=can,
                                fill_level=int(current_fill),
                                timestamp=reading_time,
                                source='ai'
                            )
                            bin_records += 1
                
                # Advance time
                current_time += time_increment
            
            # Final record at current time with random hour
            final_hour = random.randint(0, 23)
            final_minute = random.randint(0, 59)
            final_time = now.replace(hour=final_hour, minute=final_minute, second=0)
            
            FillRecord.objects.create(
                trashcan=can,
                fill_level=int(min(current_fill, 110)),
                timestamp=final_time,
                source='predicted'
            )
            bin_records += 1
            
            total_records += bin_records
            total_collections += bin_collections
            
            # Progress indicator every 50 bins
            if (idx + 1) % 50 == 0:
                self.stdout.write(f"   ✓ Processed {idx + 1}/{trash_cans.count()} bins...")
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{'='*70}"))
        self.stdout.write(self.style.SUCCESS(f"✅ GENERATION COMPLETE!\n"))
        self.stdout.write(f"📊 Statistics:")
        self.stdout.write(f"   • Bins: {trash_cans.count()}")
        self.stdout.write(f"   • Total Records: {total_records:,}")
        self.stdout.write(f"   • Collections: {total_collections}")
        self.stdout.write(f"   • Avg records/bin: {total_records/trash_cans.count():.1f}")
        self.stdout.write(f"   • Avg collections/bin: {total_collections/trash_cans.count():.1f}")
        
        if hourly_mode:
            hours_simulated = days * 24
            self.stdout.write(f"   • Time resolution: Hourly ({hours_simulated} hours)")
        else:
            self.stdout.write(f"   • Time resolution: Daily with varied hours")
        
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("📌 Next Steps:"))
        self.stdout.write("   1. python manage.py update_predictions")
        self.stdout.write("   2. Refresh dashboard to see routes!")
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))