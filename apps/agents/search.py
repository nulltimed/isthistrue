"""SearXNG autoalojado con tope ADAPTATIVO: 3 normal, hasta 5 si ambiguo (Haiku decide)."""
import httpx
from django.conf import settings


def search(query, max_results=5):
    if settings.MOCK_AGENTS:
        return [{'url': 'https://example.org/fuente-simulada',
                 'title': '[SIMULADO] Fuente de ejemplo', 'content': 'Resultado ficticio.'}]
    try:
        r = httpx.get(f'{settings.SEARXNG_URL}/search',
                      params={'q': query, 'format': 'json'}, timeout=15)
        return r.json().get('results', [])[:max_results]
    except Exception:
        return []


def budget_for_claim(claim):
    return (settings.SEARCHES_PER_CLAIM_AMBIGUOUS if claim.get('ambiguous')
            else settings.SEARCHES_PER_CLAIM)
