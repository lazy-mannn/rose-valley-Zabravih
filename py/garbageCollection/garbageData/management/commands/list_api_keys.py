from django.core.management.base import BaseCommand
from garbageData.models import APIKey

class Command(BaseCommand):
    help = "List all API keys"

    def handle(self, *args, **options):
        keys = APIKey.objects.all().order_by('-created_at')
        
        if not keys:
            self.stdout.write(self.style.WARNING("\n📋 No API keys found\n"))
            self.stdout.write("Create one with: python manage.py create_api_key <device_name>\n")
            return
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*90))
        self.stdout.write(self.style.SUCCESS("📋 API KEYS"))
        self.stdout.write(self.style.SUCCESS("="*90 + "\n"))
        
        for key in keys:
            status = "✅ Active" if key.is_active else "❌ Inactive"
            last_used = key.last_used.strftime('%Y-%m-%d %H:%M') if key.last_used else "Never"
            
            self.stdout.write(f"Device: {key.device_name}")
            self.stdout.write(f"Status: {status}")
            self.stdout.write(f"Created: {key.created_at.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"Last Used: {last_used}")
            self.stdout.write(f"Key: {key.key[:20]}...{key.key[-10:]}")
            if key.description:
                self.stdout.write(f"Description: {key.description}")
            self.stdout.write("-" * 90)
        
        self.stdout.write(f"\nTotal: {keys.count()} keys\n")