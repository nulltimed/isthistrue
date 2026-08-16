"""
Diarizacion local pyannote (Hito 2B): separa Hablante 1/2/3 con timestamps.
NUNCA se almacenan huellas de voz (clausula congelada: solo con visto bueno
ESCRITO del abogado de David; no esta construido). Sin HF_TOKEN: se omite y
todo funciona igual, sin etiquetas de hablante.
"""
import logging

from django.conf import settings

logger = logging.getLogger('agents.diarization')

_pipeline = None


def diarize(audio_path):
    """Devuelve lista [(start, end, 'SPEAKER_1'), ...] o [] si se omite.
    Regla 5.7: la omision NUNCA es silenciosa — siempre un WARNING con la causa
    (2ª reincidencia tras Turnstile; el except mudo de aqui escondio durante
    semanas el AttributeError torchaudio/pyannote en produccion)."""
    if settings.MOCK_AGENTS:
        return [(0.0, 12.0, 'SPEAKER_1'), (12.0, 24.0, 'SPEAKER_2')]
    if not settings.HF_TOKEN:
        logger.warning('Diarización omitida: HF_TOKEN ausente en .env')
        return []
    global _pipeline
    try:
        if _pipeline is None:
            from pyannote.audio import Pipeline
            _pipeline = Pipeline.from_pretrained(
                'pyannote/speaker-diarization-3.1', use_auth_token=settings.HF_TOKEN)
        import time
        t0 = time.monotonic()
        result = _pipeline(audio_path)
        # pyannote ya etiqueta como 'SPEAKER_00': usar tal cual (bug 4.2:
        # f'SPEAKER_{label}' fabricaba 'SPEAKER_SPEAKER_00').
        turns = [(turn.start, turn.end, str(label))
                 for turn, _, label in result.itertracks(yield_label=True)]
        logger.info('Diarización completada en %.1f s (%d turnos, %d hablantes)',
                    time.monotonic() - t0, len(turns), len({t[2] for t in turns}))
        return turns
    except Exception as exc:  # la diarizacion no tumba el analisis, pero AVISA
        logger.warning('Diarización omitida: %r', exc)
        return []

# label_segments eliminada en 4.2 D1: la asignacion de hablante ocurre ahora en
# tasks.merge_into_sentences (la frase completa es la unidad; grep verifico cero
# usos restantes, tests incluidos).
