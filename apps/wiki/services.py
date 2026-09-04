"""Deduplicacion semantica y alta/actualizacion de claims."""
from django.conf import settings
from .models import Claim, ClaimAppearance, ClaimVersion, Source, HAS_PGVECTOR

SIMILARITY_THRESHOLD = 0.88  # coseno sobre pivote EN


def upsert_claim(post, claim_data, verdict, sources_ok=True):
    """Crea o actualiza la pagina wiki del claim y ancla la aparicion.
    sources_ok=False (4.2 C1): el veredicto se emitio sin busquedas de fuentes."""
    # 5.1-B.2: el embedding se calculaba para deduplicar y SE TIRABA — 186
    # claims sin huella y la malla de «relacionadas» muda. Ahora se calcula UNA
    # vez, se usa para deduplicar y se GUARDA (junto al pivote EN).
    pivote, emb = '', None
    if not settings.MOCK_AGENTS and HAS_PGVECTOR:
        pivote = _pivot_en(claim_data['text'])
        emb = _embed(pivote)
    existing = find_similar_claim(claim_data['text'], emb=emb)
    if existing:
        claim = existing
    else:
        from django.utils.text import slugify
        base = slugify(claim_data['text'])[:120] or 'claim'
        slug, n = base, 2
        while Claim.objects.filter(slug=slug).exists():
            slug, n = f'{base}-{n}', n + 1
        claim = Claim.objects.create(text_original=claim_data['text'],
                                     language='es', slug=slug)
    if emb is not None and getattr(claim, 'embedding', None) is None:
        claim.embedding = emb
        claim.text_pivot_en = claim.text_pivot_en or pivote
    old_color = claim.color if claim.pk else None
    from .models import COLORS
    color = verdict.get('color', 'UNDECIDED')
    # Un modelo puede inventarse una etiqueta: si no es de las nuestras, no entra.
    claim.color = color if color in dict(COLORS) else 'UNDECIDED'
    claim.consolidated = True
    claim.what_is_claimed = verdict.get('what_is_claimed', '')
    claim.what_evidence_says = verdict.get('what_evidence_says', '')
    claim.the_difference = verdict.get('the_difference', '')
    old_color = Claim.objects.filter(pk=claim.pk).values_list('color', flat=True).first()
    claim.sensitive = verdict.get('sensitive') or ''
    # 4.4-B: contra que serie y que rango se comparo (decision de David).
    claim.temporal_basis = (verdict.get('temporal_basis') or '')[:300]
    claim.model_used = (verdict.get('model_used') or '')[:60]
    claim.sources_ok = sources_ok
    claim.save()
    # 4.3-A J3: el semaforo de un claim seguido cambia -> aviso a sus seguidores
    if old_color and old_color != claim.color:
        from apps.accounts.services import notify
        for f in claim.followers.select_related('user'):
            notify(f.user, f'El semáforo de un claim que sigues ha cambiado: '
                           f'«{claim.text_original[:70]}»',
                   f'/wiki/claim/{claim.slug or claim.pk}/', kind='claim_color')
    ClaimVersion.objects.create(claim=claim, color=claim.color, body_snapshot=verdict)
    claim.sources.all().delete()
    for s in verdict.get('sources', []):
        Source.objects.create(claim=claim, url=s.get('url', ''), title=s.get('title', ''))
    seg_idx = claim_data.get('segment_index')
    # 4.4-B (bug de anclaje): quien numero las frases uso order_by('start_seconds',
    # 'pk'); aqui se leia con el ordering del Meta, que solo ordena por
    # start_seconds. Si DOS frases empiezan en el mismo segundo — normal cuando dos
    # personas se pisan — el veredicto se pegaba a la frase equivocada. El propio
    # codigo citaba la leccion tres lineas mas arriba y no la aplicaba.
    segments = list(post.transcript_segments.order_by('start_seconds', 'pk'))
    if seg_idx is not None and 0 <= seg_idx < len(segments):
        ClaimAppearance.objects.get_or_create(claim=claim, segment=segments[seg_idx],
                                              defaults={'quote': claim_data['text']})
    if old_color and old_color != claim.color:
        from apps.accounts.services import notify
        for f in claim.followers.select_related('user'):
            notify(f.user, f'Un claim que sigues cambió de color: ahora {claim.get_color_display()}',
                   url=f'/wiki/claim/{claim.slug}/')
    return claim


def find_similar_claim(text, emb=None):
    """Dedupe por embedding pgvector; sin embeddings (mock) cae a igualdad exacta.
    5.1-B.2: acepta el embedding ya calculado para no pagar el pivote dos veces."""
    if settings.MOCK_AGENTS or not HAS_PGVECTOR:
        return Claim.objects.filter(text_original=text).first()
    if emb is None:
        emb = _embed(_pivot_en(text))
    if emb is None:
        return Claim.objects.filter(text_original=text).first()
    from pgvector.django import CosineDistance
    qs = Claim.objects.exclude(embedding__isnull=True).annotate(
        dist=CosineDistance('embedding', emb)).filter(
        dist__lt=1 - SIMILARITY_THRESHOLD).order_by('dist')
    return qs.first()


def find_similar_bad_claim(text):
    c = find_similar_claim(text)
    return c if (c and c.color in ('RED', 'AMBER') and c.consolidated) else None


def _pivot_en(text):
    from apps.agents import client, prompts
    # README §25 DEFINITIVO: pivote EN = Haiku (la subida a Sonnet era de la ronda v2 superada)
    return client.call(settings.MODEL_CHEAP, prompts.PIVOT_SYSTEM, text,
                       max_tokens=300, mock_payload=None) or text


_model = None

def _embed(text):
    """Modelo local sentence-transformers (decidido: 'ahora'). Gratis por uso;
    carga perezosa (~0.5-1.5 GB RAM la primera vez en el worker)."""
    global _model
    try:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            from django.conf import settings as s
            _model = SentenceTransformer(s.EMBEDDINGS_MODEL, device='cpu')
        return _model.encode(text, normalize_embeddings=True).tolist()
    except Exception:
        return None
