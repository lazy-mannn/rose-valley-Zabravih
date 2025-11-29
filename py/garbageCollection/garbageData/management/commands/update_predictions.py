from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from django.utils import timezone

class Command(BaseCommand):
    help = "Update predicted fill levels for all trash cans (run daily via cron)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"🔄 Updating predictions at {timezone.now()}"))
        
        trash_cans = TrashCan.objects.all()
        
        for can in trash_cans:
            predicted_fill = can.get_predicted_fill_level()
            daily_rate = can.get_average_daily_fill_rate()
            days_until_full = can.get_days_until_full()
            
            # Create predicted fill record
            FillRecord.objects.create(
                trashcan=can,
                fill_level=round(predicted_fill),
                source='predicted'
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Bin {can.id}: {predicted_fill:.1f}% "
                    f"(+{daily_rate:.1f}%/day, {days_until_full:.1f} days until full)"
                )
            )
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Updated predictions for {trash_cans.count()} bins!"))