"""Barrido universal Haiku: claims + señales + clickbait + adulto (README v2 §4)."""
from django.conf import settings
from . import client, prompts

MOCK_SWEEP = {
    'claims': [
        {'segment_index': 1, 'text': '[SIMULADO] La torre Eiffel mide 300 metros y se termino en 1889.',
         'kind': 'FACTUAL', 'ambiguous': False, 'contradicts_common_knowledge': False},
        {'segment_index': 2, 'text': '[SIMULADO] Esto va a cambiar el mundo el año que viene.',
         'kind': 'OPINION', 'ambiguous': False, 'contradicts_common_knowledge': False},
    ],
    'manipulation': True, 'is_adult': False, 'language': 'es',
}


def run(post):
    segments = list(post.transcript_segments.all())
    payload = '\n'.join(f'[{i}] ({s.start_seconds:.0f}s) {s.text}'
                        for i, s in enumerate(segments))
    result = client.call_json(settings.MODEL_CHEAP, prompts.SWEEP_SYSTEM,
                              payload, mock_payload=MOCK_SWEEP)
    # Anclar señales baratas a sus segmentos (transcripcion sincronizada):
    for c in result.get('claims', []):
        idx = c.get('segment_index')
        if idx is not None and 0 <= idx < len(segments):
            seg = segments[idx]
            if c.get('contradicts_common_knowledge'):
                seg.signal = 'CONTRADICTS_MODEL'
            elif c.get('kind') == 'OPINION':
                seg.signal = 'OPINION'
            else:
                seg.signal = 'FACTUAL_UNVERIFIED'
            seg.save(update_fields=['signal'])
    return {'claims': result.get('claims', []),
            'manipulation': bool(result.get('manipulation')),
            'is_adult': bool(result.get('is_adult'))}
