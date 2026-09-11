# 5.26-A (orden de David, 2026-09-11): el libro de cuentas apunta QUE MODELO
# hizo cada llamada, para saber cuanto se lleva cada uno.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0022_subforos_y_menu')]
    operations = [
        migrations.AddField(
            model_name='costentry', name='model',
            field=models.CharField(blank=True, db_index=True, default='', max_length=60)),
    ]
