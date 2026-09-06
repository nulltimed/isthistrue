"""5.2-A/B (orden de David): la familia Qwen3 de Alibaba como motor PRINCIPAL;
Claude queda de respaldo (el dispatch vive en client.py).

DOS PUERTAS, medidas en vivo el 2026-09-06 contra la cuenta real de David:

1) SU TOKEN PLAN (suscripcion Model Studio): host propio
   token-plan.ap-southeast-1.maas.aliyuncs.com, SOLO modo compatible-OpenAI
   (/compatible-mode/v1/chat/completions). La API nativa da «url error» y
   enable_search SE IGNORA (probado: tools=[], el modelo dice «NO PUEDO
   BUSCAR»). Sirve para TODO el volumen; jamas para veredictos con fuentes.

2) PAGO-POR-USO (clave clasica de Model Studio, QWEN_SEARCH_API_KEY): API
   NATIVA en dashscope-intl con enable_search + search_options; las fuentes
   vienen en output.search_info.search_results — lo que exige el candado
   «sin fuentes no hay color». Sin esta clave, las tareas con busqueda caen
   al respaldo Claude y la web sigue entera.

`enable_thinking: false` en las llamadas de volumen: los qwen3.x razonan por
defecto y el razonamiento cuesta tokens y ensucia los JSON.
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger('agents.qwen')

RUTA_COMPAT = '/compatible-mode/v1/chat/completions'
RUTA_NATIVA = '/api/v1/services/aigc/text-generation/generation'


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


def call_full(model, system, user_content, max_tokens=2000, cacheable=None):
    """Volumen por el Token Plan (modo compatible). Devuelve (texto, modelo)."""
    if not settings.QWEN_API_KEY:
        raise RuntimeError('QWEN_API_KEY vacía: Qwen sin configurar')
    texto = (cacheable + '\n\n' + user_content) if cacheable else user_content
    datos = _post(settings.QWEN_BASE_URL, settings.QWEN_API_KEY, RUTA_COMPAT,
                  {'model': model,
                   'messages': [{'role': 'system', 'content': system},
                                {'role': 'user', 'content': texto}],
                   'max_tokens': max_tokens,
                   'enable_thinking': False})
    return datos['choices'][0]['message']['content'], model


def call_with_search(model, system, user_content, max_tokens=2000,
                     cacheable=None, max_searches=3):
    """Busqueda con fuentes por la clave PAGO-POR-USO (API nativa).
    Devuelve (texto, modelo, n_busquedas, fuentes)."""
    if not settings.QWEN_SEARCH_API_KEY:
        raise RuntimeError('QWEN_SEARCH_API_KEY vacía: la búsqueda Qwen exige '
                           'la clave pago-por-uso de Model Studio (el Token '
                           'Plan no busca)')
    texto = (cacheable + '\n\n' + user_content) if cacheable else user_content
    datos = _post(settings.QWEN_SEARCH_BASE_URL, settings.QWEN_SEARCH_API_KEY,
                  RUTA_NATIVA,
                  {'model': model,
                   'input': {'messages': [
                       {'role': 'system', 'content': system},
                       {'role': 'user', 'content': texto}]},
                   'parameters': {'result_format': 'message',
                                  'max_tokens': max_tokens,
                                  'enable_search': True,
                                  'search_options': {
                                      'search_strategy': 'agent',
                                      'forced_search': True,
                                      'enable_source': True,
                                      'enable_citation': True,
                                      'citation_format': 'number'}}},
                  timeout=300)
    resultados = (datos.get('output', {}).get('search_info', {})
                  or {}).get('search_results', []) or []
    fuentes = [{'url': r.get('url', ''), 'title': r.get('title', '')}
               for r in resultados if r.get('url')]
    salida = datos['output']['choices'][0]['message']['content']
    # forced_search: la estrategia agent cuenta como UNA llamada de busqueda
    return salida, model, 1, fuentes
