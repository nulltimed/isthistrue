"""5.5-D (orden de David): LA VISTA — contrastar lo que se VE con lo que se DICE.

Cuando una afirmacion/opinion hace referencia visual («este grafico», «como
ven en pantalla»...), se extrae EL FOTOGRAMA del segundo exacto — sin
descargar el video: yt-dlp entrega la URL directa del stream y ffmpeg lee
solo ese instante — y los ojos de la familia (qwen3-vl, rueda «La vista» del
panel) describen si la imagen sostiene, contradice o no aporta a lo dicho.
El hallazgo se INYECTA en el expediente del verificador: es contexto para el
veredicto, no un veredicto en si. Fail-soft integral: cualquier fallo deja el
analisis como estaba. Con el vigilante de China, models_for_post entrega los
ojos de Claude en los videos que tocan a China.
"""
import base64
import json
import logging
import re
import subprocess
import tempfile

import requests
from django.conf import settings

logger = logging.getLogger('agents.vision')

# Señales de que la frase apela a lo que se ve en pantalla.
VISUAL_RX = re.compile(
    r'\b(gr[aá]fic[oa]s?|en (la )?pantalla|como (pueden )?ver|esta (tabla|imagen'
    r'|cifra|curva|foto)|este (dato|mapa|cartel|titular)|aqu[ií] (vemos|se ve)'
    r'|miren?|observen|se muestra|on (the )?screen|this (chart|graph|figure'
    r'|image|slide)|as you can see|look at (this|the))\b', re.I)

VISION_SYSTEM = """Eres los ojos de una plataforma de fact-checking. Recibes UN \
fotograma de un video y la frase que se decia en ese instante. Responde SOLO \
JSON: {"veredicto_visual": "sostiene|contradice|no_aporta", \
"detalle": "<que muestra la imagen y su relacion con lo dicho, 2-3 frases>"}. \
Se literal con lo que muestra la imagen (cifras, rotulos, ejes); jamas \
inventes lo que no se lea con claridad."""


def procede(texto):
    return bool(VISUAL_RX.search(texto or ''))


def fotograma_b64(post, segundo):
    """El fotograma del segundo dado, en JPEG base64 — SIN descargar el video."""
    stream = subprocess.run(
        ['yt-dlp', '-g', '-f', 'best[height<=480]/worst', post.url],
        capture_output=True, text=True, timeout=60)
    url = (stream.stdout or '').strip().split('\n')[0]
    if not url.startswith('http'):
        raise RuntimeError(f'yt-dlp sin stream: {stream.stderr[:150]}')
    with tempfile.NamedTemporaryFile(suffix='.jpg') as f:
        subprocess.run(['ffmpeg', '-y', '-ss', str(max(0, int(segundo))),
                        '-i', url, '-frames:v', '1', '-q:v', '4', f.name],
                       capture_output=True, timeout=90, check=True)
        datos = open(f.name, 'rb').read()
    if len(datos) < 1000:
        raise RuntimeError('fotograma vacío')
    return base64.b64encode(datos).decode()


def _mirar_qwen(model, b64, frase):
    from apps.agents import qwen
    datos = qwen._post(settings.QWEN_BASE_URL, settings.QWEN_API_KEY,
                       qwen.RUTA_CHAT,
                       {'model': model,
                        'messages': [
                            {'role': 'system', 'content': VISION_SYSTEM},
                            {'role': 'user', 'content': [
                                {'type': 'image_url', 'image_url': {
                                    'url': f'data:image/jpeg;base64,{b64}'}},
                                {'type': 'text',
                                 'text': f'LO QUE SE DICE: «{frase[:400]}»'}]}],
                        'max_tokens': 300, 'enable_thinking': False},
                       timeout=120)
    qwen._apunte(model, datos.get('usage') or {})
    return datos['choices'][0]['message']['content']


def _mirar_claude(model, b64, frase):
    import anthropic
    from apps.agents.client import _apunte_claude
    cli = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = cli.messages.create(
        model=model, max_tokens=300, system=VISION_SYSTEM,
        messages=[{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64',
                                         'media_type': 'image/jpeg',
                                         'data': b64}},
            {'type': 'text', 'text': f'LO QUE SE DICE: «{frase[:400]}»'}]}])
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
    try:
        b64 = fotograma_b64(post, segundo)
    except Exception as exc:
        logger.warning('La vista: sin fotograma en el post %s s%s (%r)',
                       post.pk, segundo, exc)
        return None
    modelo, respaldo = models_for_post('vision', post)
    for m in [modelo, respaldo]:
        if not m:
            continue
        try:
            crudo = (_mirar_qwen if provider(m) == 'qwen'
                     else _mirar_claude)(m, b64, frase)
            crudo = crudo.strip().removeprefix('```json').removesuffix('```').strip()
            datos = json.loads(crudo[crudo.find('{'):crudo.rfind('}') + 1])
            if datos.get('veredicto_visual'):
                datos['modelo'] = m
                return datos
        except Exception as exc:
            logger.warning('La vista fallo con %s en el post %s (%r)',
                           m, post.pk, exc)
    return None
