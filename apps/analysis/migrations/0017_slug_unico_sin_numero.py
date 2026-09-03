# 5.0-D (correccion de David): la URL del post pierde el numero. El slug pasa a
# ser UNICO (el duplicado recibe -2, -3...) y NULL cuando no hay titulo — unique
# permite muchos NULL pero no muchos ''.
from django.db import migrations, models


def normalizar(apps, schema_editor):
    Post = apps.get_model('analysis', 'Post')
    Post.objects.filter(slug='').update(slug=None)
    vistos = set()
    for post in Post.objects.exclude(slug=None).order_by('pk'):
        base = post.slug
        if base.isdigit():
            base += '-video'
        candidato, n = base, 1
        while candidato in vistos:
            n += 1
            candidato = f'{base}-{n}'
        vistos.add(candidato)
        if candidato != post.slug:
            Post.objects.filter(pk=post.pk).update(slug=candidato)


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0016_url_legible'),
    ]

    operations = [
        migrations.AlterField(
            model_name='post',
            name='slug',
            field=models.SlugField(blank=True, default=None, max_length=80,
                                   null=True),
        ),
        migrations.RunPython(normalizar, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='post',
            name='slug',
            field=models.SlugField(blank=True, default=None, max_length=80,
                                   null=True, unique=True),
        ),
    ]
