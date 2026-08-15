from django.contrib import messages
import re
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


VIDEO_RX = re.compile(r'(youtube\.com|youtu\.be|tiktok\.com|twitch\.tv|spotify\.com)', re.I)


@login_required
def submit(request):
    # Puerta abierta (Fase 3.9 §4): SOLO login + email verificado. Los niveles
    # limitan la CUOTA diaria y los votos, nunca la capacidad de analizar.
    if not request.user.email_verified:
        messages.error(request, 'Verifica tu email para poder analizar (revisa tu buzón o pide un reenvío).')
        return redirect('index')
    if request.method != 'POST':
        return render(request, 'analysis/submit.html')
    url = request.POST.get('url', '').strip()
    topic = request.POST.get('topic', 'otros')
    tags = request.POST.get('tags', '').strip()[:200]
    voluntary_offtopic = request.POST.get('offtopic') == 'on'
    author_opinion = request.POST.get('opinion', '').strip()[:8000]  # 4.2 A5
    author_adult_flag = request.POST.get('is_adult') == 'on'
    if not VIDEO_RX.search(url):
        messages.error(request, 'El enlace debe ser de una plataforma soportada: YouTube, TikTok, Twitch o Spotify.')
        return render(request, 'analysis/submit.html')
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
                               'author_opinion': author_opinion,
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
    from django.db.models import Count, Q
    segments = list(post.transcript_segments.annotate(
        ups=Count('sentence_votes', filter=Q(sentence_votes__value=1)),
        downs=Count('sentence_votes', filter=Q(sentence_votes__value=-1))))
    # 4.2 C2: indice estable por hablante -> color claro ciclable en la plantilla.
    labels = sorted({s.speaker_label for s in segments if s.speaker_label})
    idx = {label: i for i, label in enumerate(labels)}
    for s in segments:
        s.spk_idx = idx.get(s.speaker_label)          # None si sin hablante
        s.spk_color = (s.spk_idx % 8) if s.spk_idx is not None else None
    hide_opinions = bool(u and u.hide_opinions)
    # 4.2 C4: el analisis y su hilo del foro son UNA sola pagina.
    from apps.forum.machina_glue import get_topic_for_post
    topic_obj = get_topic_for_post(post)
    thread_messages = (topic_obj.posts.filter(approved=True)
                       .select_related('poster').order_by('created')
                       if topic_obj else [])
    is_mod = bool(u and (u.is_staff or u.level == 'MOD'))
    # 4.2 H1/H2/H8: estados por mensaje para el hilo
    from apps.forum.models import MessageSensitive, HiddenMessage
    msg_ids = [m.pk for m in thread_messages]
    sensitive_ids = set(MessageSensitive.objects.filter(
        machina_post_id__in=msg_ids).values_list('machina_post_id', flat=True))
    hidden_ids = (set(HiddenMessage.objects.filter(user=u, machina_post_id__in=msg_ids)
                      .values_list('machina_post_id', flat=True)) if u else set())
    for m in thread_messages:
        m.is_sensitive = m.pk in sensitive_ids
        m.hidden_by_me = m.pk in hidden_ids
        m.pm_allowed = bool(u and m.poster and m.poster != u and
                            (m.poster.accept_private_messages or is_mod))
    return render(request, 'analysis/post_detail.html', {
        'post': post, 'segments': segments, 'embed': build_embed(post),
        'hide_opinions': hide_opinions,
        'votes_validate': post.distinct_validation_votes('VALIDATE'),
        'votes_rescue': post.distinct_validation_votes('RESCUE'),
        'name_proposals': post.name_proposals.select_related('interlocutor')
                              .order_by('speaker_label', '-confirmed'),
        'topic_obj': topic_obj, 'thread_messages': thread_messages,
        'is_mod': is_mod, 'is_trending': post.is_trending(),
        'my_subscription': (post.subscriptions.filter(user=u).first() if u else None),
    })


def post_status(request, pk):
    """Sondeo HTMX cada 4 s; se detiene solo cuando el estado es terminal."""
    post = get_object_or_404(Post, pk=pk)
    terminal = post.status in ('DONE', 'OFFTOPIC_SIGNALED', 'OFFTOPIC_RAW', 'FAILED',
                               'PENDING_VALIDATION', 'HELD_FOR_REVIEW',
                               'VALIDATION_EXPIRED')
    resp = render(request, 'partials/post_status.html', {'post': post})
    if terminal:
        resp['HX-Reswap'] = 'outerHTML'
        resp.status_code = 286  # HTMX: stop polling
    return resp


def _require_mod(user):
    return user.is_authenticated and (user.is_staff or user.level == 'MOD')


@login_required
def relegate(request, pk):
    """4.2 A2 (decision de David): relegar a Off-Topic es SIEMPRE accion manual
    de moderador. El clasificador solo sugiere (post.offtopic_suggested)."""
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    post.category = 'OFFTOPIC'
    post.status = 'OFFTOPIC_SIGNALED'
    post.relegation_reason = (request.POST.get('reason', '').strip()[:200]
                              or 'Relegado por moderación')
    post.save(update_fields=['category', 'status', 'relegation_reason'])
    from apps.forum.machina_glue import move_topic
    move_topic(post)
    messages.success(request, 'Post relegado a Off-Topic.')
    return redirect('post_detail', pk=pk)


@login_required
def unrelegate(request, pk):
    """Devolver un post a Principal (tambien repara los relegados por el
    clasificador ANTES del 4.2, como el primer video de la siembra)."""
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    post.category = 'MAIN'
    post.relegation_reason = ''
    if post.status in ('OFFTOPIC_SIGNALED', 'OFFTOPIC_RAW'):
        from .services import open_validation_window
        open_validation_window(post)  # deja status PENDING_VALIDATION con plazo nuevo
    post.save()
    from apps.forum.machina_glue import move_topic
    move_topic(post)
    messages.success(request, 'Post devuelto al foro Principal.')
    return redirect('post_detail', pk=pk)


@login_required
def segment_vote(request, pk, direction):
    """4.2 H5: ▲/▼ por oracion. Repetir el mismo voto lo retira; el contrario lo cambia.
    Umbral de ▼ (SystemSetting segment_opus_downvotes) -> re-analisis Opus de ESA oracion."""
    from .models import TranscriptSegment, SegmentVote
    from apps.panel.models import SystemSetting
    seg = get_object_or_404(TranscriptSegment, pk=pk)
    if request.method != 'POST' or seg.post.status != 'DONE':
        return redirect('post_detail', pk=seg.post_id)
    value = 1 if direction == 'up' else -1
    obj, created = SegmentVote.objects.get_or_create(segment=seg, user=request.user,
                                                     defaults={'value': value})
    if not created:
        if obj.value == value:
            obj.delete()
        else:
            obj.value = value
            obj.save(update_fields=['value'])
    downs = seg.sentence_votes.filter(value=-1).count()
    if (value == -1 and not seg.opus_rescanned
            and downs > SystemSetting.get_int('segment_opus_downvotes', 5)):
        from .tasks import opus_rescan_segment
        opus_rescan_segment.delay(seg.pk)
        messages.info(request, 'Oración muy discutida: se re-analizará con el modelo premium.')
    return redirect(f"/post/{seg.post_id}/#seg-{seg.pk}")


@login_required
def message_report(request, mpost_id):
    """4.2 H1: reporte de inadecuado. Al superar el umbral, difuminado para todos."""
    from apps.forum.models import MessageReport, MessageSensitive
    from apps.panel.models import SystemSetting
    if request.method == 'POST':
        MessageReport.objects.get_or_create(machina_post_id=mpost_id, user=request.user)
        n = MessageReport.objects.filter(machina_post_id=mpost_id).count()
        if n >= SystemSetting.get_int('message_sensitive_reports', 5):
            MessageSensitive.objects.get_or_create(machina_post_id=mpost_id,
                                                   defaults={'auto': True})
        messages.success(request, 'Reporte registrado. Gracias por cuidar el foro.')
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def message_hide_toggle(request, mpost_id):
    """4.2 H2: difuminado PERSONAL, reversible, por mensaje."""
    from apps.forum.models import HiddenMessage
    if request.method == 'POST':
        obj, created = HiddenMessage.objects.get_or_create(
            machina_post_id=mpost_id, user=request.user)
        if not created:
            obj.delete()
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def message_sensitive_toggle(request, mpost_id):
    """4.2 H1: el moderador/superusuario difumina o restaura PARA TODOS."""
    from apps.forum.models import MessageSensitive
    if request.method == 'POST' and _require_mod(request.user):
        obj, created = MessageSensitive.objects.get_or_create(
            machina_post_id=mpost_id, defaults={'marked_by': request.user})
        if not created:
            obj.delete()
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def subscribe(request, pk):
    """4.2 D3: la campanita del post — el usuario elige a que se suscribe.
    Sin casillas marcadas = darse de baja del todo."""
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST':
        return redirect('post_detail', pk=pk)
    from .models import PostSubscription
    flags = {'on_analysis': request.POST.get('on_analysis') == 'on',
             'on_messages': request.POST.get('on_messages') == 'on',
             'on_trending': request.POST.get('on_trending') == 'on'}
    if any(flags.values()):
        PostSubscription.objects.update_or_create(post=post, user=request.user,
                                                  defaults=flags)
        messages.success(request, 'Suscripción guardada.')
    else:
        PostSubscription.objects.filter(post=post, user=request.user).delete()
        messages.success(request, 'Suscripción retirada.')
    return redirect('post_detail', pk=pk)


@login_required
def reply(request, pk):
    """4.2 C4: responder en el hilo SIN salir de la pagina del analisis."""
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST':
        return redirect('post_detail', pk=pk)
    if not request.user.email_verified:
        messages.error(request, 'Verifica tu email para poder comentar.')
        return redirect('post_detail', pk=pk)
    content = request.POST.get('content', '').strip()[:8000]
    if content:
        from apps.forum.machina_glue import add_reply
        add_reply(post, request.user, content)
        messages.success(request, 'Comentario publicado.')
    return redirect(f"{request.path.replace('/reply/', '/')}#hilo")


@login_required
def vote(request, pk, kind):
    post = get_object_or_404(Post, pk=pk)
    ok, msg = cast_vote(post, request.user, kind.upper())
    (messages.success if ok else messages.error)(request, msg)
    return redirect('post_detail', pk=pk)


def search(request):
    """Busqueda unificada, adaptada al 4.2 (G1):
    - Analisis: por TITULO real (F1), etiquetas y tema — ya no por URL en bruto.
    - Conversacion: los MENSAJES del hilo (machina) son buscables — el hilo vive
      dentro de la pagina del analisis (C4), asi que el resultado lleva alli.
    - Transcripciones: frases COMPLETAS (D1) con su hablante en el resultado.
    - Wiki: igual que antes + la redaccion del veredicto."""
    from django.contrib.postgres.search import SearchQuery, SearchVector
    from machina.core.db.models import get_model
    from apps.wiki.models import Claim
    from .models import TranscriptSegment
    MPost = get_model('forum_conversation', 'Post')
    q = request.GET.get('q', '').strip()
    scope = request.GET.get('scope', 'all')
    results = {'posts': [], 'claims': [], 'segments': [], 'messages': []}
    if q:
        query = SearchQuery(q, config='spanish')
        if scope in ('all', 'posts'):
            results['posts'] = Post.objects.annotate(
                sv=SearchVector('title', 'tags', 'topic', config='spanish')
            ).filter(sv=query)[:20]
        if scope in ('all', 'forum'):
            # El contenido machina es MarkupText: se busca su texto crudo.
            results['messages'] = (MPost.objects.filter(approved=True).annotate(
                sv=SearchVector('content', config='spanish')).filter(sv=query)
                .select_related('topic', 'poster')[:20])
        if scope in ('all', 'wiki'):
            results['claims'] = Claim.objects.annotate(
                sv=SearchVector('text_original', 'what_is_claimed',
                                'what_evidence_says', config='spanish')
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
        if post.trending_notified and not post.is_trending():
            post.trending_notified = False  # se rearma al caer del umbral
            post.save(update_fields=['trending_notified'])
    else:
        # 4.2 D4: al CRUZAR el umbral (no en cada voto) avisa una sola vez.
        if not post.trending_notified and post.is_trending():
            post.trending_notified = True
            post.save(update_fields=['trending_notified'])
            from .tasks import notify_post_event
            notify_post_event(post, 'trending', '🔥 El post está en Trending')
        from .tasks import maybe_trigger_opus_rescan
        if maybe_trigger_opus_rescan(post):  # unica puerta al reescaneo (Fase 3.4 §6)
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
