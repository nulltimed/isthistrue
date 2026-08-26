# Pase 4.4-I: la pasada de sentido marca frases de atribucion incierta.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0011_pase44g_voces')]
    operations = [
        migrations.AddField('transcriptsegment', 'attribution_uncertain',
                            models.BooleanField(default=False)),
        migrations.AddField('transcriptsegment', 'attribution_note',
                            models.CharField(blank=True, default='', max_length=160)),
    ]
