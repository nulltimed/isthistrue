# 5.23-H (orden de David): los logs del sistema, consultables en el panel.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0004_apadrinamiento'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('level', models.CharField(db_index=True, max_length=10)),
                ('logger', models.CharField(db_index=True, max_length=80)),
                ('role', models.CharField(choices=[('web', 'Web'), ('worker', 'Worker'),
                                                   ('beat', 'Beat'), ('other', 'Otro')],
                                          db_index=True, default='other', max_length=10)),
                ('message', models.TextField()),
                ('post_id', models.IntegerField(blank=True, null=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
