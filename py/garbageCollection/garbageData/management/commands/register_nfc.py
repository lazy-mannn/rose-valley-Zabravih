from django.core.management.base import BaseCommand
from garbageData.models import TrashCan

class Command(BaseCommand):
    help = "Register NFC UID to a bin"

    def add_arguments(self, parser):
        parser.add_argument('bin_id', type=int, help='Bin ID')
        parser.add_argument('nfc_uid', type=str, help='NFC tag UID (e.g., 123456789)')

    def handle(self, *args, **options):
        bin_id = options['bin_id']
        nfc_uid = str(options['nfc_uid'])
        
        try:
            # Check if UID already registered
            existing = TrashCan.objects.filter(nfc_uid=nfc_uid).first()
            if existing:
                self.stdout.write(self.style.ERROR(
                    f"\n❌ NFC UID {nfc_uid} already registered to Bin {existing.id}\n"
                ))
                return
            
            # Get bin
            bin = TrashCan.objects.get(id=bin_id)
            
            # Register UID
            bin.nfc_uid = nfc_uid
            bin.save()
            
            self.stdout.write(self.style.SUCCESS("\n" + "="*70))
            self.stdout.write(self.style.SUCCESS("✅ NFC TAG REGISTERED!"))
            self.stdout.write(self.style.SUCCESS("="*70 + "\n"))
            self.stdout.write(f"Bin ID: {bin.id}")
            self.stdout.write(f"NFC UID: {nfc_uid}")
            self.stdout.write(f"Location: {bin.latitude}, {bin.longitude}")
            self.stdout.write("")
            self.stdout.write("✅ Tag can now be used for collections")
            self.stdout.write(self.style.SUCCESS("="*70 + "\n"))
            
        except TrashCan.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"\n❌ Bin {bin_id} not found\n"))