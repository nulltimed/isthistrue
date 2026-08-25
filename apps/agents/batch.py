"""API por lotes de Anthropic (2B): veredictos al 50%. El usuario ya espera la
validacion comunitaria, asi que la latencia del lote (minutos-horas) es gratis.

4.4-G (B.1, encargo del operador): esta via se habia quedado en el pasado. El
4.4-E migro la via directa a «el modelo busca sus fuentes» y dejo esta llamando
a SearXNG, bloqueado por los buscadores: 90 afirmaciones x 4 consultas x 3
intentos x 20 s = 6 HORAS de esperas vacias, y al final un lote SIN fuentes que
el candado del 4.4-E habria dejado entero en UNDECIDED. Ahora el lote lleva la
misma herramienta de busqueda web y el MISMO payload que la via directa
(verdict.build_payload), y el sondeo aplica los mismos candados al volcar.

Lo que NO puede hacer el lote: aprovechar la memoria (cache de prompt) de la
transcripcion entera — caduca en minutos y el lote tarda hasta 24 h. Con la
transcripcion entera activada, cada sobre lleva su fotocopia del libro: el
panel lo avisa (catalog.warning_for) y de fabrica se siembra «mostrador».
"""
import json
import logging

from celery import shared_task
from django.conf import settings

from apps.agents.catalog import model_for, web_searches_per_claim
from apps.agents import prompts

logger = logging.getLogger('agents.batch')


def _request_params(model, system, payload, expediente, tope):
    """Los mismos bloques que client.call_with_search, en formato de lote."""
    if expediente:
        contenido = [{'type': 'text', 'text': expediente,
                      'cache_control': {'type': 'ephemeral'}},
                     {'type': 'text', 'text': payload}]
    else:
        contenido = payload
    return {'model': model, 'max_tokens': 1500, 'system': system,
            'tools': [{'type': 'web_search_20250305', 'name': 'web_search',
                       'max_uses': tope}],
            'messages': [{'role': 'user', 'content': contenido}]}


def submit_verdict_batch(post, claims, model=None):
    """Envia todos los claims factuales de un post en un lote. Devuelve batch_id.
    `model`: el del panel para 'verdict' salvo que quien llama mande otro (el
    reanalisis profundo pasa el de 'deep')."""
    import anthropic
    from apps.agents.verdict import build_payload, full_transcript_enabled, transcript_dossier
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    modelo = model or model_for('verdict')
    fecha = post.event_date.isoformat() if post.event_date else None
    tope = web_searches_per_claim()
    expediente = transcript_dossier(post) if full_transcript_enabled() else None
    requests = []
    for i, c in enumerate(claims):
        requests.append({
            'custom_id': f'claim-{post.pk}-{i}',
            'params': _request_params(modelo, prompts.VERDICT_SYSTEM,
                                      build_payload(c, fecha, tope), expediente, tope)})
    batch = client.messages.batches.create(requests=requests)
    logger.info('Post %s: lote %s enviado con %d afirmaciones (%s)',
                post.pk, batch.id, len(requests), modelo)
    return batch.id


def parse_result_text(text):
    """El JSON del veredicto, saltando el texto que el modelo antepone al buscar
    (mismo criterio que client.call_search_json)."""
    raw = text.strip().removeprefix('```json').removesuffix('```').strip()
    if not raw.startswith('{'):
        inicio = raw.find('{')
        if inicio >= 0:
            raw = raw[inicio:]
    fin = raw.rfind('}')
    if fin > 0:
        raw = raw[:fin + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


@shared_task(bind=True, max_retries=60, default_retry_delay=120)
def poll_verdict_batch(self, batch_id, post_id, claims_json):
    """Sondea el lote cada 2 min; al terminar, vuelca veredictos a la wiki."""
    import anthropic
    from django.utils import timezone
    from apps.analysis.models import Post
    from apps.wiki.services import upsert_claim
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status != 'ended':
        raise self.retry()
    claims = json.loads(claims_json)
    post = Post.objects.get(pk=post_id)
    for entry in client.messages.batches.results(batch_id):
        if entry.result.type != 'succeeded':
            continue
        idx = int(entry.custom_id.rsplit('-', 1)[1])
        text = ''.join(b.text for b in entry.result.message.content
                       if getattr(b, 'type', '') == 'text')
        verdict = parse_result_text(text)
        if not verdict:
            continue
        # Los mismos candados que la via directa (4.4-B/E): sin fuentes no hay
        # color, y se apunta quien contesto.
        verdict['model_used'] = getattr(entry.result.message, 'model', '') or ''
        tiene_fuentes = bool(verdict.get('sources'))
        if not tiene_fuentes:
            verdict['color'] = 'UNDECIDED'
        upsert_claim(post, claims[idx], verdict, sources_ok=tiene_fuentes)
    post.status = 'DONE'
    post.full_finished_at = timezone.now()
    post.save(update_fields=['status', 'full_finished_at'])
    from apps.analysis.tasks import notify_post_event
    notify_post_event(post, 'analysis', 'Veredictos publicados')
    return 'done'
