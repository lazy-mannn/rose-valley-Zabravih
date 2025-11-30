from django.core.management.base import BaseCommand
from django.utils import timezone
from garbageData.models import TrashCan

class Command(BaseCommand):
    help = "Reset all bins to current time (undo simulate_day)"

    def handle(self, *args, **options):
        now = timezone.now()
        
        bins = TrashCan.objects.all()
        total = bins.count()
        
        self.stdout.write(f"\n⏰ Resetting {total} bins to current time...\n")
        
        for bin in bins:
            old_time = bin.last_emptied
            days_ago = (now - old_time).days
            
            # Reset to now
            bin.last_emptied = now
            bin.save()
            
            if days_ago > 7:
                self.stdout.write(
                    f"   Bin {bin.id}: was {days_ago} days old → reset to NOW"
                )
        
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ All bins reset to {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        ))