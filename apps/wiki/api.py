"""API publica v1, solo lectura, datos CC-BY-SA. Sin auth; paginada."""
from django.http import JsonResponse
from .models import Claim

LICENSE = 'CC-BY-SA-4.0 — atribucion: isthistrue.xyztserver.com'


def claims_list(request):
    try:
        page = max(1, int(request.GET.get('page', '1')))
    except ValueError:
        page = 1
    qs = Claim.objects.filter(consolidated=True).order_by('-updated_at')
    total = qs.count()
    items = qs[(page - 1) * 50:page * 50]
    return JsonResponse({'license': LICENSE, 'total': total, 'page': page,
        'results': [{'slug': c.slug, 'text': c.text_original, 'color': c.color,
                     'updated': c.updated_at.isoformat()} for c in items]})


def claim_detail(request, slug):
    c = Claim.objects.filter(slug=slug, consolidated=True).first()
    if not c:
        return JsonResponse({'error': 'not_found'}, status=404)
    return JsonResponse({'license': LICENSE, 'slug': c.slug, 'text': c.text_original,
        'language': c.language, 'color': c.color,
        'what_is_claimed': c.what_is_claimed, 'what_evidence_says': c.what_evidence_says,
        'the_difference': c.the_difference,
        'sources': [{'url': s.url, 'title': s.title} for s in c.sources.all()],
        'appearances': c.appearances.count(), 'versions': c.versions.count(),
        'updated': c.updated_at.isoformat()})
