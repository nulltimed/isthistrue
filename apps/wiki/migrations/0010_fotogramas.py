# 5.8 (orden expresa de David): el fotograma que el claim involucra, en la wiki.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0009_titulo_ia'),
    ]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='frame_image',
            field=models.FileField(blank=True, default='', upload_to='frames/'),
        ),
        migrations.AddField(
            model_name='claim',
            name='frame_second',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='claim',
            name='frame_note',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
