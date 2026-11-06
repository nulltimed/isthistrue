# 6.1 (orden de David, 2026-11-06): el metodo CREDIT en el libro de financiacion.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0005_system_log'),
    ]

    operations = [
        migrations.AlterField(
            model_name='donation',
            name='method',
            field=models.CharField(choices=[('PAYPAL', 'PayPal'), ('BIZUM', 'Bizum'), ('OTHER', 'Otro'), ('CREDIT', 'Créditos (SL)')], max_length=8),
        ),
    ]
