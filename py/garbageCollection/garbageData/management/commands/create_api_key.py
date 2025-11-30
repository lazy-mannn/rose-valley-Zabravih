from django.core.management.base import BaseCommand
from garbageData.models import APIKey

class Command(BaseCommand):
    help = "Generate a new API key for Raspberry Pi"

    def add_arguments(self, parser):
        parser.add_argument('device_name', type=str, help='Device name (e.g., "RPi-Truck-1")')
        parser.add_argument('--description', type=str, default='', help='Optional description')

    def handle(self, *args, **options):
        device_name = options['device_name']
        description = options['description']
        
        api_key = APIKey.objects.create(
            device_name=device_name,
            description=description
        )
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*70))
        self.stdout.write(self.style.SUCCESS("✅ API KEY CREATED!"))
        self.stdout.write(self.style.SUCCESS("="*70 + "\n"))
        self.stdout.write(f"Device: {api_key.device_name}")
        self.stdout.write(f"Description: {api_key.description or '(none)'}")
        self.stdout.write(f"Created: {api_key.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("🔑 API KEY (save this!):"))
        self.stdout.write(self.style.SUCCESS(f"\n{api_key.key}\n"))
        self.stdout.write(self.style.WARNING("⚠️  This key will NOT be shown again!"))
        self.stdout.write("")
        self.stdout.write("📝 Usage:")
        self.stdout.write(f"""
curl -X POST https://zabravih.org/api/update/ \\
  -H "X-API-Key: {api_key.key}" \\
  -H "Content-Type: application/json" \\
  -d '{{"trashcan_id": 122, "category": "is_full", "confidence": 95}}'
        """)
        self.stdout.write(self.style.SUCCESS("="*70 + "\n"))