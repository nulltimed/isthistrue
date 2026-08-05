"""
Algoritmo FACTUAL vs OPINION (README v2 §4). Umbrales en SystemSetting (panel).
OPINION si CUALQUIERA de:
  - ratio: claims grises >= 70% del total
  - densidad: < 1 claim factual por cada 5 minutos de tramo
Con dos excepciones que RESCATAN al flujo completo:
  - manipulacion CON claims factuales (direccion invertida del castigo)
  - algun claim factual coincide con claim rojo/ambar ya en la wiki (embeddings, gratis)
"""
from apps.panel.models import SystemSetting


def classify(post, sweep_result):
    claims = sweep_result['claims']
    factual = [c for c in claims if c.get('kind') == 'FACTUAL']
    grey = [c for c in claims if c.get('kind') == 'OPINION']
    total = len(claims)

    ratio_threshold = SystemSetting.get_int('opinion_ratio_percent', 70)
    minutes_per_factual = SystemSetting.get_int('minutes_per_factual_claim', 5)
    tranche_minutes = max(1, min(post.duration_seconds, 1200) // 60) or 20

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
