# 5.3-A: las donaciones del boton web nacen sin verificar; David confirma.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0002_pase44c_modelhealth'),
    ]

    operations = [
        migrations.AddField(
            model_name='donation',
            name='verified',
            field=models.BooleanField(default=True),
        ),
    ]
