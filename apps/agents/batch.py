"""API por lotes de Anthropic (2B): veredictos al 50%. El usuario ya espera la
validacion comunitaria, asi que la latencia del lote (minutos-horas) es gratis."""
import json
from celery import shared_task
from django.conf import settings
from apps.agents import prompts, search


def submit_verdict_batch(post, claims):
    """Envia todos los claims factuales de un post en un lote. Devuelve batch_id."""
    import anthropic
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    requests = []
    for i, c in enumerate(claims):
        n = search.budget_for_claim(c)
        results = search.search(c['text'], max_results=n)
        context = '\n'.join(f"- {r.get('title','')}: {r.get('url','')}\n  {r.get('content','')[:300]}"
                            for r in results)
        requests.append({
            'custom_id': f'claim-{post.pk}-{i}',
            'params': {'model': settings.MODEL_VERDICT, 'max_tokens': 1500,
                       'system': prompts.VERDICT_SYSTEM,
                       'messages': [{'role': 'user', 'content':
                           f"CLAIM: {c['text']}\n\nRESULTADOS DE BUSQUEDA:\n{context or '(sin resultados)'}"}]}})
    batch = client.messages.batches.create(requests=requests)
    return batch.id


@shared_task(bind=True, max_retries=60, default_retry_delay=120)
def poll_verdict_batch(self, batch_id, post_id, claims_json):
    """Sondea el lote cada 2 min; al terminar, vuelca veredictos a la wiki."""
    import anthropic
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
        text = text.strip().removeprefix('```json').removesuffix('```').strip()
        try:
            verdict = json.loads(text)
        except json.JSONDecodeError:
            continue
        upsert_claim(post, claims[idx], verdict)
    post.status = 'DONE'
    post.save(update_fields=['status'])
    return 'done'
