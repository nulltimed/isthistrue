# 6.3 (orden de David, 2026-11-06): escrutinio del registro en dos carriles.
import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_serie61f_motivo_deep'),
    ]

    operations = [
        migrations.CreateModel(
            name='SignupVetting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('PERSON', 'Persona física'), ('ORG', 'Persona jurídica')], default='PERSON', max_length=8)),
                ('org_name', models.CharField(blank=True, default='', max_length=200)),
                ('org_website', models.URLField(blank=True, default='')),
                ('status', models.CharField(choices=[('OK', 'Sin reparos'), ('PENDING', 'En escrutinio'), ('DENIED', 'Denegado'), ('APPEALED', 'Reclamado — en la bandeja')], default='OK', max_length=10)),
                ('verdict', models.JSONField(blank=True, default=dict)),
                ('appeal_token', models.CharField(default=secrets.token_urlsafe, max_length=64)),
                ('appeal_text', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='signups_resolved', to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='signup_vetting', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
