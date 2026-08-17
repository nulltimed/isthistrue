"""4.3-D: las fichas ANTIGUAS que ya tenian QID tambien abren pagina.

Objecion justa del operador (docs/35 §3.1): el 4.3-C justifico dejar cerradas
las fichas antiguas diciendo que "nunca se confirmaron con QID", y en el espejo
habia una que SI lo tenia (Ana Botella, Q41266) y quedo cerrada igualmente,
porque 0004 no reabria retroactivamente.

La regla del proyecto es una sola: **tener QID de Wikidata abre pagina**. Si vale
para las fichas nuevas, tiene que valer para las viejas; si no, la regla depende
de la fecha de creacion, que es justo lo que no se le puede explicar a nadie.
Las fichas SIN QID siguen cerradas: podrian ser particulares (candado congelado).
"""
from django.db import migrations


def abrir_las_que_tienen_qid(apps, schema_editor):
    Interlocutor = apps.get_model('wiki', 'Interlocutor')
    Interlocutor.objects.exclude(wikidata_id='').filter(
        is_public_figure__isnull=True).update(is_public_figure=True)


def atras(apps, schema_editor):
    """Vuelve a dejarlas en revision (None), que es de donde venian."""
    Interlocutor = apps.get_model('wiki', 'Interlocutor')
    Interlocutor.objects.exclude(wikidata_id='').filter(
        is_public_figure=True).update(is_public_figure=None)


class Migration(migrations.Migration):

    dependencies = [('wiki', '0004_interlocutor_base_slug')]

    operations = [migrations.RunPython(abrir_las_que_tienen_qid, atras)]
