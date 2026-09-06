# 5.20 (orden de David): gestion de post para moderacion — censura con
# cortina reversible por el lector + notas internas.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0020_relojes_por_palabra'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name='post', name='censored',
                            field=models.BooleanField(default=False)),
        migrations.AddField(model_name='post', name='censored_reason',
                            field=models.CharField(blank=True, default='', max_length=200)),
        migrations.AddField(model_name='post', name='censored_by',
                            field=models.ForeignKey(blank=True, null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='censored_posts', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='post', name='censored_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name='PostModNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('text', models.TextField(max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL)),
                ('post', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mod_notes', to='analysis.post')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
