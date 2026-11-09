# Serie 6.16 (orden de David, 2026-11-09): nivel de proceso visible del analisis.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0025_serie69_etiqueta_cola'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='progress_note',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
    ]
