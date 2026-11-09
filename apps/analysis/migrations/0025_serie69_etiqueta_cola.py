# 6.9 (orden de David, 2026-11-09: «Elimina las donaciones de cualquier
# página»): la etiqueta del estado AWAITING_BUDGET deja de hablar de
# apadrinamiento. Solo cambia el texto del choice.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0024_bibliotecario_sugerencia'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='status',
            field=models.CharField(choices=[('NEW', 'Nuevo'), ('CHEAP_RUNNING', 'Fase barata en curso'), ('PENDING_VALIDATION', 'Pendiente de validación (5 votos / 3 días)'), ('FULL_QUEUED', 'Análisis completo en cola'), ('AWAITING_BUDGET', 'En cola por presupuesto (los créditos la adelantan)'), ('FULL_RUNNING', 'Análisis completo en curso'), ('DONE', 'Analizado'), ('OFFTOPIC_SIGNALED', 'Off-Topic con señales'), ('VALIDATION_EXPIRED', 'Validación expirada (a criterio de moderación)'), ('OFFTOPIC_RAW', 'Off-Topic sin analizar (voluntario)'), ('HELD_FOR_REVIEW', 'Retenido (anti-acoso)'), ('FAILED', 'Error'), ('PENDING_APPROVAL', 'Pendiente de aprobación (categoría propuesta)')], default='NEW', max_length=24),
        ),
    ]
