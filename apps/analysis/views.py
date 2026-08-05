from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.models import AnalysisCredit
from apps.embeds.adapters import detect_platform, build_embed
from .models import AnalysisRequest, Post
from .services import cast_vote
from .tasks import run_cheap_phase


def index(request):
    """Portada Fase 3: Recientes / Mas votados (7 dias) / Reincidentes / Por tema / Off-Topic."""
    from django.db.models import Count, Q
    from django.utils import timezone as tz
    from .models import TOPICS, Channel
    topic = request.GET.get('tema', '')
    base = Post.objects.filter(category='MAIN')
    if topic:
        base = base.filter(topic=topic)
    recent = base.order_by('-created_at')[:20]
    window = tz.now() - tz.timedelta(days=7)
    top = base.annotate(n=Count('votes', filter=Q(votes__created_at__gte=window)))               .filter(n__gt=0).order_by('-n')[:10]
    repeat_channels = [c for c in Channel.objects.order_by('-created_at')[:50]
                       if c.meets_threshold()][:10]
    offtopic = Post.objects.filter(category='OFFTOPIC').order_by('-created_at')[:20]
    return render(request, 'analysis/index.html', {
        'recent': recent, 'top': top, 'repeat_channels': repeat_channels,
        'offtopic': offtopic, 'topics': TOPICS, 'active_topic': topic})


@login_required
def submit(request):
    if request.method != 'POST':
        return render(request, 'analysis/submit.html')
    url = request.POST.get('url', '').strip()
    topic = request.POST.get('topic', 'otros')
    tags = request.POST.get('tags', '').strip()[:200]
    voluntary_offtopic = request.POST.get('offtopic') == 'on'
    author_adult_flag = request.POST.get('is_adult') == 'on'
    platform, external_id = detect_platform(url)
    if not platform:
        messages.error(request, 'Plataforma no soportada todavía. Se mostrará como tarjeta-enlace.')
        platform = 'link'

    with transaction.atomic():
        post, created = Post.objects.get_or_create(
            url=url, defaults={'author': request.user, 'platform': platform,
                               'external_id': external_id or '',
                               'voluntary_offtopic': voluntary_offtopic,
                               'topic': topic, 'tags': tags,
                               'is_adult': author_adult_flag,
                               'adult_flag_source': 'author' if author_adult_flag else ''})
        AnalysisRequest.objects.create(post=post, user=request.user,
                                       served_from_cache=not created)
        if not created:
            # Cache: gratis, instantaneo, pero cuenta como solicitante (umbral 5/10/5)
            return redirect('post_detail', pk=post.pk)

        if voluntary_offtopic:
            post.category = 'OFFTOPIC'
            post.status = 'OFFTOPIC_RAW'  # coste CERO hasta reunir 10 votos
            post.save()
            return redirect('post_detail', pk=post.pk)

        if not request.user.can_spend_credit():
            post.delete()
            messages.error(request, 'Has agotado tu cupo diario de análisis.')
            return redirect('index')
        from .models import DailyBudget
        from django.conf import settings as dj
        from django.utils import timezone as tz
        today = DailyBudget.objects.filter(date=tz.localdate()).first()
        if today and float(today.spent_eur) >= dj.DAILY_BUDGET_EUR:
            waiting = Post.objects.filter(status='NEW').count() + 1
            messages.info(request, f'Presupuesto diario agotado (proyecto sin ánimo de '
                          f'lucro). Tu análisis es el nº {waiting} de mañana. '
                          f'Si donas, el depósito crece.')
        AnalysisCredit.objects.create(user=request.user, post=post)  # sin devolucion

    run_cheap_phase.delay(post.pk)
    return redirect('post_detail', pk=post.pk)


def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)
    u = request.user if request.user.is_authenticated else None
    if post.is_adult and (not u or not u.is_adult or u.hide_adult):
        blocked = (not u) or (not u.is_adult)
        if blocked:
            return render(request, 'analysis/adult_blocked.html', status=403)
    segments = post.transcript_segments.all()
    hide_opinions = bool(u and u.hide_opinions)
    return render(request, 'analysis/post_detail.html', {
        'post': post, 'segments': segments, 'embed': build_embed(post),
        'hide_opinions': hide_opinions,
        'votes_validate': post.distinct_validation_votes('VALIDATE'),
        'votes_rescue': post.distinct_validation_votes('RESCUE'),
        'name_proposals': post.name_proposals.select_related('interlocutor')
                              .order_by('speaker_label', '-confirmed'),
    })


def post_status(request, pk):
    """Sondeo HTMX cada 4 s; se detiene solo cuando el estado es terminal."""
    post = get_object_or_404(Post, pk=pk)
    terminal = post.status in ('DONE', 'OFFTOPIC_SIGNALED', 'OFFTOPIC_RAW', 'FAILED',
                               'PENDING_VALIDATION', 'HELD_FOR_REVIEW')
    resp = render(request, 'partials/post_status.html', {'post': post})
    if terminal:
        resp['HX-Reswap'] = 'outerHTML'
        resp.status_code = 286  # HTMX: stop polling
    return resp


@login_required
def vote(request, pk, kind):
    post = get_object_or_404(Post, pk=pk)
    ok, msg = cast_vote(post, request.user, kind.upper())
    (messages.success if ok else messages.error)(request, msg)
    return redirect('post_detail', pk=pk)


def search(request):
    """Busqueda unificada (quiz 12A) con selector: Todo/Foro/Wiki/Transcripciones."""
    from django.contrib.postgres.search import SearchQuery, SearchVector
    from apps.wiki.models import Claim
    from .models import TranscriptSegment
    q = request.GET.get('q', '').strip()
    scope = request.GET.get('scope', 'all')
    results = {'posts': [], 'claims': [], 'segments': []}
    if q:
        query = SearchQuery(q, config='spanish')
        if scope in ('all', 'forum'):
            results['posts'] = Post.objects.annotate(
                sv=SearchVector('title', 'url', config='spanish')).filter(sv=query)[:20]
        if scope in ('all', 'wiki'):
            results['claims'] = Claim.objects.annotate(
                sv=SearchVector('text_original', 'what_evidence_says', config='spanish')
            ).filter(sv=query)[:20]
        if scope in ('all', 'transcripts'):
            results['segments'] = TranscriptSegment.objects.annotate(
                sv=SearchVector('text', config='spanish')).filter(sv=query
            ).select_related('post')[:20]
    return render(request, 'analysis/search.html',
                  {'q': q, 'scope': scope, 'results': results})


@login_required
def vote_speaker_name(request, proposal_id):
    from apps.wiki.models import SpeakerNameProposal
    from apps.wiki.naming import vote_proposal
    prop = get_object_or_404(SpeakerNameProposal, pk=proposal_id)
    ok, msg = vote_proposal(prop, request.user)
    (messages.success if ok else messages.error)(request, msg)
    return redirect('post_detail', pk=prop.post_id)


@login_required
def upvote(request, pk):
    """Voto positivo (los negativos no existen: decision congelada)."""
    from apps.forum.models import Vote
    post = get_object_or_404(Post, pk=pk)
    obj, created = Vote.objects.get_or_create(post=post, user=request.user)
    if not created:
        obj.delete()
    else:
        from .services import should_opus_rescan
        if should_opus_rescan(post):
            from .tasks import opus_rescan
            opus_rescan.delay(post.pk)
            messages.info(request, 'Este contenido ha alcanzado gran interés: '
                                   're-verificación con el modelo mayor en marcha.')
    return redirect('post_detail', pk=pk)


def donations_page(request):
    """Pagina publica de donaciones: objetivo, progreso, PayPal (Bizum ONG llegara con la asociacion)."""
    from apps.panel.models import Donation, SystemSetting
    from apps.panel.services import live_monthly_cap
    cap, donated, base = live_monthly_cap()
    goal = SystemSetting.get_int('donation_goal_eur', 60)
    paypal = SystemSetting.objects.filter(key='paypal_url').first()
    return render(request, 'analysis/donations.html', {
        'donated': donated, 'goal': goal, 'base': base, 'cap': cap,
        'paypal_url': paypal.value if paypal else '',
        'count': Donation.objects.count()})
