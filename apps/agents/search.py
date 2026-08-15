"""SearXNG autoalojado con tope ADAPTATIVO: 3 normal, hasta 5 si ambiguo (Haiku decide)."""
import logging

import httpx
from django.conf import settings

logger = logging.getLogger('agents.search')


def search_with_status(query, max_results=5):
    """Devuelve (resultados, ok). ok=False = la BUSQUEDA fallo (SearXNG caido,
    403 por formato JSON deshabilitado, timeout...). Regla 5.7: jamas en silencio
    — el 403 masivo del 2026-08-15 emitio veredictos SIN FUENTES sin avisar."""
    if settings.MOCK_AGENTS:
        return ([{'url': 'https://example.org/fuente-simulada',
                  'title': '[SIMULADO] Fuente de ejemplo', 'content': 'Resultado ficticio.'}], True)
    try:
        r = httpx.get(f'{settings.SEARXNG_URL}/search',
                      params={'q': query, 'format': 'json'}, timeout=15)
        if r.status_code != 200:
            logger.warning('Búsqueda de fuentes fallida (HTTP %s de SearXNG): %.60s',
                           r.status_code, query)
            return ([], False)
        return (r.json().get('results', [])[:max_results], True)
    except Exception as exc:
        logger.warning('Búsqueda de fuentes fallida (%r): %.60s', exc, query)
        return ([], False)


def search(query, max_results=5):
    """Compatibilidad: quien no necesite el estado sigue usando search()."""
    results, _ok = search_with_status(query, max_results)
    return results


def budget_for_claim(claim):
    return (settings.SEARCHES_PER_CLAIM_AMBIGUOUS if claim.get('ambiguous')
            else settings.SEARCHES_PER_CLAIM)
