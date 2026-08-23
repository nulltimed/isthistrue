# Pase 4.4-A: idioma de la interfaz en el perfil del usuario.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_pase43a_prefs_firma_pausa')]
    operations = [
        migrations.AddField(
            'user', 'language',
            models.CharField(blank=True, default='', max_length=5,
                             choices=[('', 'Automático (idioma del navegador)'),
                                      ('es', 'Español'), ('en', 'English')])),
    ]
