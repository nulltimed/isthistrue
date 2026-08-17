"""4.3-C: raiz comun del nombre para la desambiguacion de homonimos.

David: "si hay conflictos de nombres y apellidos, en la misma pagina de
wikitrue.xyztserver.com/pedro-sanchez apareceran todos los personajes posibles
indexados". El `slug` es unico y puede llevar sufijo ('pedro-sanchez-2'); el
`base_slug` NO lo lleva, y es lo que permite encontrar a todos los homonimos de
una sola consulta.

La migracion de datos rellena el base_slug de las fichas ya existentes: un fallo
de formato que ya llego a la base de datos necesita DOS correcciones, el codigo y
los datos (regla 7 del operador, §2.12 de docs/34).
"""
from django.db import migrations, models
from django.utils.text import slugify


def rellenar_base_slug(apps, schema_editor):
    Interlocutor = apps.get_model('wiki', 'Interlocutor')
    for person in Interlocutor.objects.all().iterator():
        base = slugify(person.name)[:150] or 'persona'
        if person.base_slug != base:
            person.base_slug = base
            person.save(update_fields=['base_slug'])


def atras(apps, schema_editor):
    pass  # quitar la columna ya deshace el cambio


class Migration(migrations.Migration):

    dependencies = [('wiki', '0003_identidad_univoca_wikidata')]

    operations = [
        migrations.AddField(
            model_name='interlocutor',
            name='base_slug',
            field=models.SlugField(blank=True, db_index=True, default='', max_length=170),
        ),
        migrations.RunPython(rellenar_base_slug, atras),
    ]
