# 5.5-A: los relojes por palabra de AssemblyAI, guardados para el karaoke.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0019_vigilante_china'),
    ]

    operations = [
        migrations.AddField(
            model_name='transcriptsegment',
            name='word_times',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
