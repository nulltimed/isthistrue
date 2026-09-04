# 5.1-D (orden de David): taxonomia viva — tabla Category sembrada con los 12
# temas historicos y su uso real; Post.topic pasa a slug libre (40 chars).
from django.db import migrations, models


def sembrar(apps, schema_editor):
    Category = apps.get_model('analysis', 'Category')
    Post = apps.get_model('analysis', 'Post')
    TOPICS = [('politica', 'Política'), ('salud', 'Salud'), ('ciencia', 'Ciencia'),
              ('economia', 'Economía'), ('sucesos', 'Sucesos'),
              ('internacional', 'Internacional'), ('tecnologia', 'Tecnología'),
              ('medioambiente', 'Medioambiente'), ('deporte', 'Deporte'),
              ('cultura', 'Cultura'), ('sociedad', 'Sociedad'), ('otros', 'Otros')]
    for slug, name in TOPICS:
        Category.objects.get_or_create(
            slug=slug, defaults={'name': name,
                                 'times_used': Post.objects.filter(topic=slug).count()})


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0017_slug_unico_sin_numero'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40)),
                ('slug', models.SlugField(max_length=40, unique=True)),
                ('times_used', models.IntegerField(default=0)),
                ('created_by_agent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-times_used', 'name']},
        ),
        migrations.AlterField(
            model_name='post',
            name='topic',
            field=models.CharField(default='otros', max_length=40),
        ),
        migrations.RunPython(sembrar, migrations.RunPython.noop),
    ]
