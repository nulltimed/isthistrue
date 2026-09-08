# 5.23-C (orden de David, 2026-09-08): votos ▲/▼ en posts y comentarios que
# suben y bajan el karma del autor. Los votos existentes eran positivos.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('forum_local', '0003_pase43a_topicread'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(
            model_name='vote', name='value',
            field=models.SmallIntegerField(default=1)),
        migrations.CreateModel(
            name='MessageVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('machina_post_id', models.IntegerField(db_index=True)),
                ('value', models.SmallIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('machina_post_id', 'user')}}),
    ]
