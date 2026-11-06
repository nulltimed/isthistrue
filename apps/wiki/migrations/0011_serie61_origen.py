# 6.1 (orden de David, 2026-11-06): cadena de difusion del claim (rastreo de origen).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0010_fotogramas'),
    ]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='origin_chain',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='claim',
            name='origin_status',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
    ]
