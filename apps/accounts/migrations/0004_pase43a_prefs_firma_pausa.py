# Pase 4.3-A: preferencias de aviso por tipo, firma del foro, silencio nocturno,
# hora del resumen y pausa de 24 horas.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0003_pase42_h_mensajes_privados')]
    operations = [
        migrations.AddField('user', 'signature', models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField('user', 'notify_prefs', models.JSONField(blank=True, default=dict)),
        migrations.AddField('user', 'digest_hour', models.PositiveSmallIntegerField(default=8)),
        migrations.AddField('user', 'quiet_night', models.BooleanField(default=True)),
        migrations.AddField('user', 'notifications_paused_until', models.DateTimeField(blank=True, null=True)),
    ]
