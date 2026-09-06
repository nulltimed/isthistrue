# 5.4-D: el vigilante de China — si el video involucra a China, el analisis
# posterior evita los modelos chinos (censura) y usa los Anthropic del panel.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0018_categorias_vivas'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='china_related',
            field=models.BooleanField(default=None, null=True),
        ),
    ]
