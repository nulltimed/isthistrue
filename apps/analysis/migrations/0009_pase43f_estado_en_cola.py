"""4.3-F: nuevo estado AWAITING_BUDGET ("En cola por presupuesto").

Un video que se lleva mas de media asignacion diaria no se rechaza ni se cobra:
espera turno. Solo cambia la lista de opciones del campo `status`; ningun dato
existente se toca.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('analysis', '0008_pase43d_tiempos_de_analisis')]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='status',
            field=models.CharField(
                choices=[('NEW', 'Nuevo'),
                         ('CHEAP_RUNNING', 'Fase barata en curso'),
                         ('PENDING_VALIDATION', 'Pendiente de validación (5 votos / 3 días)'),
                         ('FULL_QUEUED', 'Análisis completo en cola'),
                         ('AWAITING_BUDGET',
                          'En cola por presupuesto (esperando depósito o apadrinamiento)'),
                         ('FULL_RUNNING', 'Análisis completo en curso'),
                         ('DONE', 'Analizado'),
                         ('OFFTOPIC_SIGNALED', 'Off-Topic con señales'),
                         ('VALIDATION_EXPIRED', 'Validación expirada (a criterio de moderación)'),
                         ('OFFTOPIC_RAW', 'Off-Topic sin analizar (voluntario)'),
                         ('HELD_FOR_REVIEW', 'Retenido (anti-acoso)'),
                         ('FAILED', 'Error')],
                default='NEW', max_length=24),
        ),
    ]
