"""Barrido universal de clasificacion (MODEL_CLASSIFIER=Sonnet, decidido por David):
claims + señales + clickbait + adulto. Coste fase barata ~0,05 EUR.

4.3-A.7: se trocea en lotes de settings.SWEEP_BATCH_SIZE frases. Los indices que
viajan al modelo y vuelven son SIEMPRE globales (posicion en la transcripcion
completa), para que anclar la señal y crear el claim sigan apuntando a la misma
frase. Si un lote vuelve roto, se avisa a gritos en los logs y se sigue con los
demas: degradar con WARNING, jamas fallar en silencio (regla 6.7 del operador).
"""
import logging

from django.conf import settings
from . import client, prompts

logger = logging.getLogger('agents.sweep')

MOCK_SWEEP = {
    'claims': [
        {'segment_index': 1, 'text': '[SIMULADO] La torre Eiffel mide 300 metros y se termino en 1889.',
         'kind': 'FACTUAL', 'ambiguous': False, 'contradicts_common_knowledge': False},
        {'segment_index': 2, 'text': '[SIMULADO] Esto va a cambiar el mundo el año que viene.',
         'kind': 'OPINION', 'ambiguous': False, 'contradicts_common_knowledge': False},
    ],
    'manipulation': True, 'is_adult': False, 'language': 'es',
}


def _anchor(segments, claims):
    """Ancla la señal barata a su frase. El indice es GLOBAL: posicion en la
    transcripcion completa, no dentro del lote."""
    for c in claims:
        idx = c.get('segment_index')
        if isinstance(idx, int) and 0 <= idx < len(segments):
            seg = segments[idx]
            if c.get('contradicts_common_knowledge'):
                seg.signal = 'CONTRADICTS_MODEL'
            elif c.get('kind') == 'OPINION':
                seg.signal = 'OPINION'
            else:
                seg.signal = 'FACTUAL_UNVERIFIED'
            seg.save(update_fields=['signal'])


def run(post):
    # Orden explicito: el Meta ya ordena, pero esta lista define los indices que
    # viajan al modelo y no puede depender de lo que decida la BD (leccion O1).
    segments = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
    size = max(1, int(getattr(settings, 'SWEEP_BATCH_SIZE', 40)))
    max_tokens = int(getattr(settings, 'SWEEP_MAX_TOKENS', 8000))

    claims, manipulation, is_adult = [], False, False
    lotes = fallidos = 0
    for start in range(0, len(segments), size):
        lote = segments[start:start + size]
        lotes += 1
        payload = '\n'.join(f'[{start + j}] ({s.start_seconds:.0f}s) {s.text}'
                             for j, s in enumerate(lote))
        from apps.agents.catalog import model_for
        result = client.call_json(model_for('sweep'), prompts.SWEEP_SYSTEM,
                                  payload, max_tokens=max_tokens,
                                  mock_payload=MOCK_SWEEP)
        if not isinstance(result, dict) or 'error' in result:
            fallidos += 1
            motivo = result.get('error') if isinstance(result, dict) else 'respuesta_no_dict'
            logger.warning('Barrido: lote %d/%d (frases %d-%d) del post %s ILEGIBLE (%s). '
                           'Sube SWEEP_MAX_TOKENS o baja SWEEP_BATCH_SIZE en el .env.',
                           lotes, (len(segments) + size - 1) // size or 1,
                           start, start + len(lote) - 1, post.pk, motivo)
            continue
        lote_claims = [c for c in (result.get('claims') or []) if isinstance(c, dict)]
        _anchor(segments, lote_claims)
        claims.extend(lote_claims)
        manipulation = manipulation or bool(result.get('manipulation'))
        is_adult = is_adult or bool(result.get('is_adult'))

    if fallidos:
        logger.error('Barrido del post %s: %d de %d lotes ilegibles. El semaforo de '
                     'esas frases queda vacio (NO es que el video no tenga nada).',
                     post.pk, fallidos, lotes)
    return {'claims': claims, 'manipulation': manipulation, 'is_adult': is_adult,
            'sweep_failed': bool(fallidos), 'batches': lotes, 'batches_failed': fallidos}
