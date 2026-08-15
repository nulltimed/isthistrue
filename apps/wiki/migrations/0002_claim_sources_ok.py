# Pase 4.2 (C1): False = veredicto emitido con las busquedas de fuentes caidas
# (403 masivo de SearXNG, 2026-08-15). Re-analizable con reverdict_missing_sources.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('wiki', '0001_initial')]
    operations = [
        migrations.AddField(model_name='claim', name='sources_ok',
                            field=models.BooleanField(default=True)),
    ]
