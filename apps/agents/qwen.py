"""5.2-A/B/C (orden de David): la familia Qwen3 de Alibaba como motor
PRINCIPAL; Claude queda de respaldo (el dispatch vive en client.py).

TRES generaciones de contrato medidas EN VIVO contra la cuenta real
(2026-09-06, la leccion del 4.10: la API viva manda, no el folleto):

- Claves sk-sp- (Token Plan): host propio, sin busqueda. RETIRADA por David.
- Claves sk-ws- (workspace, pago-por-uso): dashscope-intl SOLO en modo
  compatible-OpenAI (la API nativa clasica responde «url error»).
- La BUSQUEDA con fuentes: API Responses (/compatible-mode/v1/responses) con
  `tools: [{"type": "web_search"}]` al estilo OpenAI — el enable_search del
  folleto DashScope se ignora por esta puerta. Las fuentes llegan en
  output[].web_search_call.action.sources[] (urls).

Costes REALES: cada llamada registra en el libro de cuentas (CostEntry,
proveedor 'qwen') los tokens de `usage` a precios del catalogo, y las
busquedas a USD_PER_SEARCH. El post en curso se engancha solo (thread-local
de apps.analysis.costs).
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger('agents.qwen')

RUTA_CHAT = '/compatible-mode/v1/chat/completions'
RUTA_RESPONSES = '/compatible-mode/v1/responses'


def _post(base, key, ruta, body, timeout=180):
    resp = requests.post(base.rstrip('/') + ruta,
                         headers={'Authorization': f'Bearer {key}',
                                  'Content-Type': 'application/json'},
                         json=body, timeout=timeout)
    resp.raise_for_status()
    datos = resp.json()
    if datos.get('code'):    # DashScope devuelve 200 con code de error a veces
        raise RuntimeError(f"DashScope {datos.get('code')}: "
                           f"{str(datos.get('message'))[:200]}")
    return datos


def _apunte(model, usage, busquedas=0):
    """Gasto REAL al libro de cuentas: tokens de usage a precios del catalogo
    + busquedas. Nunca rompe la llamada que lo origina."""
    try:
        from apps.agents.catalog import prices, USD_EUR, USD_PER_SEARCH
        from apps.analysis import costs
        pin, pout = prices(model)
        eur = ((usage.get('input_tokens', 0) or usage.get('prompt_tokens', 0)) * pin
               + (usage.get('output_tokens', 0) or usage.get('completion_tokens', 0)) * pout
               ) / 1_000_000 * USD_EUR
        if eur > 0:
            costs.record('qwen', 'analisis', round(eur, 6), model=model)
        if busquedas:
            costs.record('qwen', 'busqueda',
                         round(busquedas * USD_PER_SEARCH * USD_EUR, 6),
                         model=model)
    except Exception:
        logger.warning('Apunte qwen fallido (no bloquea)', exc_info=True)


def call_full(model, system, user_content, max_tokens=2000, cacheable=None):
    """Devuelve (texto, modelo). enable_thinking apagado: los qwen3.x razonan
    por defecto y el razonamiento cuesta tokens y ensucia los JSON."""
    if not settings.QWEN_API_KEY:
        raise RuntimeError('QWEN_API_KEY vacía: Qwen sin configurar')
    texto = (cacheable + '\n\n' + user_content) if cacheable else user_content
    datos = _post(settings.QWEN_BASE_URL, settings.QWEN_API_KEY, RUTA_CHAT,
                  {'model': model,
                   'messages': [{'role': 'system', 'content': system},
                                {'role': 'user', 'content': texto}],
                   'max_tokens': max_tokens,
                   'enable_thinking': False})
    _apunte(model, datos.get('usage') or {})
    return datos['choices'][0]['message']['content'], model


def call_with_search(model, system, user_content, max_tokens=2000,
                     cacheable=None, max_searches=3):
    """Busqueda con fuentes por la API Responses (tools estilo OpenAI).
    Devuelve (texto, modelo, n_busquedas, fuentes)."""
    key = settings.QWEN_SEARCH_API_KEY or settings.QWEN_API_KEY
    if not key:
        raise RuntimeError('Sin clave Qwen para buscar (QWEN_SEARCH_API_KEY '
                           'ni QWEN_API_KEY)')
    texto = (cacheable + '\n\n' + user_content) if cacheable else user_content
    datos = _post(settings.QWEN_SEARCH_BASE_URL, key, RUTA_RESPONSES,
                  {'model': model,
                   'instructions': system,
                   'input': texto,
                   'max_output_tokens': max_tokens,
                   'tools': [{'type': 'web_search'}]},
                  timeout=300)
    salida, fuentes, n_busquedas = '', [], 0
    vistos = set()
    for item in datos.get('output', []):
        if item.get('type') == 'message':
            for c in item.get('content', []):
                salida += str(c.get('text', ''))
        elif item.get('type') == 'web_search_call':
            n_busquedas += 1
            for f in (item.get('action') or {}).get('sources', []) or []:
                url = f.get('url', '')
                if url and url not in vistos:
                    vistos.add(url)
                    fuentes.append({'url': url, 'title': f.get('title', '')})
    _apunte(model, datos.get('usage') or {}, busquedas=n_busquedas)
    return salida, model, n_busquedas, fuentes[:12]
