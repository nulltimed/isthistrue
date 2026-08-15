# Pase 4.2 H8 (congelada §4 LEVANTADA por David con factura vista): MP simple,
# buzon cerrado por defecto, mods/superusuario siempre pueden enviar.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_initial')]
    operations = [
        migrations.AddField(model_name='user', name='accept_private_messages',
                            field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name='PrivateMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('body', models.TextField(max_length=8000)),
                ('read', models.BooleanField(default=False)),
                ('reported', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='pm_received', to=settings.AUTH_USER_MODEL)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='pm_sent', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']}),
    ]
