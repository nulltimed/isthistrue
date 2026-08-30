"""4.7-B · Motor AssemblyAI: transcripcion Y voces cosidas de fabrica.

Decision de David (2026-08-30): tras medir el techo de coser whisper+pyannote a
mano (docs/60), se prueba el modelo CONJUNTO — cada palabra llega ya con su
hablante, sin costuras nuestras. Cadena aprobada: AssemblyAI → GPU Runpod →
CPU (regla 5.7: cada eslabon que falla cede al siguiente con WARNING, jamas
rompe). Modelo: universal-3-5-pro con retorno a universal-2 (el mas potente,
eleccion de David). Coste: ~0,10-0,15 $ por video de 23 min, del saldo AAI.

Autenticacion: header `authorization` con la clave CRUDA (sin Bearer) — la
peculiaridad numero uno de esta API segun su propio manual.
"""
import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger('agents.assembly')

BASE = 'https://api.assemblyai.com'


def _activo():
    from apps.panel.models import SystemSetting
    return bool(settings.ASSEMBLYAI_API_KEY) and \
        SystemSetting.get_int('audio_engine_assemblyai', 1) > 0


def transcribe_diarize(audio_path, hint=None):
    """Sube el audio y devuelve la lista de intervenciones YA atribuidas, en el
    formato local ({start_seconds, end_seconds, text, speaker_label, words}),
    o None ante cualquier impedimento: el llamante DEBE caer al motor GPU."""
    if not _activo():
        return None
    H = {'authorization': settings.ASSEMBLYAI_API_KEY}
    try:
        with open(audio_path, 'rb') as f:
            up = httpx.post(f'{BASE}/v2/upload', headers=H, content=f.read(),
                            timeout=300)
        url = up.json().get('upload_url')
        if not url:
            logger.warning('AssemblyAI: subida sin upload_url (HTTP %s)',
                           up.status_code)
            return None
        sub = httpx.post(f'{BASE}/v2/transcript', timeout=60,
                         headers={**H, 'content-type': 'application/json'},
                         json={'audio_url': url,
                               'speech_models': ['universal-3-5-pro',
                                                 'universal-2'],
                               'speaker_labels': True,
                               'language_detection': True,
                               # 4.8-A: la pista de voces que ya sabemos
                               # (moderacion o relanzamiento) viaja al motor —
                               # sin ella invento un fantasma en el post 5.
                               **_pista_aai(hint)})
        tid = sub.json().get('id')
        if not tid:
            logger.warning('AssemblyAI: submit sin id (HTTP %s): %s',
                           sub.status_code, str(sub.text)[:150])
            return None
        limite = time.monotonic() + settings.ASSEMBLYAI_TIMEOUT
        datos = {}
        while time.monotonic() < limite:
            time.sleep(3)
            datos = httpx.get(f'{BASE}/v2/transcript/{tid}', headers=H,
                              timeout=30).json()
            if datos.get('status') in ('completed', 'error'):
                break
        if datos.get('status') != 'completed':
            logger.warning('AssemblyAI: trabajo %s -> %s (%s)', tid,
                           datos.get('status'), str(datos.get('error'))[:150])
            return None
        return _map(datos)
    except Exception as exc:
        logger.warning('AssemblyAI indisponible (%r); se sigue con la GPU', exc)
        return None


def _pista_aai(hint):
    """Traduce nuestra pista (num/min/max_speakers) al dialecto de AssemblyAI
    (speakers_expected / min_ / max_speakers_expected)."""
    hint = hint or {}
    out = {}
    if hint.get('num_speakers'):
        out['speakers_expected'] = int(hint['num_speakers'])
    else:
        if hint.get('min_speakers'):
            out['min_speakers_expected'] = int(hint['min_speakers'])
        if hint.get('max_speakers'):
            out['max_speakers_expected'] = int(hint['max_speakers'])
    return out


def _map(datos):
    """utterances de AAI (letras, milisegundos) -> formato local. Las letras se
    convierten a SPEAKER_00/01... por orden de aparicion (etiquetas por video,
    como siempre: nada de identidades)."""
    utt = datos.get('utterances') or []
    if not utt:
        logger.warning('AssemblyAI: respuesta sin utterances')
        return None
    letras = {}
    out = []
    for u in utt:
        sp = u.get('speaker') or '?'
        if sp not in letras:
            letras[sp] = f'SPEAKER_{len(letras):02d}'
        out.append({
            'start_seconds': (u.get('start') or 0) / 1000.0,
            'end_seconds': (u.get('end') or 0) / 1000.0,
            'text': (u.get('text') or '').strip(),
            'speaker_label': letras[sp],
            'words': [{'start': (w.get('start') or 0) / 1000.0,
                       'end': (w.get('end') or 0) / 1000.0,
                       'text': (w.get('text') or '').strip()}
                      for w in (u.get('words') or [])],
        })
    logger.info('AssemblyAI: %d intervenciones, %d voces, idioma %s',
                len(out), len(letras), datos.get('language_code'))
    return [s for s in out if s['text']]
