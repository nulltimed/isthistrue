# Pase 4.4-B: tres estados nuevos del semaforo y la base temporal del veredicto.
from django.db import migrations, models

COLORS = [('GREEN', '🟢 Verificado'), ('AMBER', '🟡 Engañoso o sin contexto'),
          ('RED', '🔴 Falso'), ('GREY', '⚪ No verificable'),
          ('PENDING', '⏳ Pendiente de verificar'),
          ('UNDECIDED', '🔍 El sistema lo ha mirado y no se ha decidido'),
          ('NEEDS_HUMAN', '👁 No verificable solo con audio')]


class Migration(migrations.Migration):
    dependencies = [('wiki', '0005_abrir_fichas_con_qid')]
    operations = [
        migrations.AlterField('claim', 'color',
                              models.CharField(choices=COLORS, default='PENDING', max_length=12)),
        migrations.AlterField('claimversion', 'color',
                              models.CharField(choices=COLORS, max_length=12)),
        migrations.AddField('claim', 'temporal_basis',
                            models.CharField(blank=True, default='', max_length=300)),
    ]
