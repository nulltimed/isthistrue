# 5.23-D/E (ordenes de David, 2026-09-08): menu de tres puntos (cerrar
# comentarios, fijar) y subforos en ARBOL con aprobacion de categorias
# propuestas. Los 12 temas historicos pasan a colgar de la raiz «principal».
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def colgar_de_principal(apps, schema_editor):
    Category = apps.get_model('analysis', 'Category')
    raiz, _ = Category.objects.get_or_create(slug='principal',
                                             defaults={'name': 'Principal'})
    Category.objects.exclude(pk=raiz.pk).filter(parent__isnull=True).update(parent=raiz)


def descolgar(apps, schema_editor):
    Category = apps.get_model('analysis', 'Category')
    Category.objects.update(parent=None)
    Category.objects.filter(slug='principal').delete()


class Migration(migrations.Migration):
    dependencies = [('analysis', '0021_gestion_del_post'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='category', name='parent',
                            field=models.ForeignKey(blank=True, null=True,
                                                    on_delete=django.db.models.deletion.SET_NULL,
                                                    related_name='children', to='analysis.category')),
        migrations.AddField(model_name='post', name='comments_closed',
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='post', name='pinned',
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='post', name='pending_category',
                            field=models.CharField(blank=True, default='', max_length=40)),
        migrations.AddField(model_name='post', name='approved_by',
                            field=models.ForeignKey(blank=True, null=True,
                                                    on_delete=django.db.models.deletion.SET_NULL,
                                                    related_name='approved_posts',
                                                    to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='post', name='approved_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name='post', name='status',
                              field=models.CharField(choices=[
                                  ('NEW', 'Nuevo'), ('CHEAP_RUNNING', 'Fase barata en curso'),
                                  ('PENDING_VALIDATION', 'Pendiente de validación (5 votos / 3 días)'),
                                  ('FULL_QUEUED', 'Análisis completo en cola'),
                                  ('AWAITING_BUDGET', 'En cola por presupuesto (esperando depósito o apadrinamiento)'),
                                  ('FULL_RUNNING', 'Análisis completo en curso'), ('DONE', 'Analizado'),
                                  ('OFFTOPIC_SIGNALED', 'Off-Topic con señales'),
                                  ('VALIDATION_EXPIRED', 'Validación expirada (a criterio de moderación)'),
                                  ('OFFTOPIC_RAW', 'Off-Topic sin analizar (voluntario)'),
                                  ('HELD_FOR_REVIEW', 'Retenido (anti-acoso)'), ('FAILED', 'Error'),
                                  ('PENDING_APPROVAL', 'Pendiente de aprobación (categoría propuesta)')],
                                  default='NEW', max_length=24)),
        migrations.RunPython(colgar_de_principal, descolgar),
    ]
