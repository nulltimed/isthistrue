"""SearXNG autoalojado con tope ADAPTATIVO: 3 normal, hasta 5 si ambiguo (Haiku decide).

4.4-B — EL FALLO DE RAIZ DEL SEMAFORO. Los logs del 2026-08-23 lo destaparon:

    SearxEngineTooManyRequestsException: Too many request (suspended_time=180)

Un analisis lanza de 3 a 5 busquedas POR AFIRMACION; con 22 frases factuales son
mas de 100 consultas en pocos minutos. A la decima, los buscadores cortan el grifo
y suspenden el motor tres minutos. Y entonces SearXNG responde **HTTP 200 con la
lista vacia**.

El codigo miraba el codigo de estado: 200 = "todo bien". Resultado: 96 de 96
afirmaciones marcadas con `sources_ok=True` mientras el verificador escribia "no se
aportan resultados de busqueda". Se pagaba Sonnet para que dijera que no tenia
datos, y salia gris.

Es el mismo fallo del 403 masivo de agosto, pero DISFRAZADO DE EXITO — y por eso
mucho peor: aquel al menos gritaba.

Reglas nuevas:
  · vacio == fallo (`ok=False`), sin excepciones;
  · si el motor esta suspendido, se ESPERA y se reintenta, no se ametralla;
  · las consultas van primero a las fuentes oficiales (decision de David).
"""
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger('agents.search')

# Dominios que mandan. Lista viva en el panel ('official_sources'); esto es la
# siembra. Prensa NUNCA es base unica de un verde o un rojo (decision de David).
OFFICIAL_FALLBACK = ('ine.es', 'europa.eu', 'boe.es', 'bde.es', 'aemet.es',
                     'seg-social.es', 'sepe.es', 'who.int', 'un.org', 'oecd.org')


def official_domains():
    """Lista viva de fuentes oficiales, editable en el panel."""
    from apps.panel.models import SystemSetting
    crudo = (SystemSetting.get_str('official_sources', '') or '').strip()
    if not crudo:
        return list(OFFICIAL_FALLBACK)
    return [d.strip() for d in crudo.replace('\n', ',').split(',') if d.strip()]


def _one_call(query, timeout=15):
    """Una llamada. Devuelve (resultados, motivo) — motivo '' significa que fue bien."""
    try:
        r = httpx.get(f'{settings.SEARXNG_URL}/search',
                      params={'q': query, 'format': 'json'}, timeout=timeout)
    except Exception as exc:
        return ([], f'excepcion:{exc!r}')
    if r.status_code != 200:
        return ([], f'http:{r.status_code}')
    try:
        datos = r.json()
    except Exception:
        return ([], 'json_ilegible')
    resultados = datos.get('results', []) or []
    if not resultados:
        # 200 y cero resultados = motores suspendidos por exceso de peticiones,
        # o consulta imposible. En ninguno de los dos casos es un exito.
        return ([], 'vacio')
    return (resultados, '')


def search_with_status(query, max_results=5, official_first=True):
    """Devuelve (resultados, ok).

    ok=False significa que NO hay base documental para emitir veredicto. Quien
    llame DEBE abstenerse de pintar semaforo (verdict.py lo hace).
    """
    if settings.MOCK_AGENTS:
        return ([{'url': 'https://example.org/fuente-simulada',
                  'title': '[SIMULADO] Fuente de ejemplo', 'content': 'Resultado ficticio.'}], True)

    from apps.panel.models import SystemSetting
    reintentos = max(0, SystemSetting.get_int('search_retries', 2))
    espera = max(1, SystemSetting.get_int('search_retry_seconds', 20))

    # 4.4-B (decision de David): organismos oficiales primero, prensa como apoyo.
    intentos = []
    if official_first:
        for dominio in official_domains()[:3]:
            intentos.append(f'site:{dominio} {query}')
    intentos.append(query)

    ultimo_motivo = 'sin_intentos'
    for consulta in intentos:
        for vuelta in range(reintentos + 1):
            resultados, motivo = _one_call(consulta)
            if resultados:
                return (resultados[:max_results], True)
            ultimo_motivo = motivo
            if motivo == 'vacio' and vuelta < reintentos:
                # Motores suspendidos: esperar es la unica salida que funciona.
                logger.warning('Búsqueda vacía (motores suspendidos), espero %ss: %.60s',
                               espera, consulta)
                time.sleep(espera)
                continue
            break
    logger.warning('Búsqueda de fuentes SIN RESULTADOS (%s): %.60s', ultimo_motivo, query)
    return ([], False)


def search(query, max_results=5):
    """Compatibilidad: quien no necesite el estado sigue usando search()."""
    results, _ok = search_with_status(query, max_results)
    return results


def budget_for_claim(claim):
    return (settings.SEARCHES_PER_CLAIM_AMBIGUOUS if claim.get('ambiguous')
            else settings.SEARCHES_PER_CLAIM)
