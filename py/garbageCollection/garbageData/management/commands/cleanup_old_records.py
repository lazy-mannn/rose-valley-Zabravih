from django.core.management.base import BaseCommand
from garbageData.models import FillRecord
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = "Clean up old fill records to prevent database bloat"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Keep records from last N days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get records to delete
        old_records = FillRecord.objects.filter(timestamp__lt=cutoff_date)
        total_count = old_records.count()
        
        # Breakdown by source
        manual_count = old_records.filter(source='manual').count()
        ai_count = old_records.filter(source='ai').count()
        predicted_count = old_records.filter(source='predicted').count()
        
        self.stdout.write(self.style.WARNING("\n" + "="*70))
        self.stdout.write(self.style.WARNING("🧹 DATABASE CLEANUP"))
        self.stdout.write(self.style.WARNING("="*70 + "\n"))
        
        self.stdout.write(f"Cutoff Date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write(f"Records to delete: {total_count}")
        self.stdout.write(f"  • Manual: {manual_count}")
        self.stdout.write(f"  • AI: {ai_count}")
        self.stdout.write(f"  • Predicted: {predicted_count}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN - No records deleted"))
        else:
            if total_count > 0:
                confirm = input(f"\n⚠️  Delete {total_count} records older than {days} days? (yes/no): ")
                if confirm.lower() == 'yes':
                    deleted_count, _ = old_records.delete()
                    self.stdout.write(self.style.SUCCESS(f"\n✅ Deleted {deleted_count} old records"))
                else:
                    self.stdout.write(self.style.WARNING("\n❌ Cleanup cancelled"))
            else:
                self.stdout.write(self.style.SUCCESS("\n✅ No old records to delete"))
        
        # Show current database stats
        total_remaining = FillRecord.objects.count()
        self.stdout.write(f"\n📊 Current database size: {total_remaining} records")
        self.stdout.write(self.style.SUCCESS("="*70 + "\n"))