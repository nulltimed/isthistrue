# Pase 4.4-G: pista del numero de voces para la diarizacion (agente o moderacion).
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0010_pase44b_fecha_suceso')]
    operations = [
        migrations.AddField('post', 'speakers_count',
                            models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField('post', 'speakers_confidence',
                            models.CharField(blank=True, default='', max_length=8)),
        migrations.AddField('post', 'speakers_count_source',
                            models.CharField(blank=True, default='', max_length=8,
                                             choices=[('', '—'), ('agent', 'Estimado por el sistema'),
                                                      ('mod', 'Corregido por moderación')])),
    ]
