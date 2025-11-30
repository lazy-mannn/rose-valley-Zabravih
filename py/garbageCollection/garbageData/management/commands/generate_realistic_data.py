from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = "Generate realistic historical fill data with spike events for demo"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14, help='Days of history (default: 14)')
        parser.add_argument('--spikes', action='store_true', help='Add random spike events')
        parser.add_argument('--demo', action='store_true', help='Demo mode: guaranteed visible spikes')

    def handle(self, *args, **options):
        days = options['days']
        add_spikes = options['spikes']
        demo_mode = options['demo']
        
        if demo_mode:
            add_spikes = True
        
        self.stdout.write(self.style.SUCCESS(f"\n{'='*70}"))
        self.stdout.write(self.style.SUCCESS(f"🗑️  GENERATING REALISTIC DATA"))
        if demo_mode:
            self.stdout.write(self.style.WARNING(f"📊 DEMO MODE: Guaranteed spike events for presentation"))
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))
        self.stdout.write(f"📅 Period: {days} days")
        
        now = timezone.now()
        start_time = now - timedelta(days=days)
        
        self.stdout.write(f"📆 Start: {start_time.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"📆 End:   {now.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write("")
        
        trash_cans = list(TrashCan.objects.all())
        if not trash_cans:
            self.stdout.write(self.style.ERROR("❌ No bins found. Run: python manage.py initialfill"))
            return
        
        # Select bins for spike events
        spike_schedule = {}
        if add_spikes:
            if demo_mode:
                # Demo: Select 10% of bins, schedule spikes at specific days
                num_spike_bins = max(5, int(len(trash_cans) * 0.10))
                spike_bins = random.sample(trash_cans, num_spike_bins)
                
                for bin in spike_bins:
                    # Schedule spike 3-5 days ago (so we can see recovery)
                    spike_day = random.randint(max(3, days-10), days-3)
                    spike_duration = random.randint(1, 2)  # 1-2 days
                    spike_schedule[bin.id] = (spike_day, spike_duration)
                
                self.stdout.write(self.style.WARNING(
                    f"📊 {len(spike_bins)} bins will have spike events for demo"
                ))
            else:
                # Normal: Random 5% of bins
                num_spike_bins = max(1, int(len(trash_cans) * 0.05))
                spike_bins = random.sample(trash_cans, num_spike_bins)
                
                for bin in spike_bins:
                    spike_day = random.randint(2, days-2)
                    spike_duration = random.randint(1, 3)
                    spike_schedule[bin.id] = (spike_day, spike_duration)
        
        self.stdout.write("")
        
        total_records = 0
        total_collections = 0
        total_spikes = 0
        
        for idx, can in enumerate(trash_cans):
            # Normal fill rate
            days_to_full = random.uniform(7, 10)
            base_fill_rate = random.uniform(85, 95) / days_to_full
            
            current_time = start_time
            current_fill = 0
            bin_collections = 0
            bin_records = 0
            
            # Check if this bin has scheduled spike
            has_spike = can.id in spike_schedule
            if has_spike:
                spike_start_day, spike_duration = spike_schedule[can.id]
            
            day_counter = 0
            
            while current_time < now:
                day_counter += 1
                
                # Check if in spike period
                in_spike = False
                if has_spike and spike_start_day <= day_counter < (spike_start_day + spike_duration):
                    in_spike = True
                    daily_increase = base_fill_rate * random.uniform(2.5, 4.0)  # 2.5-4× normal
                    if day_counter == spike_start_day:
                        total_spikes += 1
                else:
                    daily_increase = base_fill_rate * random.uniform(0.8, 1.2)
                
                current_fill += daily_increase
                current_fill = max(0, current_fill)
                
                # Check if needs collection
                if current_fill >= random.uniform(85, 105):
                    collection_hour = random.randint(6, 22)
                    collection_minute = random.randint(0, 59)
                    
                    pre_collection_time = current_time.replace(
                        hour=collection_hour, 
                        minute=collection_minute, 
                        second=0
                    )
                    
                    # Record before collection
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=min(int(current_fill), 110),
                        timestamp=pre_collection_time,
                        source='ai'
                    )
                    bin_records += 1
                    
                    # Collection delay
                    post_collection_time = pre_collection_time + timedelta(hours=random.uniform(0.25, 4))
                    
                    # Record after collection (empty)
                    FillRecord.objects.create(
                        trashcan=can,
                        fill_level=0,
                        timestamp=post_collection_time,
                        source='ai'
                    )
                    bin_records += 1
                    bin_collections += 1
                    
                    # Update bin
                    can.last_emptied = post_collection_time
                    can.save()
                    
                    current_fill = 0
                    current_time = post_collection_time
                else:
                    # Occasional intermediate readings
                    if random.random() < 0.2:
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
                
                current_time += timedelta(days=1)
            
            # Final record
            final_time = now.replace(
                hour=random.randint(0, 23),
                minute=random.randint(0, 59),
                second=0
            )
            
            FillRecord.objects.create(
                trashcan=can,
                fill_level=int(min(current_fill, 110)),
                timestamp=final_time,
                source='predicted'
            )
            bin_records += 1
            
            total_records += bin_records
            total_collections += bin_collections
            
            if (idx + 1) % 50 == 0:
                self.stdout.write(f"   ✓ Processed {idx + 1}/{len(trash_cans)} bins...")
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{'='*70}"))
        self.stdout.write(self.style.SUCCESS(f"✅ GENERATION COMPLETE!\n"))
        self.stdout.write(f"📊 Statistics:")
        self.stdout.write(f"   • Bins: {len(trash_cans)}")
        self.stdout.write(f"   • Total Records: {total_records:,}")
        self.stdout.write(f"   • Collections: {total_collections}")
        if add_spikes:
            self.stdout.write(f"   • Spike Events: {total_spikes}")
        self.stdout.write(f"   • Avg records/bin: {total_records/len(trash_cans):.1f}")
        self.stdout.write(f"   • Avg collections/bin: {total_collections/len(trash_cans):.1f}")
        
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("📌 Next Steps:"))
        self.stdout.write("   1. python manage.py update_predictions")
        if demo_mode:
            self.stdout.write(self.style.SUCCESS("   2. Check dashboard - you'll see spike recovery in action!"))
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))