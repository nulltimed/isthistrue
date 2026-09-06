# 5.4-B: titulo corto de cada pagina wiki, generado por el modelo profundo.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0008_opiniones_analizadas'),
    ]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='title',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]
