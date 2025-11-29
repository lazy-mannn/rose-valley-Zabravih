from django.core.management.base import BaseCommand
from garbageData.models import TrashCan, FillRecord
from datetime import datetime, timedelta
import random

class Command(BaseCommand):
    help = "Create 50 trash cans in Kazanlak with initial fill records"

    def handle(self, *args, **options):
        # --- Trash cans data (50 locations in Kazanlak area) ---
        trash_cans_data = [
            (1, 42.62157187091345, 25.39428178312431),
            (2, 42.62047193601686, 25.395088604816188),
            (3, 42.62180812323232, 25.393416769763647),
            (4, 42.62234191611349, 25.39648177079153),
            (5, 42.62337715947338, 25.393733907311518),
            (6, 42.624641655959415, 25.392957120001345),
            (7, 42.62089123456789, 25.39512345678901),
            (8, 42.62298765432109, 25.39456789012345),
            (9, 42.62412345678901, 25.39389012345678),
            (10, 42.62156789012345, 25.39567890123456),
            # Add 40 more bins
            (11, 42.6205, 25.3940),
            (12, 42.6220, 25.3965),
            (13, 42.6235, 25.3945),
            (14, 42.6215, 25.3980),
            (15, 42.6240, 25.3950),
            (16, 42.6210, 25.3925),
            (17, 42.6225, 25.3935),
            (18, 42.6250, 25.3960),
            (19, 42.6195, 25.3955),
            (20, 42.6230, 25.3920),
            (21, 42.6208, 25.3948),
            (22, 42.6245, 25.3938),
            (23, 42.6218, 25.3970),
            (24, 42.6232, 25.3930),
            (25, 42.6212, 25.3943),
            (26, 42.6238, 25.3958),
            (27, 42.6222, 25.3953),
            (28, 42.6248, 25.3968),
            (29, 42.6202, 25.3933),
            (30, 42.6228, 25.3963),
            (31, 42.6214, 25.3928),
            (32, 42.6242, 25.3973),
            (33, 42.6206, 25.3978),
            (34, 42.6236, 25.3923),
            (35, 42.6224, 25.3948),
            (36, 42.6252, 25.3943),
            (37, 42.6198, 25.3938),
            (38, 42.6246, 25.3953),
            (39, 42.6216, 25.3968),
            (40, 42.6234, 25.3933),
            (41, 42.6204, 25.3963),
            (42, 42.6244, 25.3928),
            (43, 42.6226, 25.3958),
            (44, 42.6200, 25.3973),
            (45, 42.6240, 25.3983),
            (46, 42.6220, 25.3918),
            (47, 42.6254, 25.3948),
            (48, 42.6210, 25.3953),
            (49, 42.6230, 25.3938),
            (50, 42.6196, 25.3968),
        ]

        for trash_id, lat, lon in trash_cans_data:
            # Create or get TrashCan
            tc, created = TrashCan.objects.get_or_create(
                id=trash_id,
                defaults={'latitude': lat, 'longitude': lon}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Created TrashCan {trash_id}"))
                
                # Add 5 initial fill records (simulate last 5 days)
                for days_ago in range(5, 0, -1):
                    fill_level = random.randint(10, 95)
                    record_time = datetime.now() - timedelta(days=days_ago)
                    
                    FillRecord.objects.create(
                        trashcan=tc,
                        fill_level=fill_level,
                        timestamp=record_time
                    )
                
                self.stdout.write(self.style.SUCCESS(f"  Added 5 fill records for TrashCan {trash_id}"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠ TrashCan {trash_id} already exists"))

        self.stdout.write(self.style.SUCCESS("\n✓ All trash cans and fill records processed successfully!"))
