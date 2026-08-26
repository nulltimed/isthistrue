"""
Cliente de la GPU serverless de Runpod (intervencion del operador, 2026-08-26).

Orden de David: «todo el analisis susceptible de mejorar por GPU pasa por Runpod»,
con autorizacion permanente para el gasto (saldo PREPAGO: el techo es lo cargado).
Primera etapa migrada: la transcripcion (whisper small-int8 en CPU -> large-v3 en
GPU). La separacion de voces necesita un worker a medida: encargada a Fable en
docs/54 (pase 4.4-J).

REGLA DE ORO (5.7): la GPU acelera, JAMAS bloquea. Cualquier fallo -> None, y el
que llama sigue en CPU exactamente como hasta hoy, con un WARNING en el log.
"""
import base64
import logging
import os
import subprocess
import tempfile
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

RUN_BASE = 'https://api.runpod.ai/v2'
# /run admite ~10 MB de carga util. El opus mono a 24 kbps mete el tramo tipico
# muy por debajo (23 min ~ 4,3 MB -> 5,8 MB en base64). Si aun asi no cabe, se
# devuelve None y la CPU se encarga: nunca se recorta audio en silencio.
MAX_B64_BYTES = 9_500_000


def _audio_to_opus_b64(audio_path):
    """Recomprime a opus mono 24k (ffmpeg, ya en la imagen) y codifica base64.
    None si no cabe en la carga util de /run o si ffmpeg falla."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'audio.ogg')
        proc = subprocess.run(
            ['ffmpeg', '-y', '-i', audio_path, '-ac', '1', '-c:a', 'libopus',
             '-b:a', '24k', '-vn', out],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if proc.returncode != 0 or not os.path.exists(out):
            logger.warning('GPU: ffmpeg no pudo recomprimir %s', audio_path)
            return None
        b64 = base64.b64encode(open(out, 'rb').read()).decode('ascii')
    if len(b64) > MAX_B64_BYTES:
        logger.warning('GPU: audio de %.1f MB en base64 no cabe en /run; CPU',
                       len(b64) / 1e6)
        return None
    return b64


def _map_output(out):
    """Del contrato del worker oficial (runpod/ai-api-faster-whisper) al formato
    local: segments trae el texto y word_timestamps es una LISTA GLOBAL aparte
    (medido contra el endpoint real, no contra la documentacion). Se reparte
    cada palabra al segmento en cuyo reloj cae, con un puntero para no duplicar."""
    segs = out.get('segments') or []
    words = out.get('word_timestamps') or []
    res, i = [], 0
    for s in segs:
        start, end = float(s.get('start', 0.0)), float(s.get('end', 0.0))
        sw = []
        while i < len(words) and float(words[i].get('start', 0.0)) < end:
            w = words[i]
            sw.append({'start': float(w.get('start', 0.0)),
                       'end': float(w.get('end', 0.0)),
                       'text': str(w.get('word', '')).strip()})
            i += 1
        res.append({'start_seconds': start, 'end_seconds': end,
                    'text': str(s.get('text', '')).strip(), 'words': sw})
    return res or None


def transcribe_gpu(audio_path):
    """Transcribe en la GPU de Runpod. Devuelve segmentos en el MISMO formato
    que la via CPU, o None ante cualquier impedimento (sin configurar, audio
    demasiado grande, fallo o timeout remoto): el llamante DEBE caer a CPU."""
    key, ep = settings.RUNPOD_API_KEY, settings.RUNPOD_WHISPER_ENDPOINT
    if not (key and ep):
        return None
    try:
        b64 = _audio_to_opus_b64(audio_path)
        if not b64:
            return None
        headers = {'Authorization': f'Bearer {key}'}
        r = httpx.post(f'{RUN_BASE}/{ep}/run', headers=headers, timeout=60,
                       json={'input': {'audio_base64': b64,
                                       'model': settings.WHISPER_GPU_MODEL,
                                       'word_timestamps': True,
                                       'beam_size': 5}})
        job_id = (r.json() or {}).get('id')
        if not job_id:
            logger.warning('GPU: /run sin id de trabajo (HTTP %s)', r.status_code)
            return None
        deadline = time.monotonic() + settings.RUNPOD_JOB_TIMEOUT
        while time.monotonic() < deadline:
            time.sleep(settings.RUNPOD_POLL_SECONDS)
            st = httpx.get(f'{RUN_BASE}/{ep}/status/{job_id}',
                           headers=headers, timeout=30).json() or {}
            estado = st.get('status')
            if estado == 'COMPLETED':
                logger.info('GPU: transcripcion %s en %s ms de GPU facturada',
                            settings.WHISPER_GPU_MODEL, st.get('executionTime'))
                return _map_output(st.get('output') or {})
            if estado in ('FAILED', 'CANCELLED', 'TIMED_OUT'):
                logger.warning('GPU: trabajo %s -> %s; se sigue en CPU',
                               job_id, estado)
                return None
        # timeout nuestro: cancelar el trabajo para no dejar GPU corriendo sola
        httpx.post(f'{RUN_BASE}/{ep}/cancel/{job_id}', headers=headers, timeout=30)
        logger.warning('GPU: trabajo %s cancelado por timeout local; CPU', job_id)
        return None
    except Exception as exc:
        logger.warning('GPU Runpod indisponible (%s); se sigue en CPU', exc)
        return None
