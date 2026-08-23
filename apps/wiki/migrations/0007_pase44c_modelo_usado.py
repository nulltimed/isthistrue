# Pase 4.4-C: con que modelo se emitio cada veredicto.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('wiki', '0006_pase44b_semaforo')]
    operations = [
        migrations.AddField('claim', 'model_used',
                            models.CharField(blank=True, default='', max_length=60)),
    ]
