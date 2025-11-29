from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = "Advance time simulation by X days to test predictions"

    def add_arguments(self, parser):
        parser.add_argument(
            'days',
            type=int,
            help='Number of days to advance'
        )

    def handle(self, *args, **options):
        days = options['days']
        
        trash_cans = TrashCan.objects.all()
        
        if not trash_cans.exists():
            self.stdout.write(self.style.ERROR("❌ No trash cans found."))
            return
        
        self.stdout.write(self.style.WARNING(f"\n⏰ Advancing time by {days} day(s)...\n"))
        
        for can in trash_cans:
            daily_rate = can.get_average_daily_fill_rate()
            current_predicted = can.get_predicted_fill_level()
            
            # Calculate new fill after X days
            fill_increase = daily_rate * days
            new_fill = current_predicted + fill_increase
            
            # Add random variance
            variance = random.uniform(-5, 8)
            new_fill += variance
            new_fill = max(0, min(110, new_fill))  # Cap at 110%
            
            # Create record with timestamp in future
            future_time = timezone.now()
            FillRecord.objects.create(
                trashcan=can,
                fill_level=round(new_fill),
                timestamp=future_time,
                source='predicted'
            )
            
            status = "🚨 OVERFLOW" if new_fill > 100 else "⚠️ FULL" if new_fill >= 80 else "⚡ HIGH" if new_fill >= 60 else "✓ OK"
            
            self.stdout.write(
                f"Bin {can.id}: {current_predicted:.1f}% → {new_fill:.1f}% {status}"
            )
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Advanced {days} day(s)! Run update_predictions to recalculate."))