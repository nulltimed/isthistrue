# 6.1 (orden de David, 2026-11-06): monedero y libro de creditos.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_ultima_visita'),
        ('analysis', '0024_bibliotecario_sugerencia'),
        ('wiki', '0011_serie61_origen'),
    ]

    operations = [
        migrations.CreateModel(
            name='CreditWallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance', models.PositiveIntegerField(default=0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='credit_wallet', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='CreditLedger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delta', models.IntegerField()),
                ('reason', models.CharField(choices=[('PACK', 'Compra de pack'), ('ADVANCE', 'Adelantar análisis'), ('ORIGIN', 'Rastreo de origen'), ('ADMIN', 'Ajuste del administrador')], max_length=8)),
                ('note', models.CharField(blank=True, default='', max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('claim', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='credit_moves', to='wiki.claim')),
                ('post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='credit_moves', to='analysis.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_moves', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
