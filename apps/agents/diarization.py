"""
Diarizacion local pyannote (Hito 2B): separa Hablante 1/2/3 con timestamps.
NUNCA se almacenan huellas de voz (clausula congelada: solo con visto bueno
ESCRITO del abogado de David; no esta construido). Sin HF_TOKEN: se omite y
todo funciona igual, sin etiquetas de hablante.
"""
from django.conf import settings

_pipeline = None


def diarize(audio_path):
    """Devuelve lista [(start, end, 'SPEAKER_1'), ...] o [] si no hay token/mock."""
    if settings.MOCK_AGENTS:
        return [(0.0, 12.0, 'SPEAKER_1'), (12.0, 24.0, 'SPEAKER_2')]
    if not settings.HF_TOKEN:
        return []
    global _pipeline
    try:
        if _pipeline is None:
            from pyannote.audio import Pipeline
            _pipeline = Pipeline.from_pretrained(
                'pyannote/speaker-diarization-3.1', use_auth_token=settings.HF_TOKEN)
        result = _pipeline(audio_path)
        return [(turn.start, turn.end, f'SPEAKER_{label}')
                for turn, _, label in result.itertracks(yield_label=True)]
    except Exception:
        return []  # la diarizacion nunca debe tumbar el analisis


def label_segments(segments, turns):
    """Asigna a cada segmento de transcripcion el hablante con mas solape temporal."""
    for seg in segments:
        best, best_overlap = '', 0.0
        for (ts, te, label) in turns:
            overlap = min(seg.end_seconds, te) - max(seg.start_seconds, ts)
            if overlap > best_overlap:
                best, best_overlap = label, overlap
        if best:
            seg.speaker_label = best
            seg.save(update_fields=['speaker_label'])
