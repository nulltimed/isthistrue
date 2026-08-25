"""
Algoritmo FACTUAL vs OPINION (README v2 §4). Umbrales en SystemSetting (panel).
OPINION si CUALQUIERA de:
  - ratio: claims grises >= 70% del total
  - densidad: < 1 claim factual por cada 5 minutos de tramo
Con dos excepciones que RESCATAN al flujo completo:
  - manipulacion CON claims factuales (direccion invertida del castigo)
  - algun claim factual coincide con claim rojo/ambar ya en la wiki (embeddings, gratis)
"""
import logging

from apps.panel.models import SystemSetting

logger = logging.getLogger('agents.algorithm')


def classify(post, sweep_result):
    claims = sweep_result['claims']
    factual = [c for c in claims if c.get('kind') == 'FACTUAL']
    grey = [c for c in claims if c.get('kind') == 'OPINION']
    total = len(claims)

    ratio_threshold = SystemSetting.get_int('opinion_ratio_percent', 70)
    minutes_per_factual = SystemSetting.get_int('minutes_per_factual_claim', 5)
    # 4.3-A.8: el tramo analizado ya no son 20 min fijos.
    from django.conf import settings as dj
    tranche_minutes = max(1, min(post.duration_seconds or dj.TRANSCRIBE_MAX_SECONDS,
                                 dj.TRANSCRIBE_MAX_SECONDS) // 60)

    is_opinion = False
    if total > 0 and (len(grey) * 100 / total) >= ratio_threshold:
        is_opinion = True
        post.relegation_reason = f'{len(grey)}/{total} afirmaciones son opinión'
    if len(factual) * minutes_per_factual < tranche_minutes:
        is_opinion = True
        post.relegation_reason = (post.relegation_reason or
            f'Solo {len(factual)} afirmaciones factuales en {tranche_minutes} min')
    if total == 0:
        is_opinion = True
        post.relegation_reason = 'Sin afirmaciones extraíbles'

    if is_opinion:
        # Rescate 1: manipulacion con claims factuales -> verificar con prioridad
        if sweep_result['manipulation'] and factual:
            post.relegation_reason = ''
            return 'FACTUAL'
        # Rescate 2: coincidencia con claim rojo/ambar ya verificado (gratis, local)
        if factual and _matches_known_bad_claim(factual):
            post.relegation_reason = ''
            return 'FACTUAL'
        # Rescate 3 (4.4-G): la SEGUNDA OPINION del modelo del panel. Solo aqui,
        # solo cuando la regla iba a apartar el video, y solo para rescatar.
        if factual and second_opinion_rescues(post, sweep_result):
            post.relegation_reason = ''
            return 'FACTUAL'
        return 'OPINION'
    return 'FACTUAL'


MOCK_CLASSIFY = {'verdict': 'OPINION', 'confidence': 'high',
                 'reason': '[SIMULADO] La regla local ya lo decidió.'}


def second_opinion_rescues(post, sweep_result):
    """4.4-G (orden de David: «desarrolla las funciones»). La rueda «Clasificador»
    del panel de modelos apuntaba a una llamada que no existia. Ahora existe:
    cuando la regla local dice OPINION, el modelo configurado (Sonnet de fabrica)
    lee un resumen del video y da una segunda opinion. Solo un FACTUAL con
    confianza alta rescata; cualquier otra cosa deja la decision de la regla.
    Coste: ~0,04 EUR por hora de video, y solo en los videos que la regla iba a
    apartar. Cualquier fallo del modelo = sin rescate, con WARNING (regla 5.7).
    """
    from apps.agents import client, prompts
    from apps.agents.catalog import model_for
    claims = sweep_result.get('claims') or []
    lineas = [f"- [{c.get('kind', '?')}] {c.get('text', '')}" for c in claims[:120]]
    payload = (f"TITULO: {post.title or '(sin titulo)'}\n"
               f"MOTIVO DE LA REGLA: {post.relegation_reason or '(sin motivo)'}\n"
               f"AFIRMACIONES EXTRAIDAS ({len(claims)}):\n" + '\n'.join(lineas))
    try:
        datos = client.call_json(model_for('classify'), prompts.CLASSIFY_SYSTEM,
                                 payload, max_tokens=300, mock_payload=MOCK_CLASSIFY)
    except Exception as exc:
        logger.warning('Segunda opinión fallida en el post %s: %r', post.pk, exc)
        return False
    if 'error' in datos:
        logger.warning('Segunda opinión fallida en el post %s: %s', post.pk, datos.get('error'))
        return False
    rescata = (str(datos.get('verdict', '')).upper() == 'FACTUAL'
               and str(datos.get('confidence', '')).lower() == 'high')
    logger.info('Segunda opinión del clasificador en el post %s: %s (%s) — %s',
                post.pk, datos.get('verdict'), datos.get('confidence'),
                'RESCATA' if rescata else 'no rescata')
    return rescata


def _matches_known_bad_claim(factual_claims):
    """pgvector coseno sobre pivote EN contra claims RED/AMBER consolidados.
    En mock (sin embeddings reales) devuelve False."""
    from django.conf import settings
    if settings.MOCK_AGENTS:
        return False
    try:
        from apps.wiki.services import find_similar_bad_claim
        return any(find_similar_bad_claim(c['text']) for c in factual_claims)
    except Exception:
        return False
