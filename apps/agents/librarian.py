"""5.27-D (orden de David, 2026-09-11): el BIBLIOTECARIO comprueba, al terminar la
fase barata, que el subforo elegido por quien publico el video cuadra con lo que
se dice en el. Hereda la rueda «Bibliotecario de categorias» del panel (la del
clasificador de segunda opinion, retirado en este mismo pase).

Nunca mueve nada: deja post.suggested_topic + suggested_topic_note, y moderacion
acepta («Mover ahi») o descarta con un clic desde el post. Cualquier fallo o
duda del modelo = sin sugerencia (regla 5.7).
"""
import json
import logging

logger = logging.getLogger('agents.librarian')

MOCK_CHECK = {'encaja': True}


def check_category(post, sweep_result):
    """Devuelve el slug sugerido ('' si encaja o no se puede decidir)."""
    from apps.agents import client, prompts
    from apps.agents.catalog import models_for_post
    from apps.analysis.models import Category
    existentes = [{'slug': s, 'nombre': n}
                  for s, n in Category.objects.exclude(slug=Category.ROOT_SLUG)
                  .values_list('slug', 'name')]
    validos = {c['slug'] for c in existentes}
    if post.topic not in validos or len(validos) < 2:
        return ''
    claims = (sweep_result or {}).get('claims') or []
    lineas = [str(c.get('text', ''))[:200] for c in claims[:60]]
    payload = json.dumps({'titulo': post.title or '',
                          'categoria_elegida': post.topic,
                          'categorias': existentes,
                          'afirmaciones': lineas}, ensure_ascii=False)
    _m, _fb = models_for_post('categories', post)
    datos = client.call_json(_m, prompts.CATEGORY_CHECK_SYSTEM, payload,
                             max_tokens=150, fallback=_fb, mock_payload=MOCK_CHECK)
    if not isinstance(datos, dict) or 'error' in datos or datos.get('encaja', True):
        post.suggested_topic = ''
        post.suggested_topic_note = ''
        post.save(update_fields=['suggested_topic', 'suggested_topic_note'])
        return ''
    slug = str(datos.get('slug', '')).strip()
    if slug not in validos or slug == post.topic:
        return ''
    post.suggested_topic = slug
    post.suggested_topic_note = str(datos.get('motivo', '')).strip()[:200]
    post.save(update_fields=['suggested_topic', 'suggested_topic_note'])
    logger.info('Bibliotecario: el post %s quizá encaje mejor en «%s» (%s)',
                post.pk, slug, post.suggested_topic_note)
    return slug
