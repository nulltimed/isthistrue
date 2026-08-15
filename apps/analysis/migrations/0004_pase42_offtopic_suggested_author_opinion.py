# Pase 4.2 (A2 + A5 + D3 + D4): el clasificador solo SUGIERE Off-Topic (relegar =
# accion manual de mod) + la caja "Opina" abre el hilo + suscripciones de post +
# aviso de Trending.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0003_post_opus_rescanned'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='post', name='offtopic_suggested',
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='post', name='author_opinion',
                            field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='post', name='trending_notified',
                            field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name='PostSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('on_analysis', models.BooleanField(default=True)),
                ('on_messages', models.BooleanField(default=False)),
                ('on_trending', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name='subscriptions', to='analysis.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name='post_subscriptions',
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('post', 'user')}},
        ),
        migrations.AlterField(model_name='post', name='status',
            field=models.CharField(choices=[
                ('NEW', 'Nuevo'), ('CHEAP_RUNNING', 'Fase barata en curso'),
                ('PENDING_VALIDATION', 'Pendiente de validación (5 votos / 3 días)'),
                ('FULL_QUEUED', 'Análisis completo en cola'),
                ('FULL_RUNNING', 'Análisis completo en curso'), ('DONE', 'Analizado'),
                ('OFFTOPIC_SIGNALED', 'Off-Topic con señales'),
                ('VALIDATION_EXPIRED', 'Validación expirada (a criterio de moderación)'),
                ('OFFTOPIC_RAW', 'Off-Topic sin analizar (voluntario)'),
                ('HELD_FOR_REVIEW', 'Retenido (anti-acoso)'), ('FAILED', 'Error')],
                default='NEW', max_length=24)),
    ]
