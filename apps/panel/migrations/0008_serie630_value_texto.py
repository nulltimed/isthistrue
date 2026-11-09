# Serie 6.30 (orden de David, 2026-11-09): la mini-guia del moderador se edita
# desde el panel en HTML — el value de SystemSetting pasa a TextField (antes
# CharField(200): una guia no cabia). Cambio inofensivo para las filas viejas.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0007_serie63_dossier'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemsetting',
            name='value',
            field=models.TextField(),
        ),
    ]
