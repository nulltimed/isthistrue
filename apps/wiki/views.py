import re
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .models import Claim, ClaimSlugHistory, ClaimVersion, Interlocutor


def claim_page(request, slug):
    claim = Claim.objects.filter(slug=slug).first()
    if not claim and slug.isdigit():
        claim = Claim.objects.filter(pk=int(slug)).first()
    if not claim:
        old = ClaimSlugHistory.objects.filter(old_slug=slug).select_related('claim').first()
        if old:  # redireccion 301 PERMANENTE (candado congelado)
            return redirect(f'/wiki/claim/{old.claim.slug}/', permanent=True)
    if not claim:
        from django.http import Http404
        raise Http404
    hide_opinions = bool(request.user.is_authenticated and request.user.hide_opinions)
    body = _autolink(claim)
    return render(request, 'analysis/claim_detail.html',
                  {'claim': claim, 'hide_opinions': hide_opinions, 'linked_evidence': body})


def _autolink(claim):
    """Interenlazado automatico estilo Wikipedia (quiz 10A): si el texto menciona
    otro claim conocido, se enlaza solo."""
    text = claim.what_evidence_says or ''
    others = Claim.objects.exclude(pk=claim.pk).exclude(slug__isnull=True) \
                          .filter(consolidated=True).values('slug', 'text_original')[:300]
    for o in others:
        frag = o['text_original'][:60]
        if len(frag) > 25 and frag.lower() in text.lower():
            idx = text.lower().find(frag.lower())
            orig = text[idx:idx + len(frag)]
            text = text.replace(orig, f'<a href="/wiki/claim/{o["slug"]}/">{orig}</a>', 1)
    return text


def recent_changes(request):
    """Pagina 'Cambios recientes' (quiz 11A)."""
    versions = ClaimVersion.objects.select_related('claim').order_by('-created_at')[:100]
    return render(request, 'analysis/recent_changes.html', {'versions': versions})


def person_page(request, slug):
    """Pagina de interlocutor: SOLO figuras publicas; redaccion estrictamente factual."""
    person = Interlocutor.objects.filter(slug=slug, is_public_figure=True).first()
    if not person:
        from .models import InterlocutorSlugHistory
        old = InterlocutorSlugHistory.objects.filter(old_slug=slug).first()
        if old and old.interlocutor.is_public_figure:
            return redirect(f'/wiki/persona/{old.interlocutor.slug}/', permanent=True)
        from django.http import Http404
        raise Http404
    from .naming import claims_for_person
    appearances = claims_for_person(person)[:100]
    return render(request, 'analysis/person_detail.html',
                  {'person': person, 'appearances': appearances})


def follow_claim(request, slug):
    from django.contrib.auth.decorators import login_required as _lr
    if not request.user.is_authenticated:
        return redirect(f'/accounts/login/?next=/wiki/claim/{slug}/')
    from .models import Claim, ClaimFollow
    claim = Claim.objects.filter(slug=slug).first()
    if claim:
        obj, created = ClaimFollow.objects.get_or_create(claim=claim, user=request.user)
        if not created:
            obj.delete()
    return redirect(f'/wiki/claim/{slug}/')
