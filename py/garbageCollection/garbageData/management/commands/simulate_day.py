from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from django.utils import timezone
import random

class Command(BaseCommand):
    help = "Simulate 1 day passing - bins fill up gradually with random events"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=1, help='Days to simulate')
        parser.add_argument('--spikes', action='store_true', help='Add random spike events')

    def handle(self, *args, **options):
        days = options['days']
        add_spikes = options['spikes']
        
        self.stdout.write(self.style.WARNING(f"\n⏰ Simulating {days} day(s) passing..."))
        if add_spikes:
            self.stdout.write(self.style.WARNING("🎲 Random spike events enabled!\n"))
        
        stats = {
            'collected': 0,
            'overflow': 0,
            'high': 0,
            'normal': 0,
            'spike_events': 0
        }
        
        # Select bins for spike events
        spike_bins = set()
        if add_spikes:
            all_bins = list(TrashCan.objects.all())
            num_spikes = max(1, int(len(all_bins) * 0.05))
            spike_bins = set(random.sample(all_bins, num_spikes))
        
        for can in TrashCan.objects.all():
            current = can.get_predicted_fill_level()
            rate = can.get_average_daily_fill_rate()
            
            # Check for spike event
            if can in spike_bins:
                event_types = [
                    ('🏗️ Construction', 3.0, 4.0),
                    ('🎉 Party', 2.5, 3.5),
                    ('📦 Moving Day', 2.0, 3.0),
                ]
                event_name, min_mult, max_mult = random.choice(event_types)
                multiplier = random.uniform(min_mult, max_mult)
                increase = rate * days * multiplier
                stats['spike_events'] += 1
                self.stdout.write(self.style.WARNING(
                    f"   {event_name} at Bin {can.id}! ({multiplier:.1f}× normal rate)"
                ))
            else:
                increase = rate * days * random.uniform(0.85, 1.15)
            
            new_fill = current + increase
            new_fill = max(0, min(110, new_fill))
            
            # Simulate collection if full
            if new_fill >= random.uniform(85, 100):
                # ✅ CORRECT: Record fill level THEN empty
                FillRecord.objects.create(
                    trashcan=can,
                    fill_level=int(new_fill),
                    timestamp=timezone.now(),
                    source='ai'
                )
                can.mark_as_emptied()  # Creates 0% record after
                
                stats['collected'] += 1
                status = "🚛 COLLECTED"
                color = self.style.SUCCESS
            else:
                # Just update fill level
                FillRecord.objects.create(
                    trashcan=can,
                    fill_level=int(new_fill),
                    timestamp=timezone.now(),
                    source='predicted'
                )
                
                if new_fill >= 100:
                    stats['overflow'] += 1
                    status = "🚨 OVERFLOW"
                    color = self.style.ERROR
                elif new_fill >= 70:
                    stats['high'] += 1
                    status = "⚠️ HIGH"
                    color = self.style.WARNING
                else:
                    stats['normal'] += 1
                    status = "✓ OK"
                    color = self.style.SUCCESS
            
            self.stdout.write(color(f"Bin {can.id:3d}: {current:5.1f}% → {new_fill:5.1f}% {status}"))
        
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{'='*70}"))
        self.stdout.write(self.style.SUCCESS(f"✅ Simulated {days} day(s)!\n"))
        self.stdout.write(f"📊 Results:")
        self.stdout.write(f"   🚛 Collected: {stats['collected']}")
        self.stdout.write(f"   🚨 Overflow: {stats['overflow']}")
        self.stdout.write(f"   ⚠️  High: {stats['high']}")
        self.stdout.write(f"   ✓ Normal: {stats['normal']}")
        if add_spikes:
            self.stdout.write(f"   🎲 Spike Events: {stats['spike_events']}")
        self.stdout.write(self.style.SUCCESS(f"{'='*70}\n"))
