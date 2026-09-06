"""5.2-A (orden de David, 2026-09-06): la familia Qwen3 de Alibaba como motor
PRINCIPAL; Claude queda de respaldo (el dispatch vive en client.py).

API nativa de DashScope (portal internacional, Singapur) — NO el modo
compatible-OpenAI, porque ese no devuelve las fuentes de la busqueda web y
aqui rige el candado «sin fuentes no hay color». Contrato verificado contra la
documentacion viva el 2026-09-06:

  POST {QWEN_BASE_URL}/api/v1/services/aigc/text-generation/generation
  Authorization: Bearer $QWEN_API_KEY
  body: {model, input:{messages}, parameters:{result_format:'message', ...}}
  busqueda: parameters.enable_search=true + search_options{enable_source,...}
  fuentes: output.search_info.search_results[] -> {title, url}
  respuesta: output.choices[0].message.content

La busqueda con estrategia 'agent' cuesta 10 $/1.000 llamadas (como la de
Anthropic) mas los tokens.
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger('agents.qwen')

RUTA = '/api/v1/services/aigc/text-generation/generation'


def _post(body, timeout=180):
    resp = requests.post(
        settings.QWEN_BASE_URL.rstrip('/') + RUTA,
        headers={'Authorization': f'Bearer {settings.QWEN_API_KEY}',
                 'Content-Type': 'application/json'},
        json=body, timeout=timeout)
    resp.raise_for_status()
    datos = resp.json()
    if datos.get('code'):    # DashScope devuelve 200 con code de error a veces
        raise RuntimeError(f"DashScope {datos.get('code')}: "
                           f"{str(datos.get('message'))[:200]}")
    return datos


def _mensajes(system, user_content, cacheable):
    texto = (cacheable + '\n\n' + user_content) if cacheable else user_content
    return [{'role': 'system', 'content': system},
            {'role': 'user', 'content': texto}]


def _texto_de(datos):
    return datos['output']['choices'][0]['message']['content']


def call_full(model, system, user_content, max_tokens=2000, cacheable=None):
    """Devuelve (texto, modelo). Sin clave configurada, falla YA (el respaldo
    Claude entra desde client.py; el sistema jamas se queda mudo)."""
    if not settings.QWEN_API_KEY:
        raise RuntimeError('QWEN_API_KEY vacía: Qwen sin configurar')
    datos = _post({'model': model,
                   'input': {'messages': _mensajes(system, user_content, cacheable)},
                   'parameters': {'result_format': 'message',
                                  'max_tokens': max_tokens}})
    return _texto_de(datos), model


def call_with_search(model, system, user_content, max_tokens=2000,
                     cacheable=None, max_searches=3):
    """Devuelve (texto, modelo, n_busquedas, fuentes) — fuentes de
    output.search_info, para reforzar el candado «sin fuentes no hay color»."""
    if not settings.QWEN_API_KEY:
        raise RuntimeError('QWEN_API_KEY vacía: Qwen sin configurar')
    datos = _post({'model': model,
                   'input': {'messages': _mensajes(system, user_content, cacheable)},
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
    # forced_search: la estrategia agent cuenta como UNA llamada de busqueda
    return _texto_de(datos), model, 1, fuentes
