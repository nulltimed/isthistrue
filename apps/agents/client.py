"""
Cliente unico de la API Anthropic con MODO SIMULADO.
Regla: ANTHROPIC_API_KEY vacia + DEBUG=True => mock automatico ([SIMULADO]).
Flag explicito MOCK_AGENTS=true/false en .env para forzar.

4.4-C — tres cosas nuevas, y las tres son decisiones de David:

1. MEMORIA (cache de prompt). Cuando se manda la transcripcion entera con cada
   afirmacion, el mismo texto viaja 80 veces en un video de una hora. Marcando ese
   bloque como cacheable se paga UNA vez y las relecturas cuestan una decima parte.
   Es la diferencia entre que la transcripcion entera cueste +17% o +160%.
   La memoria caduca en minutos: por eso NO se combina con el envio por lotes.

2. SUPLENTE. Si el modelo configurado no responde, se reintenta con uno de
   calidad SUPERIOR (nunca inferior) y se deja constancia. Un veredicto flojo
   publicado en una web de verificacion hace mas daño que un video que espera;
   un suplente bueno no hace daño ninguno, y evita que la web se quede muerta un
   fin de semana.

3. QUIEN LO DIJO. Toda llamada devuelve, ademas del texto, el modelo que
   realmente respondio. Se guarda con cada veredicto para poder comparar dentro
   de unos meses si Sonnet acierta mas que Opus EN ESTE caso concreto — con datos
   propios, no con lo que diga un blog.
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger('agents.client')


def _apunte_claude(model, usage, busquedas=0):
    """5.3-D: gasto REAL de Anthropic al libro (tokens de usage a precios del
    catalogo + busquedas), como hace qwen._apunte. Nunca rompe la llamada."""
    try:
        from apps.agents.catalog import prices, USD_EUR, USD_PER_SEARCH
        from apps.analysis import costs
        pin, pout = prices(model)
        eur = (getattr(usage, 'input_tokens', 0) * pin
               + getattr(usage, 'output_tokens', 0) * pout) / 1_000_000 * USD_EUR
        if eur > 0:
            costs.record('anthropic', 'analisis', round(eur, 6), model=model)
        if busquedas:
            costs.record('anthropic', 'busqueda',
                         round(busquedas * USD_PER_SEARCH * USD_EUR, 6),
                         model=model)
    except Exception:
        logger.warning('Apunte claude fallido (no bloquea)', exc_info=True)

# Bloques mas cortos que esto no compensa cachear (la escritura cuesta 1,25x).
MIN_CACHE_CHARS = 4000


def call_full(model, system, user_content, max_tokens=2000, mock_payload=None,
              cacheable=None, allow_substitute=True, fallback=''):
    """Devuelve (texto, modelo_usado).

    `cacheable`: bloque largo y REPETIDO entre llamadas (la transcripcion). Va
    delante y marcado, porque la cache cubre el prefijo del mensaje.

    5.2-A (orden de David): si `model` es de la familia Qwen se llama a
    DashScope; si Qwen falla (clave vacia, error de API...) y hay `fallback`
    (el Claude de la rueda «respaldo» del panel), entra el respaldo y se deja
    constancia. La web nunca se queda muda por el cambio de proveedor.
    """
    if settings.MOCK_AGENTS:
        return (json.dumps(mock_payload if mock_payload is not None
                           else {'simulated': True}), model)

    if model.startswith('qwen'):
        from apps.agents import qwen
        try:
            return qwen.call_full(model, system, user_content, max_tokens,
                                  cacheable)
        except Exception as exc:
            logger.warning('Qwen %s falló (%r); respaldo: %s',
                           model, exc, fallback or 'NINGUNO')
            if not fallback:
                raise
            _avisar_suplente(model, fallback)
            model = fallback   # sigue por la via Anthropic de abajo

    import anthropic
    from apps.agents.catalog import substitute

    intentos = [model]
    if allow_substitute:
        sup = substitute(model)
        if sup:
            intentos.append(sup)

    ultimo = None
    for i, modelo in enumerate(intentos):
        try:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            if cacheable and len(cacheable) >= MIN_CACHE_CHARS:
                contenido = [
                    {'type': 'text', 'text': cacheable,
                     'cache_control': {'type': 'ephemeral'}},
                    {'type': 'text', 'text': user_content},
                ]
            else:
                contenido = ([{'type': 'text', 'text': cacheable + '\n\n' + user_content}]
                             if cacheable else user_content)
            msg = client.messages.create(
                model=modelo, max_tokens=max_tokens, system=system,
                messages=[{'role': 'user', 'content': contenido}])
            if i > 0:
                logger.warning('SUPLENTE en uso: %s no respondió, contestó %s',
                               model, modelo)
                _avisar_suplente(model, modelo)
            _apunte_claude(modelo, getattr(msg, 'usage', None))
            return (''.join(b.text for b in msg.content
                            if getattr(b, 'type', '') == 'text'), modelo)
        except Exception as exc:
            ultimo = exc
            logger.warning('Modelo %s falló (%r)', modelo, exc)
    raise ultimo


def call_with_search(model, system, user_content, max_tokens=2000,
                     mock_payload=None, cacheable=None, max_searches=3,
                     allow_substitute=True, fallback=''):
    """4.4-E (decision de David): "todo por Claude". El MODELO busca sus fuentes.

    Devuelve (texto, modelo_usado, n_busquedas). La herramienta de busqueda web
    de Anthropic cuesta 10 $/1.000 consultas mas los tokens de los resultados;
    `max_searches` es el tope por llamada (ajuste web_searches_per_claim).

    Los buscadores dejan de bloquearnos porque ya no vamos de robot anonimo:
    vamos de cliente identificado de Anthropic. A cambio, cada busqueda se paga.
    """
    if settings.MOCK_AGENTS:
        return (json.dumps(mock_payload if mock_payload is not None
                           else {'simulated': True}), model, 0)

    # 5.2-A: la via Qwen — busqueda nativa de DashScope, fuentes incluidas.
    if model.startswith('qwen'):
        from apps.agents import qwen
        try:
            texto, usado, n, fuentes = qwen.call_with_search(
                model, system, user_content, max_tokens, cacheable, max_searches)
            _FUENTES_QWEN.valor = fuentes   # para call_search_json (candado)
            return texto, usado, n
        except Exception as exc:
            logger.warning('Qwen %s falló en búsqueda (%r); respaldo: %s',
                           model, exc, fallback or 'NINGUNO')
            if not fallback:
                raise
            _avisar_suplente(model, fallback)
            model = fallback

    import anthropic
    from apps.agents.catalog import substitute, supports_web

    intentos = [model]
    if allow_substitute:
        sup = substitute(model, need_web=True)
        if sup:
            intentos.append(sup)

    ultimo = None
    for i, modelo in enumerate(intentos):
        if not supports_web(modelo):
            ultimo = RuntimeError(f'{modelo} no permite búsqueda web')
            logger.warning('Modelo %s sin búsqueda web: no sirve para esta tarea', modelo)
            continue
        try:
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            if cacheable and len(cacheable) >= MIN_CACHE_CHARS:
                contenido = [
                    {'type': 'text', 'text': cacheable,
                     'cache_control': {'type': 'ephemeral'}},
                    {'type': 'text', 'text': user_content},
                ]
            else:
                contenido = ([{'type': 'text', 'text': cacheable + '\n\n' + user_content}]
                             if cacheable else user_content)
            msg = client.messages.create(
                model=modelo, max_tokens=max_tokens, system=system,
                tools=[{'type': 'web_search_20250305', 'name': 'web_search',
                        'max_uses': max_searches}],
                messages=[{'role': 'user', 'content': contenido}])
            texto = ''.join(b.text for b in msg.content
                            if getattr(b, 'type', '') == 'text')
            usos = getattr(getattr(msg, 'usage', None), 'server_tool_use', None)
            n_busquedas = getattr(usos, 'web_search_requests', 0) if usos else 0
            if i > 0:
                logger.warning('SUPLENTE en uso: %s no respondió, contestó %s',
                               model, modelo)
                _avisar_suplente(model, modelo)
            _apunte_claude(modelo, getattr(msg, 'usage', None), n_busquedas)
            return (texto, modelo, n_busquedas)
        except Exception as exc:
            ultimo = exc
            logger.warning('Modelo %s falló (%r)', modelo, exc)
    raise ultimo


import threading

_FUENTES_QWEN = threading.local()   # fuentes de search_info del ultimo Qwen


def call_search_json(model, system, user_content, max_tokens=2000,
                     mock_payload=None, cacheable=None, max_searches=3,
                     fallback=''):
    """call_with_search + parseo JSON. Devuelve (datos, modelo_usado).

    5.2-A: si el JSON de Qwen no lista 'sources' pero la busqueda de DashScope
    SI devolvio fuentes (search_info), se rellenan con ellas — el candado «sin
    fuentes no hay color» no depende de que el modelo se acuerde de copiarlas."""
    _FUENTES_QWEN.valor = []
    try:
        raw, usado, _n = call_with_search(model, system, user_content, max_tokens,
                                          mock_payload, cacheable, max_searches,
                                          fallback=fallback)
    except Exception as exc:
        return ({'error': 'api', 'detail': repr(exc)[:200]}, model)
    raw = raw.strip().removeprefix('```json').removesuffix('```').strip()
    # Con la busqueda activada el modelo puede anteponer texto al JSON: se
    # localiza el primer bloque { ... } equilibrado.
    if not raw.startswith('{'):
        inicio = raw.find('{')
        if inicio >= 0:
            raw = raw[inicio:]
    fin = raw.rfind('}')
    if fin > 0:
        raw = raw[:fin + 1]
    try:
        datos = json.loads(raw)
    except json.JSONDecodeError:
        datos = {'error': 'json_parse', 'raw': raw[:500]}
    fuentes = getattr(_FUENTES_QWEN, 'valor', [])
    if isinstance(datos, dict) and not datos.get('sources') and fuentes:
        datos['sources'] = fuentes
    return (datos, usado)


def call(model, system, user_content, max_tokens=2000, mock_payload=None,
         cacheable=None, fallback=''):
    """Compatibilidad: quien no necesite saber quién contestó sigue usando call()."""
    texto, _modelo = call_full(model, system, user_content, max_tokens,
                               mock_payload, cacheable, fallback=fallback)
    return texto


def call_json(model, system, user_content, max_tokens=2000, mock_payload=None,
              cacheable=None, with_model=False, fallback=''):
    """Como call() pero parsea JSON (el system prompt DEBE exigir solo-JSON)."""
    try:
        raw, usado = call_full(model, system, user_content, max_tokens,
                               mock_payload, cacheable, fallback=fallback)
    except Exception as exc:
        salida = {'error': 'api', 'detail': repr(exc)[:200]}
        return (salida, model) if with_model else salida
    raw = raw.strip().removeprefix('```json').removesuffix('```').strip()
    try:
        datos = json.loads(raw)
    except json.JSONDecodeError:
        datos = {'error': 'json_parse', 'raw': raw[:500]}
    return (datos, usado) if with_model else datos


def _avisar_suplente(caido, suplente):
    """Un correo, una vez al día por modelo: enterarse importa, ser bombardeado no."""
    from django.core.cache import cache
    from apps.agents.catalog import label
    if cache.get(f'aviso_suplente_{caido}'):
        return
    cache.set(f'aviso_suplente_{caido}', 1, 86400)
    try:
        from django.core.mail import send_mail
        send_mail(
            f'[esestocierto] {label(caido)} no responde',
            f'El modelo {label(caido)} no ha respondido y el sistema está usando '
            f'{label(suplente)} en su lugar.\n\n'
            f'La web NO se ha parado. Los veredictos emitidos por el suplente quedan '
            f'marcados con su modelo en la ficha de cada afirmación, así que puedes '
            f'reverificarlos después si no te convencen.\n\n'
            f'Revisa el panel de modelos: /panel/modelos/',
            settings.DEFAULT_FROM_EMAIL,
            [getattr(settings, 'ADMIN_ALERT_EMAIL', '')], fail_silently=True)
    except Exception:
        pass
