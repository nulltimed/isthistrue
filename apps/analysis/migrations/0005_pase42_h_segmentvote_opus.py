# Pase 4.2 H5: voto ▲/▼ por oracion + candado de re-analisis Opus por oracion.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0004_pase42_offtopic_suggested_author_opinion'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AddField(model_name='transcriptsegment', name='opus_rescanned',
                            field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name='SegmentVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('value', models.SmallIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('segment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='sentence_votes', to='analysis.transcriptsegment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={'unique_together': {('segment', 'user')}},
        ),
    ]
