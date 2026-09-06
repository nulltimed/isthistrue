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
            # 5.14-C (cazado en el relanzamiento global): YouTube ya solo
            # sirve streams ADAPTATIVOS y 'best[height<=480]' devolvia
            # «Requested format is not available» — los ojos quedaban ciegos
            # en silencio. Para UN fotograma basta el video solo (bv*).
            ['yt-dlp', '-g', '-f', 'bv*[height<=480]/bv*/best/worst', post.url],
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
    """Los fotogramas alrededor del instante (retardo humano), en JPEG base64.
    Devuelve (fotos, indice del fotograma del segundo EXACTO)."""
    url = _stream_url(post)
    ya, fotos, idx_exacto = set(), [], 0
    for s in (segundo - lag, segundo, segundo + lag):
        s = max(0, int(s))
        if s in ya:
            continue
        ya.add(s)
        try:
            b = _un_fotograma(url, s)
        except Exception as exc:
            logger.warning('La vista: sin fotograma s%s del post %s (%r)',
                           s, post.pk, exc)
            continue
        if s == max(0, int(segundo)):
            idx_exacto = len(fotos)
        fotos.append(b)
    if not fotos:
        raise RuntimeError('ningún fotograma')
    return fotos, idx_exacto


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
        b64s, idx_exacto = fotogramas_b64(post, segundo, lag)
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
                # 5.8: el fotograma del segundo exacto viaja con el hallazgo,
                # para quedar registrado en la wiki si el claim lo involucra.
                datos['fotograma_b64'] = b64s[idx_exacto]
                datos['segundo'] = max(0, int(segundo))
                return datos
        except Exception as exc:
            logger.warning('La vista fallo con %s en el post %s (%r)',
                           m, post.pk, exc)
    return None


def registrar(claim, hallazgo):
    """5.8 (orden expresa de David, 2026-09-07): «cada claim, verdadero, gris
    o falso, que involucre una imagen del propio vídeo analizado, debe quedar
    registrado en la wiki con la imagen en cuestión». Un claim la INVOLUCRA
    cuando la vista miro y APORTO (sostiene o contradice); con no_aporta la
    imagen no guarda relacion y no se registra. Cita visual acotada: un JPEG."""
    import base64
    from django.core.files.base import ContentFile
    if not claim or not hallazgo:
        return False
    if hallazgo.get('veredicto_visual') not in ('sostiene', 'contradice'):
        return False
    b64 = hallazgo.get('fotograma_b64')
    if not b64:
        return False
    try:
        claim.frame_image.save(f'claim-{claim.pk}.jpg',
                               ContentFile(base64.b64decode(b64)), save=False)
        claim.frame_second = hallazgo.get('segundo')
        claim.frame_note = (f"La pantalla {hallazgo['veredicto_visual'].upper()} "
                            f"lo dicho — {hallazgo.get('detalle') or ''}")[:500]
        claim.save(update_fields=['frame_image', 'frame_second', 'frame_note'])
        return True
    except Exception as exc:
        logger.warning('5.8: no pude registrar el fotograma del claim %s (%r)',
                       claim.pk, exc)
        return False
