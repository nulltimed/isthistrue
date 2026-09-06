"""5.5-D/G (ordenes de David): LA VISTA — contrastar lo que se VE con lo que se DICE.

5.5-G: el analisis visual es COMPLETO — cada afirmacion/opinion analizada pasa
por los ojos, sin esperar palabras clave («el análisis del vídeo debe ser
completo, no sólo esperando a palabras clave»). Y como entre la pantalla y la
voz hay RETARDO HUMANO (la imagen puede aparecer antes o despues de decirse),
se capturan TRES fotogramas: antes, durante y despues del instante
(`vision_lag_seconds` del panel, 4 s de fabrica).

Sin descargar el video: yt-dlp entrega la URL directa del stream (una vez por
post, cacheada) y ffmpeg lee solo esos instantes. Los ojos de la familia
(qwen3-vl, rueda «La vista» del panel) describen si alguna de las imagenes
sostiene, contradice o no aporta a lo dicho. El hallazgo se INYECTA en el
expediente del verificador: es contexto para el veredicto, no un veredicto en
si. Fail-soft integral: cualquier fallo deja el analisis como estaba. Con el
vigilante de China, models_for_post entrega los ojos de Claude en los videos
que tocan a China. Apagado general: `vision_pass = 0` en el panel.
"""
import base64
import json
import logging
import subprocess
import tempfile

from django.conf import settings

logger = logging.getLogger('agents.vision')

VISION_SYSTEM = """Eres los ojos de una plataforma de fact-checking. Recibes \
FOTOGRAMAS consecutivos de un video (antes, durante y despues del instante en \
que se dice una frase — entre la pantalla y la voz hay retardo humano: lo \
mostrado puede ir adelantado o retrasado respecto a lo dicho) y la frase. \
Responde SOLO JSON: {"veredicto_visual": "sostiene|contradice|no_aporta", \
"detalle": "<que muestra la pantalla y su relacion con lo dicho, 2-3 frases>"}. \
Se literal con lo que muestran las imagenes (cifras, rotulos, ejes); jamas \
inventes lo que no se lea con claridad. Si ningun fotograma guarda relacion \
con la frase: no_aporta."""

# URL directa del stream por post: se pide UNA vez y las ~decenas de claims
# del mismo video la reutilizan (caducan en horas; un analisis dura minutos).
_STREAMS = {}


def _stream_url(post):
    if post.pk not in _STREAMS:
        r = subprocess.run(
            ['yt-dlp', '-g', '-f', 'best[height<=480]/worst', post.url],
            capture_output=True, text=True, timeout=60)
        url = (r.stdout or '').strip().split('\n')[0]
        if not url.startswith('http'):
            raise RuntimeError(f'yt-dlp sin stream: {r.stderr[:150]}')
        _STREAMS[post.pk] = url
    return _STREAMS[post.pk]


def _un_fotograma(url, segundo):
    with tempfile.NamedTemporaryFile(suffix='.jpg') as f:
        subprocess.run(['ffmpeg', '-y', '-ss', str(max(0, int(segundo))),
                        '-i', url, '-frames:v', '1', '-q:v', '4', f.name],
                       capture_output=True, timeout=90, check=True)
        datos = open(f.name, 'rb').read()
    if len(datos) < 1000:
        raise RuntimeError('fotograma vacío')
    return base64.b64encode(datos).decode()


def fotogramas_b64(post, segundo, lag):
    """Los fotogramas alrededor del instante (retardo humano), en JPEG base64."""
    url = _stream_url(post)
    ya, fotos = set(), []
    for s in (segundo - lag, segundo, segundo + lag):
        s = max(0, int(s))
        if s in ya:
            continue
        ya.add(s)
        try:
            fotos.append(_un_fotograma(url, s))
        except Exception as exc:
            logger.warning('La vista: sin fotograma s%s del post %s (%r)',
                           s, post.pk, exc)
    if not fotos:
        raise RuntimeError('ningún fotograma')
    return fotos


def _mirar_qwen(model, b64s, frase):
    from apps.agents import qwen
    contenido = [{'type': 'image_url',
                  'image_url': {'url': f'data:image/jpeg;base64,{b}'}}
                 for b in b64s]
    contenido.append({'type': 'text',
                      'text': f'LO QUE SE DICE: «{frase[:400]}»'})
    datos = qwen._post(settings.QWEN_BASE_URL, settings.QWEN_API_KEY,
                       qwen.RUTA_CHAT,
                       {'model': model,
                        'messages': [
                            {'role': 'system', 'content': VISION_SYSTEM},
                            {'role': 'user', 'content': contenido}],
                        'max_tokens': 300, 'enable_thinking': False},
                       timeout=120)
    qwen._apunte(model, datos.get('usage') or {})
    return datos['choices'][0]['message']['content']


def _mirar_claude(model, b64s, frase):
    import anthropic
    from apps.agents.client import _apunte_claude
    cli = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    contenido = [{'type': 'image', 'source': {'type': 'base64',
                                              'media_type': 'image/jpeg',
                                              'data': b}} for b in b64s]
    contenido.append({'type': 'text', 'text': f'LO QUE SE DICE: «{frase[:400]}»'})
    msg = cli.messages.create(
        model=model, max_tokens=300, system=VISION_SYSTEM,
        messages=[{'role': 'user', 'content': contenido}])
    _apunte_claude(model, getattr(msg, 'usage', None))
    return ''.join(b.text for b in msg.content
                   if getattr(b, 'type', '') == 'text')


def mirar(post, frase, segundo):
    """Devuelve el dict del veredicto visual, o None (fail-soft)."""
    from apps.panel.models import SystemSetting
    from apps.agents.catalog import models_for_post, provider
    if SystemSetting.get_int('vision_pass', 1) <= 0:
        return None
    if post.platform not in ('youtube', 'twitch', 'spotify'):
        return None
    lag = max(0, SystemSetting.get_int('vision_lag_seconds', 4))
    try:
        b64s = fotogramas_b64(post, segundo, lag)
    except Exception as exc:
        logger.warning('La vista: sin fotogramas en el post %s s%s (%r)',
                       post.pk, segundo, exc)
        return None
    modelo, respaldo = models_for_post('vision', post)
    for m in [modelo, respaldo]:
        if not m:
            continue
        try:
            crudo = (_mirar_qwen if provider(m) == 'qwen'
                     else _mirar_claude)(m, b64s, frase)
            crudo = crudo.strip().removeprefix('```json').removesuffix('```').strip()
            datos = json.loads(crudo[crudo.find('{'):crudo.rfind('}') + 1])
            if datos.get('veredicto_visual'):
                datos['modelo'] = m
                return datos
        except Exception as exc:
            logger.warning('La vista fallo con %s en el post %s (%r)',
                           m, post.pk, exc)
    return None
