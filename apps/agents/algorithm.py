"""
Algoritmo FACTUAL vs OPINION (README v2 §4). Umbrales en SystemSetting (panel).
5.27-A (orden de David): la etiqueta del VIDEO ENTERO ya no decide nada del
flujo (la puerta al trabajo 2 es votos + hablantes para todos); queda como
pista «parece opinión» para moderación. La etiqueta de CADA FRASE la pone el
barrido (sweep) y sigue viéndose en la transcripción.
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
        # (El «rescate 3» —la segunda opinion de un modelo, 4.4-G— se retiro en
        # el 5.27-D: desde entonces la etiqueta no decide el flujo, solo avisa a
        # moderacion, y la rueda del panel pasa al bibliotecario de categorias.)
        return 'OPINION'
    return 'FACTUAL'


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
