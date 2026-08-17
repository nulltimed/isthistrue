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


# 4.3-C: los colores del semaforo, agrupados como los quiere David — "afirmaciones
# verdaderas, opiniones o afirmaciones falsas de cada hablante de cada video".
GRUPOS = [('GREEN', 'Afirmaciones verificadas'),
          ('AMBER', 'Afirmaciones con matices'),
          ('RED', 'Afirmaciones desmentidas'),
          ('GREY', 'Opiniones y predicciones')]


def people_indexable():
    """Interruptor del panel: las fichas de persona salen (o no) en buscadores.
    Por defecto APAGADO (decision de David, 4.3-C): existen y se pueden enlazar,
    pero llevan noindex hasta que el se decida."""
    from apps.panel.models import SystemSetting
    return SystemSetting.get_int('wiki_index_people', 0) == 1


def person_page_legacy(request, slug):
    """4.3-C: /wiki/persona/<slug>/ se mudo a /persona/<slug>/. 301 permanente
    para no romper enlaces ya publicados ni perder el posicionamiento."""
    return redirect(f'/persona/{slug}/', permanent=True)


def person_page(request, slug):
    """La ficha de persona ES la wiki (4.3-C, decision de David).

    Tres caminos posibles para un mismo slug:
      1. Una sola figura publica con ese slug -> su ficha.
      2. Varias personas comparten la raiz del nombre -> pagina de
         DESAMBIGUACION: "aparecerán todos los personajes posibles indexados".
      3. Slug antiguo -> 301 permanente (candado congelado).

    Candado congelado: SOLO figuras publicas tienen pagina. Hoy eso significa
    "identificada con QID de Wikidata" (P31=Q5) o aprobada a mano por moderacion.
    Un nombre escrito a mano sin QID no abre pagina: podria ser un particular.
    """
    from django.http import Http404
    from .models import InterlocutorSlugHistory
    from .naming import claims_for_person

    publicas = Interlocutor.objects.filter(is_public_figure=True)
    person = publicas.filter(slug=slug).first()

    # 2. Homonimos: la raiz del nombre lleva a mas de una ficha.
    hermanos = list(publicas.filter(base_slug=slug).exclude(pk=person.pk if person else 0))
    if hermanos:
        candidatos = ([person] if person else []) + hermanos
        return render(request, 'wiki/person_disambiguation.html',
                      {'slug': slug, 'candidatos': candidatos,
                       'indexable': people_indexable()})

    if not person:
        # 3. Slug antiguo.
        old = InterlocutorSlugHistory.objects.filter(old_slug=slug).first()
        if old and old.interlocutor.is_public_figure:
            return redirect('person_page', slug=old.interlocutor.slug, permanent=True)
        raise Http404

    # 1. Su ficha, con las afirmaciones agrupadas por color.
    appearances = list(claims_for_person(person)[:300])
    grupos = []
    for color, titulo in GRUPOS:
        filas = [a for a in appearances if a.claim.color == color]
        if filas:
            grupos.append({'color': color, 'titulo': titulo, 'filas': filas})
    sin_color = [a for a in appearances if a.claim.color not in dict(GRUPOS)]
    return render(request, 'analysis/person_detail.html',
                  {'person': person, 'appearances': appearances, 'grupos': grupos,
                   'sin_color': sin_color, 'total': len(appearances),
                   'indexable': people_indexable()})


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
