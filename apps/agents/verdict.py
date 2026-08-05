"""Fase cara: Sonnet + busquedas adaptativas -> claims wiki con semaforo (README v2 §3)."""
from django.conf import settings
from apps.agents import client, prompts, search, sweep

MOCK_VERDICT = {
    'color': 'GREEN',
    'what_is_claimed': '[SIMULADO] La torre Eiffel mide 300 m y se terminó en 1889.',
    'what_evidence_says': '[SIMULADO] Las fuentes confirman 300 m (312 con antena original) y 1889.',
    'the_difference': '[SIMULADO] Sin diferencia sustancial.',
    'sources': [{'url': 'https://example.org/fuente-simulada', 'title': '[SIMULADO] Fuente'}],
    'sensitive': None,
}


def run(post, model=None):
    from apps.wiki.services import upsert_claim
    sw = sweep.run(post) if not post.transcript_segments.filter(
        signal__isnull=False).exclude(signal='').exists() else {
        'claims': _claims_from_segments(post)}
    for c in sw['claims']:
        if c.get('kind') != 'FACTUAL':
            # gris: solo genera wiki en flujo completo (post ya validado como FACTUAL)
            pass
        n = search.budget_for_claim(c)
        results = search.search(c['text'], max_results=n)
        context = '\n'.join(f"- {r.get('title','')}: {r.get('url','')}\n  {r.get('content','')[:300]}"
                            for r in results)
        payload = f"CLAIM: {c['text']}\n\nRESULTADOS DE BUSQUEDA:\n{context or '(sin resultados)'}"
        v = client.call_json(model or settings.MODEL_VERDICT, prompts.VERDICT_SYSTEM,
                             payload, max_tokens=1500, mock_payload=MOCK_VERDICT)
        if 'error' not in v:
            upsert_claim(post, c, v)


def _claims_from_segments(post):
    out = []
    for i, s in enumerate(post.transcript_segments.all()):
        if s.signal in ('FACTUAL_UNVERIFIED', 'CONTRADICTS_MODEL'):
            out.append({'segment_index': i, 'text': s.text, 'kind': 'FACTUAL',
                        'ambiguous': s.signal == 'CONTRADICTS_MODEL'})
        elif s.signal == 'OPINION':
            out.append({'segment_index': i, 'text': s.text, 'kind': 'OPINION',
                        'ambiguous': False})
    return out
