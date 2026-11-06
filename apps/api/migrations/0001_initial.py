# SERIE 6.2 (2026-11-06): claves y contadores de la API publica de lectura.
import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0008_serie61f_motivo_deep'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApiKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('ORG', 'Persona jurídica'), ('PERSON', 'Persona física')], default='ORG', max_length=8)),
                ('entity_name', models.CharField(max_length=200)),
                ('contact_email', models.EmailField(max_length=254)),
                ('website', models.URLField(blank=True, default='')),
                ('purpose', models.TextField(max_length=1000)),
                ('ai_verdict', models.JSONField(blank=True, default=dict)),
                ('appeal_token', models.CharField(default=secrets.token_urlsafe, max_length=64)),
                ('appeal_text', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('PENDING', 'Pendiente de escrutinio'), ('APPROVED', 'Aprobada'), ('DENIED', 'Denegada'), ('APPEALED', 'Reclamada — en la bandeja'), ('REVOKED', 'Revocada')], default='PENDING', max_length=10)),
                ('tier', models.CharField(choices=[('FREE', 'Gratuita (con atribución)'), ('PRO', 'Profesional')], default='FREE', max_length=5)),
                ('key', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ApiUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('count', models.PositiveIntegerField(default=0)),
                ('api_key', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usage', to='api.apikey')),
            ],
            options={'unique_together': {('api_key', 'date')}},
        ),
    ]
