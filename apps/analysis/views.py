from django.contrib import messages
import re
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db import models, transaction
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponsePermanentRedirect
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
    # 4.3-A.8 (decision de David): el contenido +18 NO vive en los listados
    # publicos. Tiene su propia sala cerrada (/mas18/) y solo entra quien es mayor
    # de edad segun la fecha de nacimiento del registro. Antes de esto, un post
    # marcado +18 salia en portada a cualquiera (el candado solo estaba en la
    # pagina del post): el aviso llegaba tarde, con el titular ya leido.
    base = Post.objects.filter(category='MAIN').exclude(is_adult=True)
    if topic:
        base = base.filter(topic=topic)
    recent = base.order_by('-created_at')[:20]
    window = tz.now() - tz.timedelta(days=7)
    top = base.annotate(n=Count('votes', filter=Q(votes__created_at__gte=window)))               .filter(n__gt=0).order_by('-n')[:10]
    repeat_channels = [c for c in Channel.objects.order_by('-created_at')[:50]
                       if c.meets_threshold()][:10]
    offtopic = (Post.objects.filter(category='OFFTOPIC').exclude(is_adult=True)
                .order_by('-created_at')[:20])
    return render(request, 'analysis/index.html', {
        'recent': recent, 'top': top, 'repeat_channels': repeat_channels,
        'offtopic': offtopic, 'topics': TOPICS, 'active_topic': topic,
        'adult_room': _can_see_adult(request)})


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

    # 4.3-A.8 (decision de David): ANTES de postear se comprueba el video —
    # titulo (para colocarlo bien), duracion (para el aviso de donacion) y si es
    # +18 (para que nazca ya en la sala cerrada, no despues). Si el pre-chequeo
    # falla, seguimos con lo que haya: nunca se cierra la puerta por eso.
    from apps.embeds.adapters import probe
    ficha = probe(url, platform)
    edad_plataforma = ficha['age_limit'] >= 18

    with transaction.atomic():
        post, created = Post.objects.get_or_create(
            url=url, defaults={'author': request.user, 'platform': platform,
                               'external_id': external_id or '',
                               'voluntary_offtopic': voluntary_offtopic,
                               'topic': topic, 'tags': tags,
                               'author_opinion': author_opinion,
                               'title': ficha['title'],
                               'duration_seconds': ficha['duration_seconds'],
                               'is_adult': author_adult_flag or edad_plataforma,
                               'adult_flag_source': ('author' if author_adult_flag
                                                     else 'platform' if edad_plataforma else '')})
        if created and not post.title:
            from apps.embeds.adapters import fetch_title
            title = fetch_title(url, platform)  # I2: titulo inmediato (oEmbed, 4 s max)
            if title:
                post.title = title
                post.save(update_fields=['title'])
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
        # 4.3-F: el aviso de "presupuesto agotado" comparaba con settings.DAILY_BUDGET_EUR,
        # una cifra CABLEADA (3,00 €) que ya no era la de nadie. El presupuesto vivo
        # se calcula desde el panel; dos fuentes de verdad para el mismo número es
        # justo el fallo que el operador cazó en 98d3442.
        from .services import budget_left_today
        if budget_left_today() <= 0:
            waiting = Post.objects.filter(status='NEW').count() + 1
            messages.info(request, f'Presupuesto diario agotado (proyecto sin ánimo de '
                          f'lucro). Tu análisis es el nº {waiting} de mañana. '
                          f'Si donas, el depósito crece.')
        AnalysisCredit.objects.create(user=request.user, post=post)  # sin devolucion

    # 4.3-A.8: los dos avisos del pre-chequeo. Son AVISOS, no muros: la puerta de
    # submit sigue siendo login + email verificado (decision congelada).
    if post.is_adult and post.adult_flag_source == 'platform':
        messages.warning(request, 'La plataforma marca este vídeo como +18: el análisis '
                         'irá a la sala para mayores de edad y no aparecerá en portada.')
    from .services import free_minutes, suggested_donation_eur, video_minutes
    donacion = suggested_donation_eur(post)
    if donacion:
        messages.info(request, f'Este vídeo dura {video_minutes(post)} minutos y se '
                      f'analizará entero. Por encima de {free_minutes()} minutos el coste '
                      f'lo sostienen las donaciones: si puedes, una de {donacion:.2f} € '
                      f'cubre este análisis. No es obligatoria y tu vídeo ya está en cola.')

    # 4.3-F (decisión de David): si el vídeo se lleva más de media asignación
    # diaria, NO se analiza al momento. Entra en cola y se lanza cuando haya
    # depósito, o antes si alguien lo apadrina. Nunca se rechaza, y el aviso
    # explica exactamente por qué y cuánto.
    from .services import needs_sponsorship
    a_la_cola, coste, sugerida = needs_sponsorship(post)
    if a_la_cola:
        post.status = 'AWAITING_BUDGET'
        post.save(update_fields=['status'])
        messages.info(request, f'Este vídeo se lleva más de media asignación diaria '
                      f'(cuesta unos {coste:.2f} €), así que entra en cola: se '
                      f'analizará solo en cuanto haya depósito, normalmente mañana. '
                      f'Si quieres que salga antes, puedes apadrinarlo con una '
                      f'donación de {sugerida:.2f} €.')
        return redirect('post_detail', pk=post.pk)

    run_cheap_phase.delay(post.pk)
    return redirect('post_detail', pk=post.pk)


@login_required
def greenlight(request, pk):
    """4.3-F: dar paso a un análisis en cola sin esperar al depósito. Solo
    moderación. Es acción deliberada y con coste, como el reanálisis."""
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    if post.status != 'AWAITING_BUDGET':
        messages.error(request, 'Este análisis no está en cola por presupuesto.')
        return redirect('post_detail', pk=pk)
    post.status = 'NEW'
    post.save(update_fields=['status'])
    run_cheap_phase.delay(post.pk)
    from apps.panel.models import AuditLog
    AuditLog.objects.create(action='analysis_greenlit',
                            detail=f'post {post.pk} adelantado por {request.user}')
    messages.success(request, 'Análisis adelantado: entra en marcha ahora.')
    return redirect('post_detail', pk=pk)


def _can_see_adult(request):
    """4.3-A.8: mayor de edad SEGUN LA FECHA DE NACIMIENTO del registro. Sin
    sesion, o sin fecha, o con menos de 18: no. La propiedad User.is_adult ya
    calcula la edad; aqui solo se le suma el requisito de estar identificado."""
    u = request.user if request.user.is_authenticated else None
    return bool(u and u.is_adult)


def _adult_blocked(request, post):
    return post.is_adult and not _can_see_adult(request)


def adult_room(request):
    """Sala +18: cerrada al publico. Los analisis marcados para mayores de edad
    no aparecen en portada ni en el buscador; viven aqui, y aqui solo entra quien
    tiene 18 anos cumplidos segun su fecha de nacimiento."""
    if not _can_see_adult(request):
        return render(request, 'analysis/adult_blocked.html', status=403)
    posts = Post.objects.filter(is_adult=True).order_by('-created_at')[:50]
    return render(request, 'analysis/adult_room.html', {'posts': posts})


def _post_context(request, post):
    """4.3-A.2 L2: contexto del post — lo comparten la pagina completa y el
    fragmento que se intercambia EN EL SITIO (sin recargar, sin mover el scroll)
    cuando el analisis termina."""
    # 4.9-A: el libro de cuentas del analisis, para el staff (transparencia)
    costes_filas = costes_total = None
    if request.user.is_authenticated and request.user.is_staff:
        from apps.analysis.costs import post_breakdown
        costes_filas, costes_total = post_breakdown(post)
    u = request.user if request.user.is_authenticated else None
    from django.db.models import Count, Q
    # 4.3-A.5 O1 (fallo de raíz): SIN order_by la BD devolvía los segmentos en orden
    # de inserción, no cronológico — la conversación aparecía descolocada. Se ordena
    # por tiempo de inicio para que el diálogo tenga continuidad real.
    segments = list(post.transcript_segments.annotate(
        ups=Count('sentence_votes', filter=Q(sentence_votes__value=1)),
        downs=Count('sentence_votes', filter=Q(sentence_votes__value=-1)))
        .order_by('start_seconds', 'pk'))
    # 4.2 C2: indice estable por hablante -> color claro ciclable en la plantilla.
    labels = sorted({s.speaker_label for s in segments if s.speaker_label})
    idx = {label: i for i, label in enumerate(labels)}
    for s in segments:
        s.spk_idx = idx.get(s.speaker_label)          # None si sin hablante
        s.spk_color = (s.spk_idx % 8) if s.spk_idx is not None else None
    # 4.2.1 I7: la MISMA numeracion "Hablante N" en transcripcion y "¿Quien habla?"
    speaker_names = {label: i + 1 for label, i in idx.items()}
    # 4.3-E (decision de David): en cuanto un hablante queda CONFIRMADO, su nombre
    # sustituye a "Hablante N" en los dos sitios — la ficha de ¿Quién habla? y cada
    # frase de la transcripcion. Dejar el numero despues de identificarlo obliga al
    # lector a traducir mentalmente en cada frase.
    confirmadas = dict(post.name_proposals.filter(confirmed=True)
                       .values_list('speaker_label', 'candidate_name'))
    for s in segments:
        s.spk_name = confirmadas.get(s.speaker_label, '')
    # 4.4-B — EL ESCAPARATE. Hasta hoy esta plantilla pintaba SOLO la señal barata
    # del barrido, y no habia ni una referencia a los veredictos: aunque un video
    # se verificara entero, con fuentes y semaforo, la transcripcion seguia diciendo
    # «Afirmación factual (no verificada)» para siempre. El trabajo caro se hacia,
    # se pagaba, se guardaba en la wiki... y no aparecia donde el lector lo busca.
    # (Datos del 2026-08-23: 96 afirmaciones con veredicto, cero visibles.)
    from apps.wiki.models import ClaimAppearance
    veredictos = {}
    for ap in (ClaimAppearance.objects
               .filter(segment__post=post)
               .select_related('claim')
               .prefetch_related('claim__sources')):
        veredictos.setdefault(ap.segment_id, ap.claim)
    for s in segments:
        s.claim = veredictos.get(s.pk)
    # Lista (no diccionario): las plantillas de Django no saben consultar un dict
    # por una clave variable, y meter un filtro nuevo solo para esto seria peor.
    speaker_rows = [{'label': label, 'num': i + 1, 'color': i % 8,
                     'name': confirmadas.get(label, '')}
                    for label, i in sorted(idx.items(), key=lambda kv: kv[1])]
    # 4.4-I: las frases de atribucion incierta se listan en «¿Quien habla?» para
    # que la comunidad las resuelva (cualquier usuario con sesion, un clic).
    uncertain_rows = [{'seg': s, 'options': speaker_rows}
                      for s in segments if s.attribution_uncertain]
    hide_opinions = bool(u and u.hide_opinions)
    # 4.2 C4: el analisis y su hilo del foro son UNA sola pagina.
    from apps.forum.machina_glue import get_topic_for_post
    from .services import (identification_gate, needs_sponsorship, speaker_identification,
                           waiting_for_identification, min_identified_percent)
    topic_obj = get_topic_for_post(post)
    is_mod = bool(u and (u.is_staff or u.level == 'MOD'))
    # 4.4-G: aviso visible cuando la identificacion frena la verificacion, y las
    # cuatro etapas de la llave inglesa (solo se pintan para moderacion).
    waiting_ident = waiting_for_identification(post)[0]
    relaunch_rows = relaunch_options(post) if is_mod else []
    # 4.3-F: cifras del cartel de la cola (solo se pintan si el post está en ella).
    _en_cola, queue_cost, queue_sponsor = needs_sponsorship(post)
    thread_messages, page_obj, first_unread_pk, newest_pk = _thread_page(topic_obj, u, request)
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
    return {
        'costes_filas': costes_filas, 'costes_total': costes_total,
        'post': post, 'segments': segments, 'embed': build_embed(post),
        'hide_opinions': hide_opinions,
        'votes_validate': post.distinct_validation_votes('VALIDATE'),
        'votes_rescue': post.distinct_validation_votes('RESCUE'),
        # 4.3-A.1 K3 (decision de David): SOLO propuestas de usuarios o confirmadas.
        # Los candidatos automaticos (OCR/rotulos) producian basura tipo creditos
        # de edicion y quedan desactivados; la migracion 0007 purga los existentes.
        'name_proposals': post.name_proposals.filter(
                              models.Q(source='user') | models.Q(confirmed=True))
                              .select_related('interlocutor')
                              .order_by('speaker_label', '-confirmed'),
        'queue_cost': queue_cost, 'queue_sponsor': queue_sponsor,
        'speaker_names': speaker_names, 'speaker_rows': speaker_rows,
        'identification': speaker_identification(post),
        'can_validate': identification_gate(post)[0],
        'waiting_ident': waiting_ident, 'ident_min': min_identified_percent(),
        'relaunch_rows': relaunch_rows,
        'uncertain_rows': uncertain_rows,
        'page_obj': page_obj,
        'thread_total': page_obj.paginator.count if page_obj else 0,
        'first_unread_pk': first_unread_pk, 'newest_pk': newest_pk,
        'topic_obj': topic_obj, 'thread_messages': thread_messages,
        'is_mod': is_mod, 'is_trending': post.is_trending(),
        'my_subscription': (post.subscriptions.filter(user=u).first() if u else None),
    }


def post_detail(request, pk, slug=None):
    post = get_object_or_404(Post, pk=pk)
    # 5.0-C: URL canonica /post/<slug>/<pk>/. Si llegan por la numerica o con un
    # slug desactualizado, 301 a la buena conservando ?pagina= y demas parametros.
    if post.slug and slug != post.slug:
        destino = post.get_absolute_url()
        if request.META.get('QUERY_STRING'):
            destino += '?' + request.META['QUERY_STRING']
        return HttpResponsePermanentRedirect(destino)
    if _adult_blocked(request, post):
        return render(request, 'analysis/adult_blocked.html', status=403)
    return render(request, 'analysis/post_detail.html', _post_context(request, post))


def post_body_fragment(request, pk):
    """4.3-A.2 L2: cuerpo del post (rejilla + señales + claims) como fragmento
    htmx — el contenido nuevo aparece por arte de magia, sin recarga."""
    post = get_object_or_404(Post, pk=pk)
    if _adult_blocked(request, post):
        return render(request, 'analysis/adult_blocked.html', status=403)
    return render(request, 'partials/post_body.html', _post_context(request, post))


TERMINAL_STATUSES = ('DONE', 'OFFTOPIC_SIGNALED', 'OFFTOPIC_RAW', 'FAILED',
                     'PENDING_VALIDATION', 'HELD_FOR_REVIEW', 'VALIDATION_EXPIRED')


def post_status(request, pk):
    """Sondeo HTMX cada 4 s; se detiene solo cuando el estado es terminal."""
    post = get_object_or_404(Post, pk=pk)
    terminal = post.status in TERMINAL_STATUSES
    resp = render(request, 'partials/post_status.html', {'post': post})
    # 4.3-A.2 L3 (decision de David): CERO recargas. En la transicion
    # corriendo->terminal se emiten dos eventos htmx: intercambiar el cuerpo del
    # post EN EL SITIO (isttBodyRefresh) y cantar un bocadillo (isttToast).
    prev = request.GET.get('prev', '')
    if terminal and prev and prev not in TERMINAL_STATUSES:
        import json
        resp['HX-Trigger'] = json.dumps({
            'isttBodyRefresh': {'url': f'/post/{post.pk}/fragmento/cuerpo/',
                                'target': '#post-body'},
            'isttToast': {'text': 'La transcripción y el análisis ya están aquí',
                          'url': '#post-body'},
        })
    if terminal:
        resp['HX-Reswap'] = 'outerHTML'
        resp.status_code = 286  # HTMX: stop polling
    return resp


def _require_mod(user):
    return user.is_authenticated and (user.is_staff or user.level == 'MOD')


def _thread_page(topic_obj, u, request, per_page=20):
    """4.3-A J4: pagina del hilo (foro clasico: 20/pagina) + primer no leido.
    Registra el punto de lectura del usuario (TopicRead) al servir la pagina."""
    from django.core.paginator import Paginator
    if not topic_obj:
        return [], None, None, 0
    qs = topic_obj.posts.filter(approved=True).select_related('poster').order_by('created')
    paginator = Paginator(qs, per_page)
    first_unread_pk = None
    if u:
        from apps.forum.models import TopicRead
        tr, _ = TopicRead.objects.get_or_create(topic_id=topic_obj.pk, user=u)
        unread = qs.filter(pk__gt=tr.last_post_id).first()
        first_unread_pk = unread.pk if unread else None
    raw = request.GET.get('pagina', '')
    if raw.isdigit():
        number = int(raw)
    elif first_unread_pk:  # sin pagina pedida: aterrizar donde estan los nuevos
        idx = list(qs.values_list('pk', flat=True)).index(first_unread_pk)
        number = idx // per_page + 1
    else:
        number = paginator.num_pages  # convencion de foro: la ultima pagina
    page_obj = paginator.get_page(number)
    messages_list = list(page_obj.object_list)
    # 4.3-G: numero de mensaje dentro del HILO (#1, #2, ...), no de la pagina:
    # es la referencia con la que se cita en cualquier foro.
    inicio = page_obj.start_index()
    for i, m in enumerate(messages_list):
        m.first_unread = (m.pk == first_unread_pk)
        m.number = inicio + i
    # 4.3-G: el "Mensajes: N" de la ficha del autor, en UNA sola consulta para
    # toda la pagina. OJO (trampa conocida): sin .order_by() vacio, el ordering
    # del Meta de machina se cuela en el GROUP BY y el recuento sale partido.
    autores = {m.poster_id for m in messages_list if m.poster_id}
    if autores:
        from django.db.models import Count as _Count
        recuento = dict(qs.model.objects.filter(poster_id__in=autores, approved=True)
                        .order_by().values_list('poster_id')
                        .annotate(n=_Count('pk')))
        for m in messages_list:
            m.author_posts = recuento.get(m.poster_id, 0)
    newest = qs.last()
    newest_pk = newest.pk if newest else 0
    if u and messages_list:
        from apps.forum.models import TopicRead
        TopicRead.objects.filter(topic_id=topic_obj.pk, user=u).update(
            last_post_id=newest_pk)
    return messages_list, page_obj, first_unread_pk, newest_pk


def post_thread_fragment(request, pk):
    """4.2.1 I3: los mensajes del hilo, como fragmento htmx (sondeo cada 12 s)."""
    post = get_object_or_404(Post, pk=pk)
    u = request.user if request.user.is_authenticated else None
    is_mod = bool(u and (u.is_staff or u.level == 'MOD'))
    from apps.forum.machina_glue import get_topic_for_post
    topic_obj = get_topic_for_post(post)
    thread_messages, page_obj, _first, newest_pk = _thread_page(topic_obj, u, request)
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
    resp = render(request, 'partials/thread_messages.html',
                  {'post': post, 'thread_messages': thread_messages, 'is_mod': is_mod,
                   'page_obj': page_obj, 'newest_pk': newest_pk})
    # 4.3-A.2 L3: si hay mensajes posteriores a los que el navegador conocia,
    # ademas del intercambio silencioso, un bocadillo lo canta (SIEMPRE: es
    # independiente de las suscripciones de la campana).
    try:
        conocido = int(request.GET.get('ultimo', 0))
    except ValueError:
        conocido = 0
    if conocido and newest_pk > conocido:
        import json
        nuevos = sum(1 for m in thread_messages if m.pk > conocido)
        texto = ('Nuevo mensaje en la conversación' if nuevos <= 1
                 else f'{nuevos} mensajes nuevos en la conversación')
        resp['HX-Trigger'] = json.dumps({'isttToast': {'text': texto, 'url': '#hilo'}})
    return resp


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
def reanalyze(request, pk):
    """4.3-A.5 O3: reanálisis manual. Desde el 4.4-G es la etapa (a) de la llave
    inglesa y pasa por su página de confirmación con el coste (decisión de
    David: confirmación para cualquier opción). La URL se conserva."""
    return relaunch(request, pk, 'cheap')


# 4.4-G (encargo de David, 2026-08-24): la LLAVE INGLESA. Junto al estado del
# post, solo moderación/superusuario, cuatro etapas relanzables con su coste
# delante. Sin JavaScript: POST -> pagina de confirmacion con el coste ->
# segundo POST (confirm=1) ejecuta. AuditLog por accion; todo pasa por
# DailyBudget.try_spend dentro de las tareas.
RELAUNCH_STAGES = ['cheap', 'dating', 'verdicts', 'deep']


def relaunch_options(post):
    """Las cuatro etapas con etiqueta, coste estimado y si estan disponibles en
    el estado actual del post. Lista (no dict): la plantilla lo recorre."""
    from .services import cost_cheap_eur, cost_full_eur, cost_dating_eur, cost_deep_eur
    tiene_frases = post.transcript_segments.exists()
    return [
        {'stage': 'cheap', 'label': 'Transcripción y voces', 'cost': cost_cheap_eur(post),
         'available': True,
         'note': 'Borra la transcripción, las voces y las identificaciones de este vídeo.'},
        {'stage': 'dating', 'label': 'Fecha del suceso', 'cost': cost_dating_eur(post),
         'available': tiene_frases, 'note': 'Solo la datación; céntimos.'},
        {'stage': 'verdicts', 'label': 'Veredictos', 'cost': cost_full_eur(post),
         'available': tiene_frases,
         'note': 'Conserva transcripción y hablantes; rehace la verificación con fuentes.'},
        {'stage': 'deep', 'label': 'Análisis profundo', 'cost': cost_deep_eur(post),
         'available': post.status == 'DONE',
         'note': 'El más caro: el modelo profundo del panel vuelve a mirar cada afirmación.'},
    ]


@login_required
def relaunch(request, pk, stage):
    """Etapa a relanzar: cheap | dating | verdicts | deep."""
    from django.http import Http404
    from apps.panel.models import AuditLog
    post = get_object_or_404(Post, pk=pk)
    if stage not in RELAUNCH_STAGES:
        raise Http404
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    opcion = next(o for o in relaunch_options(post) if o['stage'] == stage)
    if not opcion['available']:
        messages.error(request, 'Esa etapa no se puede relanzar en el estado actual del post.')
        return redirect('post_detail', pk=pk)
    voces = request.POST.get('speakers', '').strip()
    if request.POST.get('confirm') != '1':
        from .services import waiting_for_identification, budget_left_today
        _espera, ident, total, minimo = waiting_for_identification(post)
        return render(request, 'analysis/relaunch_confirm.html', {
            'post': post, 'opcion': opcion, 'stage': stage,
            'budget_left': round(budget_left_today(), 2),
            'ident': ident, 'ident_total': total, 'ident_min': minimo,
            'gate_open': ident * 100 >= total * minimo if total else True,
            'speakers_now': post.speakers_count, 'speakers_source': post.speakers_count_source,
        })
    detalle = f'post {post.pk} etapa {stage} ({opcion["cost"]:.2f} EUR estimados)'
    if stage == 'cheap':
        from .tasks import run_cheap_phase, reset_for_cheap_phase
        # Red de seguridad de David: moderacion puede corregir el numero de voces.
        if voces.isdigit() and 1 <= int(voces) <= 20:
            post.speakers_count, post.speakers_confidence = int(voces), 'high'
            post.speakers_count_source = 'mod'
            post.save(update_fields=['speakers_count', 'speakers_confidence',
                                     'speakers_count_source'])
            detalle += f', voces fijadas por moderación: {voces}'
        reset_for_cheap_phase(post)
        run_cheap_phase.delay(post.pk)
        messages.success(request, 'Relanzado: transcripción y voces se regenerarán en unos minutos.')
    elif stage == 'dating':
        from .tasks import redate_post
        redate_post.delay(post.pk)
        messages.success(request, 'Relanzada la datación del suceso.')
    elif stage == 'verdicts':
        from .tasks import reverify_post
        reverify_post.delay(post.pk)
        messages.success(request, 'Relanzados los veredictos: los hablantes se conservan.')
    else:
        from .tasks import opus_rescan
        opus_rescan.delay(post.pk, forced=True)
        messages.success(request, 'Relanzado el análisis profundo con el modelo del panel.')
    AuditLog.objects.create(user=request.user, action=f'relaunch_{stage}', detail=detalle)
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
def speaker_search(request):
    """Autocompletado de personas (2026-08-17): busca en Wikidata y devuelve
    candidatos con QID, descripcion y foto. Requiere login (no es un proxy
    abierto a Wikidata) y degrada a lista vacia si Wikidata no responde."""
    from django.http import JsonResponse
    from apps.agents.wikidata import search_people
    q = request.GET.get('q', '')
    lang = 'en' if getattr(request, 'LANGUAGE_CODE', 'es') == 'en' else 'es'
    return JsonResponse({'results': search_people(q, lang=lang)})


@login_required
def propose_speaker_name(request, pk):
    """4.2.1 I7 + autocompletado (2026-08-17): el usuario propone quien es el
    hablante. Si eligio una sugerencia, la propuesta viaja con su QID de Wikidata
    (identidad univoca) + foto y descripcion; si escribio a mano, se acepta igual
    como texto libre. Entra en el voto participativo de siempre."""
    from apps.wiki.models import SpeakerNameProposal
    post = get_object_or_404(Post, pk=pk)
    if request.method == 'POST':
        label = request.POST.get('label', '').strip()[:20]
        name = ' '.join(request.POST.get('name', '').split())[:160]
        qid = request.POST.get('qid', '').strip()[:16]
        desc = ' '.join(request.POST.get('qdesc', '').split())[:120]
        if not re.fullmatch(r'Q\d{1,14}', qid or 'Q1'):
            qid, desc = '', ''   # QID manipulado: se ignora, no se rompe nada
        valid_labels = set(post.transcript_segments.exclude(speaker_label='')
                           .values_list('speaker_label', flat=True))
        if label in valid_labels and len(name) >= 3:
            from apps.agents.wikidata import entity_photo, photo_for
            photo = entity_photo(qid) if qid else (photo_for(name) or '')
            SpeakerNameProposal.objects.get_or_create(
                post=post, speaker_label=label, candidate_name=name,
                defaults={'source': 'user', 'photo_url': photo,
                          'wikidata_id': qid, 'description': desc})
            messages.success(request, 'Candidato propuesto. Ahora, ¡a votar!')
        else:
            messages.error(request, 'Propuesta no válida.')
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
    # 4.4-D (orden de David, 2026-08-23): "El voto del admin siempre relanzará el
    # analisis". Sin esto el reanalisis profundo era INALCANZABLE: hacen falta 5
    # personas distintas y la web esta cerrada a registros. La rueda de "Reanalisis
    # profundo" del panel de modelos estaba configurada y no la podia usar nadie.
    # Es la misma solucion que ya rige en la validacion de videos y en la
    # confirmacion de nombres: el voto de moderador confirma en solitario.
    es_admin = request.user.is_superuser or request.user.effective_level() == 'MOD'
    if value == -1 and es_admin:
        from .tasks import opus_rescan_segment
        opus_rescan_segment.delay(seg.pk, forced=True)
        from apps.panel.models import AuditLog
        AuditLog.objects.create(user=request.user, action='force_deep_scan',
                                detail=f'segmento {seg.pk} del post {seg.post_id}')
        messages.info(request, 'Reanálisis profundo lanzado con tu voto de moderación.')
    # 4.3-A.7 (David): "si llega a 5 usuarios" son 5, no 6. Era > (estricto).
    elif (value == -1 and not seg.opus_rescanned
            and downs >= SystemSetting.get_int('segment_opus_downvotes', 5)):
        from .tasks import opus_rescan_segment
        opus_rescan_segment.delay(seg.pk)
        messages.info(request, 'Oración muy discutida: se re-analizará con el modelo premium.')
    return redirect(f"/post/{seg.post_id}/#seg-{seg.pk}")


@login_required
def message_edit(request, mpost_id):
    """4.3-A J4: editar TU mensaje durante 15 minutos (estandar de foro).
    La edicion de moderacion llegara con su registro en el 4.4."""
    from django.utils import timezone
    from machina.core.db.models import get_model
    MPost = get_model('forum_conversation', 'Post')
    m = get_object_or_404(MPost, pk=mpost_id)
    if m.poster_id != request.user.pk:
        return redirect('/')
    if (timezone.now() - m.created).total_seconds() > 900:
        messages.error(request, 'La ventana de edición (15 minutos) ha pasado.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()[:8000]
        if content:
            m.content = content
            m.save()
            messages.success(request, 'Mensaje editado.')
        try:
            pk = int(m.topic.slug.split('-')[1])
            return redirect(f'/post/{pk}/#hilo')
        except (IndexError, ValueError):
            return redirect('/')
    return render(request, 'analysis/message_edit.html', {'m': m})


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
def md_preview(request):
    """4.3-G: vista previa de un mensaje del foro.

    La pinta el SERVIDOR con el MISMO renderizador que usa machina para guardar
    (config.MACHINA_MARKUP_LANGUAGE). Una sola fuente de verdad: si el servidor
    no sabe pintar una marca, tampoco aparece en la vista previa — que es justo
    lo que evita prometer al usuario un formato que luego saldra en crudo.
    Mejora progresiva: sin JS no hay boton y el foro funciona igual."""
    if request.method != 'POST':
        return redirect('index')
    from django.conf import settings
    from django.http import HttpResponse
    from django.utils.module_loading import import_string
    ruta, kwargs = settings.MACHINA_MARKUP_LANGUAGE
    render_md = import_string(ruta)
    texto = request.POST.get('content', '')[:8000]
    return HttpResponse(render_md(texto, **kwargs))


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
            # 4.3-A.8: el buscador era la puerta de atras de la sala +18.
            visibles = Post.objects.all()
            if not _can_see_adult(request):
                visibles = visibles.exclude(is_adult=True)
            results['posts'] = visibles.annotate(
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
def resolve_attribution(request, segment_id):
    """4.4-I: un usuario con sesion resuelve una frase de atribucion incierta:
    le pone la voz que corresponde. Sin JS (form POST). Queda en la nota de la
    frase quien la resolvio, y se vuelve a probar el piloto automatico porque
    la puerta del 65 % puede haberse abierto."""
    from .models import TranscriptSegment
    from .services import try_autopilot
    seg = get_object_or_404(TranscriptSegment, pk=segment_id)
    voz = request.POST.get('speaker', '')
    etiquetas = set(seg.post.transcript_segments.exclude(speaker_label='')
                    .values_list('speaker_label', flat=True))
    if request.method != 'POST' or voz not in etiquetas:
        return redirect('post_detail', pk=seg.post_id)
    seg.speaker_label = voz
    seg.attribution_uncertain = False
    seg.attribution_note = f'resuelta por {request.user.username}'
    seg.save(update_fields=['speaker_label', 'attribution_uncertain', 'attribution_note'])
    try_autopilot(seg.post)
    messages.success(request, 'Frase atribuida. Gracias.')
    return redirect('post_detail', pk=seg.post_id)


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
        from apps.accounts.services import notify as _notify
        if post.author_id != request.user.pk:
            _notify(post.author, f'{request.user.username} ha votado tu post: '
                                 f'{(post.title or post.url)[:80]}',
                    f'/post/{post.pk}/', kind='post_votes')
        # 4.2 D4: al CRUZAR el umbral (no en cada voto) avisa una sola vez.
        if not post.trending_notified and post.is_trending():
            post.trending_notified = True
            post.save(update_fields=['trending_notified'])
            from .tasks import notify_post_event
            notify_post_event(post, 'trending', '🔥 El post está en Trending')
        from .tasks import maybe_trigger_opus_rescan
        if maybe_trigger_opus_rescan(post, request.user):  # unica puerta (Fase 3.4 §6)
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


@csrf_exempt
def aai_webhook(request):
    """4.10-A: el TIMBRE de AssemblyAI. Valida el secreto de cabecera, responde
    rapido (su plazo es 10 s) y delega TODO al worker. Idempotente: un post ya
    resuelto o un id desconocido devuelven 200 y no hacen nada."""
    import json as _json
    from django.conf import settings as djs
    from django.http import HttpResponse, HttpResponseForbidden
    if request.method != 'POST':
        return HttpResponse(status=405)
    if request.headers.get('X-Istt-Hook') != djs.AAI_WEBHOOK_SECRET:
        return HttpResponseForbidden('no')
    try:
        cuerpo = _json.loads(request.body.decode() or '{}')
    except Exception:
        return HttpResponse('mal cuerpo', status=200)   # no reintenteis esto
    tid = cuerpo.get('transcript_id') or ''
    from .models import Post
    post = Post.objects.filter(aai_job_id=tid).first() if tid else None
    if post is None:
        return HttpResponse('desconocido', status=200)
    from .tasks import resume_after_aai, run_cheap_phase
    if cuerpo.get('status') == 'completed':
        resume_after_aai.delay(post.pk, tid)
    else:
        post.aai_job_id = ''
        post.save(update_fields=['aai_job_id'])
        run_cheap_phase.delay(post.pk, skip_charge=True, skip_aai=True)
    return HttpResponse('ok')
