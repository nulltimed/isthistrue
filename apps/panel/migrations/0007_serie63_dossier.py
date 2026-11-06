# 6.3 (2026-11-06): el dossier B2B con acceso por enlace secreto.
import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0006_serie61_metodo_credit'),
        ('analysis', '0024_bibliotecario_sugerencia'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dossier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_name', models.CharField(max_length=200)),
                ('client_email', models.EmailField(max_length=254)),
                ('token', models.CharField(default=secrets.token_urlsafe, max_length=64)),
                ('intro', models.TextField(blank=True, default='')),
                ('revoked', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('posts', models.ManyToManyField(blank=True, related_name='dossiers', to='analysis.post')),
            ],
        ),
    ]
