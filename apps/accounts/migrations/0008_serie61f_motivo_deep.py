# 6.1-f (orden de David, 2026-11-06): el reanalisis profundo de pago en el libro.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_serie61_creditos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditledger',
            name='reason',
            field=models.CharField(choices=[('PACK', 'Compra de pack'), ('ADVANCE', 'Adelantar análisis'), ('ORIGIN', 'Rastreo de origen'), ('DEEP', 'Reanálisis profundo'), ('ADMIN', 'Ajuste del administrador')], max_length=8),
        ),
    ]
