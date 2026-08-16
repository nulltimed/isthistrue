# Pase 4.3-A: punto de lectura por usuario e hilo (separador de no leidos).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('forum_local', '0002_pase42_h_sensibles_ocultos'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='TopicRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('topic_id', models.IntegerField()),
                ('last_post_id', models.IntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('topic_id', 'user')}}),
    ]
