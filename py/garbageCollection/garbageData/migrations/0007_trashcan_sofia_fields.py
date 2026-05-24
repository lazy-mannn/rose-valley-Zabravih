from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('garbageData', '0006_trashcan_nfc_uid'),
    ]

    operations = [
        migrations.AddField(
            model_name='trashcan',
            name='public_number',
            field=models.CharField(blank=True, default='', max_length=40),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='district_id',
            field=models.IntegerField(blank=True, db_index=True, null=True,
                                      help_text='Sofia district number 1–24'),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='district_name',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='waste_type',
            field=models.CharField(blank=True, default='general', max_length=30,
                                   help_text='e.g. general, recycling, organic'),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='bin_status',
            field=models.CharField(blank=True, default='pending', max_length=20,
                                   help_text='Sofia API status: pending, active, …'),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='capacity_volume',
            field=models.FloatField(blank=True, null=True,
                                    help_text='Bin volume in cubic metres'),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='bin_count',
            field=models.IntegerField(default=1,
                                      help_text='Number of bins at this location'),
        ),
        migrations.AddField(
            model_name='trashcan',
            name='last_cleaned',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text='Last collection per Sofia API'),
        ),
    ]
