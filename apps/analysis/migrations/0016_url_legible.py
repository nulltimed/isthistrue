# 5.0-C: URL legible del post — el campo slug y su relleno para los posts ya
# existentes. El slug se genera UNA vez del titulo y no cambia despues.
from django.db import migrations, models
from django.utils.text import slugify


def rellenar_slugs(apps, schema_editor):
    Post = apps.get_model('analysis', 'Post')
    for post in Post.objects.exclude(title='').filter(slug=''):
        s = slugify(post.title)[:80].rstrip('-')
        if s:
            Post.objects.filter(pk=post.pk).update(slug=s)


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0015_timbre_aai'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='slug',
            field=models.SlugField(blank=True, default='', max_length=80),
        ),
        migrations.RunPython(rellenar_slugs, migrations.RunPython.noop),
    ]
