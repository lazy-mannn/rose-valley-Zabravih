from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from django.utils import timezone

class Command(BaseCommand):
    help = "Reset system - delete all fill records and reset last_emptied dates"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("🔄 Resetting system..."))
        
        # Delete ALL fill records
        deleted_count = FillRecord.objects.all().count()
        FillRecord.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"✓ Deleted {deleted_count} fill records"))
        
        # Reset all bins to "just emptied"
        for can in TrashCan.objects.all():
            can.last_emptied = timezone.now()
            can.save()
            
            # Create initial empty record
            FillRecord.objects.create(
                trashcan=can,
                fill_level=0,
                source='manual'
            )
        
        self.stdout.write(self.style.SUCCESS(f"✓ Reset {TrashCan.objects.count()} bins to empty state"))
        self.stdout.write(self.style.SUCCESS("\n✅ System reset complete! All bins are now empty."))
        