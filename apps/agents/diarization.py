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


def diarize(audio_path, num_speakers=None, min_speakers=None, max_speakers=None):
    """Devuelve lista [(start, end, 'SPEAKER_1'), ...] o [] si se omite.
    Regla 5.7: la omision NUNCA es silenciosa — siempre un WARNING con la causa
    (2ª reincidencia tras Turnstile; el except mudo de aqui escondio durante
    semanas el AttributeError torchaudio/pyannote en produccion).

    4.4-G (A.1, reformulado por David): el pipeline recibe una PISTA del numero
    de voces. Medido por el operador sobre el post 5 (docs/47): sin pista,
    pyannote fundia a los dos hablantes y sacaba un tercero de los restos
    (94,8 % / 5,2 %); con `num_speakers=2` el segundo casi se triplicaba. Un
    `min_speakers=2` fijo quedo DESCARTADO: partiria en dos la voz unica de un
    monologo. La pista viene de la datacion (misma llamada de Haiku, coste
    cero) o de moderacion; sin pista, automatico como siempre.
    """
    if settings.MOCK_AGENTS:
        if num_speakers == 1:
            return [(0.0, 24.0, 'SPEAKER_1')]
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
        kwargs = pipeline_kwargs(num_speakers, min_speakers, max_speakers)
        logger.info('Diarización con pista de voces: %s', kwargs or 'ninguna (automático)')
        result = _pipeline(audio_path, **kwargs)
        # pyannote ya etiqueta como 'SPEAKER_00': usar tal cual (bug 4.2:
        # f'SPEAKER_{label}' fabricaba 'SPEAKER_SPEAKER_00').
        turns = [(turn.start, turn.end, str(label))
                 for turn, _, label in result.itertracks(yield_label=True)]
        logger.info('Diarización completada en %.1f s (%d turnos, %d hablantes)',
                    time.monotonic() - t0, len(turns), len({t[2] for t in turns}))
        return absorb_ghost_speakers(turns)
    except Exception as exc:  # la diarizacion no tumba el analisis, pero AVISA
        logger.warning('Diarización omitida: %r', exc)
        return []

def pipeline_kwargs(num_speakers=None, min_speakers=None, max_speakers=None):
    """Traduce la pista a los argumentos de pyannote, sin contradicciones:
    un numero exacto manda sobre el rango; un rango vacio no se envia."""
    if num_speakers and num_speakers >= 1:
        return {'num_speakers': int(num_speakers)}
    out = {}
    if min_speakers and min_speakers >= 1:
        out['min_speakers'] = int(min_speakers)
    if max_speakers and max_speakers >= 1:
        out['max_speakers'] = max(int(max_speakers), out.get('min_speakers', 1))
    return out


def absorb_ghost_speakers(turns, min_share=0.01, min_seconds=10.0):
    """4.4-G (A.3): el «hablante 3» del post 5 eran 12 apariciones que sumaban
    7,7 s («Mm», «Nice.», «glow»...): con eso no hay material acustico para
    caracterizar a nadie, asi que el clustering aparta lo que no sabe clasificar
    y le pone etiqueta propia. Una etiqueta con menos del 1 % del tiempo total
    (o menos de 10 s absolutos) NO es una persona: cada uno de sus turnos se
    reasigna al hablante real mas cercano en el tiempo. Si no queda ningun
    hablante real (audio brevisimo), no se toca nada.

    Post-proceso puro sobre la lista de turnos; no toca pyannote.
    """
    if not turns:
        return turns
    tiempo = {}
    for ts, te, label in turns:
        tiempo[label] = tiempo.get(label, 0.0) + max(0.0, te - ts)
    total = sum(tiempo.values()) or 1.0
    fantasmas = {l for l, t in tiempo.items()
                 if t < min_seconds or t / total < min_share}
    reales = [t for t in turns if t[2] not in fantasmas]
    if not fantasmas or not reales:
        return turns
    logger.info('Voces fantasma absorbidas: %s',
                ', '.join(f'{l} ({tiempo[l]:.1f} s)' for l in sorted(fantasmas)))

    def vecino(ts, te):
        medio = (ts + te) / 2.0
        return min(reales, key=lambda t: min(abs(t[0] - medio), abs(t[1] - medio)))[2]

    out = []
    for ts, te, label in turns:
        out.append((ts, te, vecino(ts, te) if label in fantasmas else label))
    return out


# label_segments eliminada en 4.2 D1: la asignacion de hablante ocurre ahora en
# tasks.merge_into_sentences (la frase completa es la unidad; grep verifico cero
# usos restantes, tests incluidos).
