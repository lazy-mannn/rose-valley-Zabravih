from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('garbageData', '0007_trashcan_sofia_fields'),
    ]

    operations = [
        # Widen public_number so coloured-bin street addresses fit
        migrations.AlterField(
            model_name='trashcan',
            name='public_number',
            field=models.CharField(
                blank=True, default='', max_length=120,
                help_text='Sofia public number or street address (coloured bins)',
            ),
        ),
        # Compound lat/lon index — speeds up every bbox query
        migrations.AddIndex(
            model_name='trashcan',
            index=models.Index(fields=['latitude', 'longitude'], name='trashcan_lat_lon_idx'),
        ),
        # waste_type index — used by totals aggregation and future type filters
        migrations.AddIndex(
            model_name='trashcan',
            index=models.Index(fields=['waste_type'], name='trashcan_waste_type_idx'),
        ),
    ]
