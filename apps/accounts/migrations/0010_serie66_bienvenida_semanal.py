# 6.6 (orden de David, 2026-11-09, «para cada cambio nuevo intenta implementar
# un sistema de revenue»): credito de bienvenida (motivo WELCOME en el libro)
# y resumen SEMANAL de avisos (modo WEEKLY). Solo cambian los choices.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_serie63_escrutinio_registro'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditledger',
            name='reason',
            field=models.CharField(choices=[('PACK', 'Compra de pack'), ('ADVANCE', 'Adelantar análisis'), ('ORIGIN', 'Rastreo de origen'), ('DEEP', 'Reanálisis profundo'), ('ADMIN', 'Ajuste del administrador'), ('WELCOME', 'Bienvenida')], max_length=8),
        ),
        migrations.AlterField(
            model_name='user',
            name='notify_mode',
            field=models.CharField(choices=[('WEB', 'Solo campana'), ('INSTANT', 'Email inmediato'), ('DAILY', 'Resumen diario'), ('WEEKLY', 'Resumen semanal')], default='WEB', max_length=8),
        ),
    ]
