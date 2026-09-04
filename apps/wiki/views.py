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
                  {'claim': claim, 'hide_opinions': hide_opinions, 'linked_evidence': body,
                   # 5.1-B: la malla — quien lo dijo y afirmaciones cercanas
                   'hablantes': speakers_of_claim(claim),
                   'relacionados': related_claims(claim)})


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
    # 5.1-B: los nombres con ficha publica se enlazan solos (efecto Wikipedia).
    for per in Interlocutor.objects.filter(is_public_figure=True).values('slug', 'name'):
        low = text.lower()
        idx = low.find(per['name'].lower())
        if idx == -1:
            continue
        # nunca dentro de un enlace ya puesto
        if text.rfind('<a ', 0, idx) > text.rfind('</a>', 0, idx):
            continue
        orig = text[idx:idx + len(per['name'])]
        text = text.replace(orig, f'<a href="/persona/{per["slug"]}/">{orig}</a>', 1)
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
                   'indexable': people_indexable(),
                   # 5.1-A: analisis de sus intervenciones + graficos en tiempo real
                   'stats': person_stats(person, appearances),
                   # 5.1-B: «aparece junto a»
                   'junto_a': co_speakers(person)})


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


# ------------------------- 5.1-A: la wiki-red -------------------------
# Decision de David (docs/06 §58): la wiki como red interconectada. Portada
# propia, ficha de persona con analisis de sus intervenciones, graficos en
# tiempo real (CSS puro calculado de la BD en cada peticion: cero librerias)
# y listado interactivo de claims con enlace al post.

# Colores de los graficos (mismos tonos que el semaforo).
CHART_COLORS = {'GREEN': '#16a34a', 'AMBER': '#d97706', 'RED': '#dc2626',
                'GREY': '#9ca3af', 'SIN': '#e5e7eb'}
MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
         'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def _pares_confirmados(person):
    from .models import SpeakerNameProposal
    return list(SpeakerNameProposal.objects.filter(
        confirmed=True, interlocutor=person).values_list('post_id', 'speaker_label'))


def _frases_atribuidas(person):
    """Cuantas frases (segmentos) tiene atribuidas esta persona en total."""
    from apps.analysis.models import TranscriptSegment
    from django.db.models import Q
    pares = _pares_confirmados(person)
    if not pares:
        return 0
    filtro = Q()
    for post_id, label in pares:
        filtro |= Q(post_id=post_id, speaker_label=label)
    return TranscriptSegment.objects.filter(filtro, attribution_uncertain=False).count()


def _donut(conteo, total):
    """Segmentos del donut como gradiente conico CSS + leyenda."""
    if not total:
        return '', []
    orden = [('GREEN', 'Verificadas'), ('AMBER', 'Con matices'),
             ('RED', 'Desmentidas'), ('GREY', 'Opiniones y predicciones')]
    decididos = {c for c, _ in orden}
    sin = sum(n for c, n in conteo.items() if c not in decididos)
    partes, leyenda, acum = [], [], 0.0
    filas = [(c, t, conteo.get(c, 0)) for c, t in orden] + [('SIN', 'Sin decidir aún', sin)]
    for color, titulo, n in filas:
        if not n:
            continue
        pct = n * 100.0 / total
        partes.append(f'{CHART_COLORS[color]} {acum:.2f}% {acum + pct:.2f}%')
        leyenda.append({'css': CHART_COLORS[color], 'titulo': titulo,
                        'n': n, 'pct': round(pct)})
        acum += pct
    return 'conic-gradient(' + ', '.join(partes) + ')', leyenda


def _barras_por_mes(appearances, meses=12):
    """Afirmaciones analizadas por mes (los ultimos N), para las barras."""
    from collections import Counter
    from django.utils import timezone
    hoy = timezone.now()
    claves = []
    y, m = hoy.year, hoy.month
    for _ in range(meses):
        claves.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    claves.reverse()
    cuenta = Counter((a.claim.created_at.year, a.claim.created_at.month)
                     for a in appearances)
    tope = max([cuenta.get(k, 0) for k in claves] + [1])
    return [{'label': MESES[m - 1], 'n': cuenta.get((y, m), 0),
             'pct': round(cuenta.get((y, m), 0) * 100.0 / tope)}
            for (y, m) in claves]


def _videos_de(appearances):
    """Videos donde aparece, con su recuento de afirmaciones (mas reciente primero)."""
    vistos = {}
    for a in appearances:
        p = a.segment.post
        fila = vistos.setdefault(p.pk, {'post': p, 'n': 0})
        fila['n'] += 1
    return sorted(vistos.values(), key=lambda f: f['post'].created_at, reverse=True)


def person_stats(person, appearances):
    from collections import Counter
    conteo = Counter(a.claim.color for a in appearances)
    total = len(appearances)
    gradiente, leyenda = _donut(conteo, total)
    return {'total': total,
            'frases': _frases_atribuidas(person),
            'videos': _videos_de(appearances),
            'donut_css': gradiente, 'donut_leyenda': leyenda,
            'barras': _barras_por_mes(appearances)}


def wiki_home(request):
    """Portada de la wiki: las personas con ficha, los ultimos cambios y los
    numeros del proyecto. En castellano por defecto (decision de David)."""
    from collections import Counter
    from .naming import claims_for_person
    personas = []
    for p in Interlocutor.objects.filter(is_public_figure=True).order_by('name'):
        apps_ = list(claims_for_person(p))
        if not apps_:
            continue
        conteo = Counter(a.claim.color for a in apps_)
        personas.append({'person': p, 'total': len(apps_),
                         'verdes': conteo.get('GREEN', 0),
                         'ambar': conteo.get('AMBER', 0),
                         'rojas': conteo.get('RED', 0)})
    personas.sort(key=lambda f: -f['total'])
    versions = ClaimVersion.objects.select_related('claim').order_by('-created_at')[:15]
    totales = {'claims': Claim.objects.count(),
               'decididos': Claim.objects.filter(
                   color__in=['GREEN', 'AMBER', 'RED', 'GREY']).count(),
               'personas': len(personas)}
    return render(request, 'wiki/home.html',
                  {'personas': personas, 'versions': versions, 'totales': totales,
                   'indexable': people_indexable()})


# ------------------------- 5.1-B: la malla -------------------------
# Los hilos entre paginas: afirmaciones relacionadas por SIGNIFICADO (los
# embeddings pgvector llevan guardandose desde el 9B), «aparece junto a» entre
# personas que comparten videos, y quien dijo cada afirmacion con enlace a su
# ficha. Todo consultas locales: cero llamadas de pago.

def related_claims(claim, n=5):
    """Afirmaciones cercanas por significado. Sin embedding (o sin pgvector,
    como en desarrollo), la seccion simplemente no aparece."""
    if getattr(claim, 'embedding', None) is None:
        return []
    try:
        from pgvector.django import CosineDistance
        return list(Claim.objects.exclude(pk=claim.pk).exclude(embedding=None)
                    .order_by(CosineDistance('embedding', claim.embedding))[:n])
    except Exception:
        return []


def speakers_of_claim(claim):
    """Quien dijo esta afirmacion — solo fichas publicas confirmadas."""
    from .models import SpeakerNameProposal
    out, vistos = [], set()
    for a in claim.appearances.select_related('segment'):
        prop = (SpeakerNameProposal.objects.filter(
                    post_id=a.segment.post_id,
                    speaker_label=a.segment.speaker_label,
                    confirmed=True, interlocutor__is_public_figure=True)
                .select_related('interlocutor').first())
        if prop and prop.interlocutor_id not in vistos:
            vistos.add(prop.interlocutor_id)
            out.append(prop.interlocutor)
    return out


def co_speakers(person):
    """«Aparece junto a»: fichas publicas que comparten videos con esta,
    ordenadas por cuantos comparten."""
    from .models import SpeakerNameProposal
    mis_posts = set(SpeakerNameProposal.objects.filter(
        confirmed=True, interlocutor=person).values_list('post_id', flat=True))
    if not mis_posts:
        return []
    filas = {}
    for prop in (SpeakerNameProposal.objects.filter(
                     post_id__in=mis_posts, confirmed=True,
                     interlocutor__is_public_figure=True)
                 .exclude(interlocutor=person).select_related('interlocutor')):
        fila = filas.setdefault(prop.interlocutor_id,
                                {'person': prop.interlocutor, 'posts': set()})
        fila['posts'].add(prop.post_id)
    out = [{'person': f['person'], 'n': len(f['posts'])} for f in filas.values()]
    out.sort(key=lambda f: -f['n'])
    return out
