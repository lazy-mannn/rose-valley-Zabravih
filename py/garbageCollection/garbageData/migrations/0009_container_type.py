from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('garbageData', '0008_indexes_and_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='trashcan',
            name='container_type',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Container shape: iglu, bobar, etc.',
                max_length=20,
            ),
        ),
    ]
