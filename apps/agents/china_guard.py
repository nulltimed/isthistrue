"""5.4-D (orden de David): el vigilante de China.

Los modelos chinos censuran lo que toca a China. Al llegar la transcripcion,
un detector (Haiku por defecto; rueda «Detector de temas sobre China» del
panel de David) marca el video. Si involucra a China, models_for_post entrega
los modelos Anthropic del panel para TODO el analisis posterior — la censura
no analiza. En la duda o si el detector falla, se marca True (mejor pagar un
poco mas que publicar un analisis censurado).
"""
import json
import logging

from apps.agents import client, prompts
from apps.agents.catalog import model_for, fallback_for

logger = logging.getLogger('agents.china_guard')


def detectar(post, transcript_text):
    """Marca post.china_related (una sola vez por video)."""
    if post.china_related is not None:
        return post.china_related
    payload = json.dumps({'titulo': (post.title or '')[:200],
                          'transcripcion': (transcript_text or '')[:4000]},
                         ensure_ascii=False)
    datos = client.call_json(model_for('china_guard'),
                             prompts.CHINA_GUARD_SYSTEM, payload,
                             max_tokens=120,
                             fallback=fallback_for('china_guard'),
                             mock_payload={'involucra_china': False,
                                           'motivo': 'simulado'})
    if 'error' in datos:
        # Fallo del detector: en la duda, fuera de los modelos chinos.
        logger.warning('Vigilante de China fallo en el post %s: %s — se marca '
                       'True por prudencia', post.pk, datos.get('error'))
        post.china_related = True
    else:
        post.china_related = bool(datos.get('involucra_china'))
        if post.china_related:
            logger.info('Post %s involucra a China (%s): analisis por Anthropic',
                        post.pk, str(datos.get('motivo'))[:100])
    post.save(update_fields=['china_related'])
    return post.china_related
