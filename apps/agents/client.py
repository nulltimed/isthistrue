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

# Bloques mas cortos que esto no compensa cachear (la escritura cuesta 1,25x).
MIN_CACHE_CHARS = 4000


def call_full(model, system, user_content, max_tokens=2000, mock_payload=None,
              cacheable=None, allow_substitute=True):
    """Devuelve (texto, modelo_usado).

    `cacheable`: bloque largo y REPETIDO entre llamadas (la transcripcion). Va
    delante y marcado, porque la cache cubre el prefijo del mensaje.
    """
    if settings.MOCK_AGENTS:
        return (json.dumps(mock_payload if mock_payload is not None
                           else {'simulated': True}), model)

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
            return (''.join(b.text for b in msg.content
                            if getattr(b, 'type', '') == 'text'), modelo)
        except Exception as exc:
            ultimo = exc
            logger.warning('Modelo %s falló (%r)', modelo, exc)
    raise ultimo


def call(model, system, user_content, max_tokens=2000, mock_payload=None,
         cacheable=None):
    """Compatibilidad: quien no necesite saber quién contestó sigue usando call()."""
    texto, _modelo = call_full(model, system, user_content, max_tokens,
                               mock_payload, cacheable)
    return texto


def call_json(model, system, user_content, max_tokens=2000, mock_payload=None,
              cacheable=None, with_model=False):
    """Como call() pero parsea JSON (el system prompt DEBE exigir solo-JSON)."""
    try:
        raw, usado = call_full(model, system, user_content, max_tokens,
                               mock_payload, cacheable)
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
            f'[isthistrue] {label(caido)} no responde',
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
