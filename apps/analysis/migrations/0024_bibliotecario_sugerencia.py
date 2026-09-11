# 5.27-D (orden de David, 2026-09-11): el bibliotecario sugiere el subforo.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0023_costentry_model')]
    operations = [
        migrations.AddField(model_name='post', name='suggested_topic',
                            field=models.CharField(blank=True, default='', max_length=40)),
        migrations.AddField(model_name='post', name='suggested_topic_note',
                            field=models.CharField(blank=True, default='', max_length=200)),
    ]
