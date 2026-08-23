# Pase 4.4-C: salud diaria de los modelos configurados.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('panel', '0001_initial')]
    operations = [
        migrations.CreateModel(
            name='ModelHealth',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('model_id', models.CharField(max_length=60, unique=True)),
                ('ok', models.BooleanField(default=True)),
                ('checked_at', models.DateTimeField(auto_now=True)),
                ('detail', models.CharField(blank=True, default='', max_length=200)),
            ],
        ),
    ]
