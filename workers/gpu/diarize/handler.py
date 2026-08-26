"""Worker serverless de diarizacion (pase 4.4-J) — contrato de docs/56 §4.2.

entrada: {"audio_base64": <opus b64>,
          "hint": {"num_speakers": N} | {"min_speakers": a, "max_speakers": b} | {},
          "model": "pyannote/speaker-diarization-3.1" | "pyannote/speaker-diarization-community-1",
          "second_pass_num_speakers": N | null}
salida:  {"turns": [[start, end, "SPEAKER_00"], ...],
          "turns_second_pass": [...] | null,
          "tiempos": {"diarize_s": x, "second_pass_s": y},
          "model": <modelo usado>, "device": "cuda"|"cpu"}

Politica (docs/56 §4.2, leccion 4.4-E): aqui SOLO musculo. La eleccion entre la
primera y la segunda pasada (keep_better_split), la absorcion de fantasmas y
todo lo demas se decide en el VPS. Este proceso arranca, separa y MUERE: no
persiste audio, embeddings ni nada (linea roja de biometria, docs/56 §6).
"""
import base64
import os
import subprocess
import tempfile
import time

import runpod
import torch

DEFAULT_MODEL = 'pyannote/speaker-diarization-3.1'
ALLOWED = {DEFAULT_MODEL, 'pyannote/speaker-diarization-community-1'}
_pipelines = {}


def _pipeline(name):
    from pyannote.audio import Pipeline
    if name not in _pipelines:
        # Fix del operador (2026-08-26): pyannote 4 renombro use_auth_token -> token.
        # Se inspecciona la firma para que el MISMO handler sirva en ambas imagenes.
        import inspect
        params = inspect.signature(Pipeline.from_pretrained).parameters
        kw = 'use_auth_token' if 'use_auth_token' in params else 'token'
        p = Pipeline.from_pretrained(name, **{kw: os.environ.get('HF_TOKEN')})
        if torch.cuda.is_available():
            p.to(torch.device('cuda'))
        _pipelines[name] = p
    return _pipelines[name]


def _decode(audio_b64, workdir):
    """opus/ogg base64 -> dict {waveform, sample_rate} para pyannote.

    Fix del operador (2026-08-26): pyannote 4 lee FICHEROS via torchcodec, que
    arrastra su propia matriz de FFmpeg y fallaba en el worker real. Decodificar
    con ffmpeg a PCM crudo y entregar el tensor evita torchcodec POR COMPLETO y
    funciona igual bajo pyannote 3 y 4 (ambos aceptan el dict)."""
    import numpy as np
    import torch
    src = os.path.join(workdir, 'in.ogg')
    with open(src, 'wb') as f:
        f.write(base64.b64decode(audio_b64))
    proc = subprocess.run(['ffmpeg', '-y', '-i', src, '-f', 'f32le', '-ac', '1',
                           '-ar', '16000', '-'],
                          check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
    onda = torch.from_numpy(
        np.frombuffer(proc.stdout, dtype=np.float32).copy()).unsqueeze(0)
    return {'waveform': onda, 'sample_rate': 16000}


def _kwargs(hint):
    """Sin contradicciones: numero exacto manda; un rango vacio no se envia."""
    hint = hint or {}
    n = hint.get('num_speakers')
    if n:
        return {'num_speakers': int(n)}
    out = {}
    if hint.get('min_speakers'):
        out['min_speakers'] = int(hint['min_speakers'])
    if hint.get('max_speakers'):
        out['max_speakers'] = max(int(hint['max_speakers']), out.get('min_speakers', 1))
    return out


def _run(pipeline, wav, **kw):
    t0 = time.monotonic()
    result = pipeline(wav, **kw)
    # Fix del operador (2026-08-26): pyannote 4 devuelve DiarizeOutput, no la
    # Annotation directa de pyannote 3; la Annotation con itertracks vive dentro.
    # Se desenvuelve por atributos para que el MISMO handler sirva en ambas.
    if not hasattr(result, 'itertracks'):
        for _attr in ('speaker_diarization', 'diarization', 'annotation', 'prediction'):
            _cand = getattr(result, _attr, None)
            if _cand is not None and hasattr(_cand, 'itertracks'):
                result = _cand
                break
        else:
            raise RuntimeError('salida de pyannote sin itertracks: %r' % type(result))
    turns = [[round(turn.start, 3), round(turn.end, 3), str(label)]
             for turn, _, label in result.itertracks(yield_label=True)]
    return turns, round(time.monotonic() - t0, 2)


def handler(job):
    inp = job.get('input') or {}
    audio = inp.get('audio_base64')
    if not audio:
        return {'error': 'falta audio_base64'}
    model = inp.get('model') or DEFAULT_MODEL
    if model not in ALLOWED:
        return {'error': f'modelo no permitido: {model}'}
    n2 = inp.get('second_pass_num_speakers')
    with tempfile.TemporaryDirectory() as td:
        wav = _decode(audio, td)
        pipe = _pipeline(model)
        turns, t1 = _run(pipe, wav, **_kwargs(inp.get('hint')))
        turns2, t2 = (None, None)
        if n2 and int(n2) >= 1:
            turns2, t2 = _run(pipe, wav, num_speakers=int(n2))
    return {'turns': turns, 'turns_second_pass': turns2,
            'tiempos': {'diarize_s': t1, 'second_pass_s': t2},
            'model': model, 'device': 'cuda' if torch.cuda.is_available() else 'cpu'}


runpod.serverless.start({'handler': handler})
