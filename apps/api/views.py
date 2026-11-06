"""6.2: la API publica de lectura (v1) + solicitud de clave + reclamacion.

Solo LECTURA y solo lo ya publico en la web: claims con sus veredictos, fuentes
y cadenas de origen; analisis (posts) con su semaforo; canales con ficha; la
transcripcion; estadisticas agregadas. Nada de datos de usuarios, JAMAS.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .auth import envelope, require_api_key

PER_PAGE_MAX = 100


def _page(request, qs):
    try:
        page = max(1, int(request.GET.get('page', 1)))
        per = min(PER_PAGE_MAX, max(1, int(request.GET.get('per_page', 25))))
    except ValueError:
        page, per = 1, 25
    total = qs.count()
    return qs[(page - 1) * per: page * per], {'page': page, 'per_page': per,
                                              'total': total}


def _claim_dict(c, full=False):
    d = {'slug': c.slug, 'title': c.title or '', 'text': c.text_original,
         'color': c.color, 'kind': c.kind, 'consolidated': c.consolidated,
         'created_at': c.created_at.isoformat(),
         'url': f'/wiki/claim/{c.slug or c.pk}/'}
    if full:
        d.update({
            'what_is_claimed': c.what_is_claimed,
            'what_evidence_says': c.what_evidence_says,
            'the_difference': c.the_difference,
            'temporal_basis': c.temporal_basis,
            'sources': [{'url': s.url, 'title': s.title} for s in c.sources.all()],
            'origin_status': c.origin_status,
            'origin_chain': c.origin_chain,
            'appearances': [{
                'post_id': ap.segment.post_id,
                'post_url': ap.segment.post.url,
                'post_title': ap.segment.post.title,
                'second': ap.segment.start_seconds,
                'quote': ap.quote,
            } for ap in c.appearances.select_related('segment__post')[:20]],
        })
    return d


@require_api_key
def claims_list(request):
    """GET /api/v1/claims/ — filtros: color, kind, q (texto), since (YYYY-MM-DD),
    consolidated, origin (1 = solo con cadena), page/per_page."""
    from apps.wiki.models import Claim
    qs = Claim.objects.all().order_by('-created_at')
    color = request.GET.get('color', '').upper()
    if color in ('GREEN', 'AMBER', 'RED', 'GREY', 'UNDECIDED'):
        qs = qs.filter(color=color)
    kind = request.GET.get('kind', '').upper()
    if kind:
        qs = qs.filter(kind=kind)
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(text_original__icontains=q)
    since = parse_date(request.GET.get('since', '') or '')
    if since:
        qs = qs.filter(created_at__date__gte=since)
    if request.GET.get('consolidated') == '1':
        qs = qs.filter(consolidated=True)
    if request.GET.get('origin') == '1':
        qs = qs.filter(origin_status='DONE')
    rows, meta = _page(request, qs)
    return envelope([_claim_dict(c) for c in rows], meta=meta)


@require_api_key
def claim_detail(request, slug):
    from apps.wiki.models import Claim
    c = get_object_or_404(Claim, slug=slug)
    return envelope(_claim_dict(c, full=True))


@require_api_key
def posts_list(request):
    """GET /api/v1/analisis/ — los analisis publicos, con su semaforo."""
    from django.db.models import Count
    from apps.analysis.models import Post
    from apps.wiki.models import Claim
    qs = Post.objects.publicos().filter(status='DONE').order_by('-created_at')
    since = parse_date(request.GET.get('since', '') or '')
    if since:
        qs = qs.filter(created_at__date__gte=since)
    rows, meta = _page(request, qs)
    data = []
    for p in rows:
        colores = dict(Claim.objects.filter(appearances__segment__post=p)
                       .values_list('color').annotate(n=Count('pk'))
                       .values_list('color', 'n'))
        data.append({'id': p.pk, 'title': p.title, 'source_url': p.url,
                     'created_at': p.created_at.isoformat(),
                     'url': p.get_absolute_url(),
                     'semaforo': {k.lower(): v for k, v in colores.items()}})
    return envelope(data, meta=meta)


@require_api_key
def post_detail(request, pk):
    from apps.analysis.models import Post
    from apps.wiki.models import Claim
    p = get_object_or_404(Post.objects.publicos(), pk=pk)
    claims = (Claim.objects.filter(appearances__segment__post=p).distinct()
              .order_by('-created_at'))
    return envelope({'id': p.pk, 'title': p.title, 'source_url': p.url,
                     'status': p.status, 'created_at': p.created_at.isoformat(),
                     'url': p.get_absolute_url(),
                     'claims': [_claim_dict(c) for c in claims[:200]]})


@require_api_key
def post_transcript(request, pk):
    from apps.analysis.models import Post
    p = get_object_or_404(Post.objects.publicos(), pk=pk)
    segs = p.transcript_segments.order_by('start_seconds')
    rows, meta = _page(request, segs)
    return envelope([{'start': s.start_seconds, 'end': s.end_seconds,
                      'text': s.text} for s in rows], meta=meta)


@require_api_key
def channels_list(request):
    """Solo canales CON ficha publica (umbral 5/10/5; particulares jamas)."""
    from apps.analysis.models import Channel
    data = []
    for ch in Channel.objects.all().order_by('name'):
        if not ch.meets_threshold():
            continue
        data.append({'id': ch.pk, 'name': ch.name, 'platform': ch.platform})
    return envelope(data)


@require_api_key
def stats(request):
    """Agregados para informes: totales y las ultimas 8 semanas."""
    from datetime import timedelta
    from django.db.models import Count
    from apps.analysis.models import Post
    from apps.wiki.models import Claim
    por_color = dict(Claim.objects.values_list('color').annotate(n=Count('pk')))
    hace8 = timezone.now() - timedelta(weeks=8)
    semanal = (Claim.objects.filter(created_at__gte=hace8)
               .extra(select={'w': "to_char(created_at, 'IYYY-IW')"})
               .values('w').annotate(n=Count('pk')).order_by('w'))
    return envelope({
        'claims_total': Claim.objects.count(),
        'claims_por_color': {k.lower(): v for k, v in por_color.items()},
        'claims_con_origen': Claim.objects.filter(origin_status='DONE').count(),
        'analisis_publicados': Post.objects.publicos().filter(status='DONE').count(),
        'claims_por_semana': list(semanal),
    })


# --------- solicitud de clave y reclamacion (publicas, sin clave) ---------

def api_home(request):
    """/api/: documentacion + formulario de solicitud (con cebo antispam)."""
    from .models import ApiKey
    if request.method == 'POST':
        if request.POST.get('web2'):   # cebo: los robots lo rellenan
            return redirect('/api/')
        entity = request.POST.get('entity_name', '').strip()[:200]
        email = request.POST.get('contact_email', '').strip()[:200]
        purpose = request.POST.get('purpose', '').strip()[:1000]
        kind = 'ORG' if request.POST.get('kind') == 'ORG' else 'PERSON'
        if not entity or '@' not in email or len(purpose) < 20:
            messages.error(request, 'Faltan datos: nombre, email válido y un uso '
                                    'declarado de al menos 20 caracteres.')
        else:
            sol = ApiKey.objects.create(
                kind=kind, entity_name=entity, contact_email=email,
                website=request.POST.get('website', '').strip()[:200],
                purpose=purpose)
            from .tasks import vet_api_key
            vet_api_key.delay(sol.pk)
            messages.success(request, 'Solicitud recibida: el escrutinio automático '
                                      'tarda unos minutos y el resultado llega a tu '
                                      'correo. Si se deniega, podrás reclamar y lo '
                                      'revisará una persona.')
        return redirect('/api/')
    return render(request, 'api/docs.html', {})


def api_appeal(request, pk, token):
    """La reclamacion del denegado: entra en la bandeja de los superusuarios."""
    from .models import ApiKey
    sol = get_object_or_404(ApiKey, pk=pk, appeal_token=token)
    if sol.status not in ('DENIED', 'APPEALED'):
        messages.info(request, 'Esta solicitud no está denegada.')
        return redirect('/api/')
    if request.method == 'POST':
        sol.appeal_text = request.POST.get('appeal_text', '').strip()[:1000]
        sol.status = 'APPEALED'
        sol.save(update_fields=['appeal_text', 'status'])
        messages.success(request, 'Reclamación recibida: una persona revisará la '
                                  'decisión y te contestará al correo.')
        return redirect('/api/')
    return render(request, 'api/reclamar.html', {'sol': sol})
