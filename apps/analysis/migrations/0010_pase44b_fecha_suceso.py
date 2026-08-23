# Pase 4.4-B: fecha del SUCESO (no la de subida) para poder datar los datos.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0009_pase43f_estado_en_cola')]
    operations = [
        migrations.AddField('post', 'event_date', models.DateField(blank=True, null=True)),
        migrations.AddField('post', 'event_date_note',
                            models.CharField(blank=True, default='', max_length=250)),
        migrations.AddField('post', 'event_date_source',
                            models.CharField(blank=True, default='', max_length=8,
                                             choices=[('', '—'), ('agent', 'Estimada por el sistema'),
                                                      ('mod', 'Corregida por moderación')])),
    ]
