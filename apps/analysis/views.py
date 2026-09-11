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
    # 5.1-A.1 (reporte de David): en el subdominio de la wiki, la RAIZ es la
    # portada de la wiki — como en Wikipedia. El resto de rutas no cambian.
    host = request.get_host().split(':')[0]
    if host.startswith('wiki.') or host.startswith('wikitrue.'):
        from apps.wiki.views import wiki_home
        return wiki_home(request)
    # 5.1-B.1 (orden de David): la portada, SOLO con lo que pidio — novedades en
    # sus posts seguidos desde su ultima visita, los mas nuevos, los mas
    # comentados y los mas votados. Reincidentes, temas y Off-Topic salen de
    # aqui (el Off-Topic vive ahora en la pagina del foro).
    from django.db.models import Count, Q
    from django.utils import timezone as tz
    # 4.3-A.8 (decision de David): el contenido +18 NO vive en los listados
    # publicos; tiene su sala cerrada (/mas18/).
    base = Post.objects.publicos().filter(category='MAIN').exclude(is_adult=True)
    nuevos = base.fijados_primero()[:15]   # 5.23-D: los fijados, arriba
    window = tz.now() - tz.timedelta(days=7)
    # 5.30-A (orden de David): «mas votados» = ▲ menos ▼ de los ultimos 7 dias
    # (antes, 5.23-C, solo positivos).
    from django.db.models import F
    top = base.annotate(ups=Count('votes', filter=Q(votes__created_at__gte=window, votes__value=1)),
                        downs=Count('votes', filter=Q(votes__created_at__gte=window, votes__value=-1))) \
              .annotate(n=F('ups') - F('downs')).filter(n__gt=0).order_by('-n')[:10]
    comentados = _mas_comentados(base)
    seguidos = _novedades_en_seguidos(request.user) \
        if request.user.is_authenticated else []
    return render(request, 'analysis/index.html', {
        'nuevos': nuevos, 'top': top, 'comentados': comentados,
        'seguidos': seguidos, 'adult_room': _can_see_adult(request)})


def _mas_comentados(base):
    """Los posts con mas mensajes en su hilo. El hilo vive en machina como el
    topic 'post-<pk>'; posts_count ya lo mantiene machina al dia."""
    from machina.core.db.models import get_model
    Topic = get_model('forum_conversation', 'Topic')
    filas = []
    for t in Topic.objects.filter(slug__startswith='post-') \
                          .order_by('-posts_count')[:30]:
        try:
            pk = int(t.slug.split('-', 1)[1])
        except (ValueError, IndexError):
            continue
        post = base.filter(pk=pk).first()
        if post and t.posts_count > 1:   # el primer mensaje es el «Opina» del autor
            filas.append({'post': post, 'n': t.posts_count - 1})
        if len(filas) >= 10:
            break
    return filas


def _novedades_en_seguidos(user):
    """Que paso en los posts que sigue este usuario desde su ultima visita:
    mensajes nuevos en el hilo y analisis que terminaron. La 'ultima visita' es
    su login ANTERIOR (previous_login, que VerifiedLoginView guarda antes de
    que Django pise last_login) — la mejor marca sin espiar la navegacion."""
    from machina.core.db.models import get_model
    from .models import PostSubscription
    MPost = get_model('forum_conversation', 'Post')
    desde = user.previous_login or user.last_login or user.date_joined
    filas = []
    subs = PostSubscription.objects.filter(user=user).select_related('post')[:100]
    for sub in subs:
        post = sub.post
        if post.is_adult or post.censored or post.status == 'PENDING_APPROVAL':
            continue
        mensajes = MPost.objects.filter(topic__slug=f'post-{post.pk}',
                                        approved=True, created__gt=desde) \
                                .exclude(poster=user).count()
        analizado = bool(
            (post.cheap_finished_at and post.cheap_finished_at > desde) or
            (post.full_finished_at and post.full_finished_at > desde))
        if mensajes or analizado:
            filas.append({'post': post, 'mensajes': mensajes,
                          'analizado': analizado})
    filas.sort(key=lambda f: -f['mensajes'])
    return filas[:10]


def _alternativas_web(url, platform):
    """5.19: busca el MISMO podcast/video fuera de la plataforma con DRM.
    Devuelve [{url, titulo, plataforma}] SOLO de plataformas analizables."""
    import json as _json
    from apps.agents import client
    from apps.agents.catalog import fallback_for, model_for
    from apps.embeds.adapters import (NON_ANALYZABLE, detect_platform,
                                      fetch_title)
    titulo = fetch_title(url, platform) or url
    sistema = ('Buscas contenidos multimedia. Responde SOLO JSON: '
               '{"resultados": [{"url": "...", "titulo": "...", '
               '"plataforma": "youtube|twitch|tiktok"}]} — hasta 5, los mas '
               'fieles primero. Solo URLs REALES halladas en la busqueda.')
    payload = (f'Busca este podcast/episodio FUERA de Spotify (preferencia: '
               f'YouTube con video completo): «{titulo}». Si existe en varias '
               f'plataformas, listalas todas.')
    try:
        datos, _usado = client.call_search_json(
            model_for('sweep'), sistema, payload, max_tokens=700,
            max_searches=2, fallback=fallback_for('sweep'),
            mock_payload={'resultados': [
                {'url': 'https://youtu.be/simulado', 'titulo': f'[SIMULADO] {titulo}',
                 'plataforma': 'youtube'}]})
    except Exception:
        return []
    limpias = []
    for r in (datos.get('resultados') or [])[:5]:
        u = str(r.get('url') or '')
        p, _vid = detect_platform(u)
        if p and p not in NON_ANALYZABLE:
            limpias.append({'url': u, 'titulo': str(r.get('titulo') or u)[:120],
                            'plataforma': p})
    return limpias


VIDEO_RX = re.compile(r'(youtube\.com|youtu\.be|tiktok\.com|twitch\.tv|spotify\.com)', re.I)


def _categoria_contrastada(propuesta, url):
    """5.1-D: el bibliotecario (Sonnet, rueda «Orden de categorías» del panel)
    contrasta la propuesta con la taxonomia viva y su uso real: la encaja en
    una existente o crea una nueva normalizada. Devuelve (slug, aviso) o None."""
    import json
    from django.utils.text import slugify
    from apps.agents import client, prompts
    from apps.agents.catalog import fallback_for, model_for
    from .models import Category
    existentes = [{'slug': s, 'nombre': n, 'usos': u}
                  for s, n, u in Category.objects.values_list(
                      'slug', 'name', 'times_used')]
    payload = json.dumps({'propuesta': propuesta, 'video_url': url,
                          'categorias_existentes': existentes},
                         ensure_ascii=False)
    datos = client.call_json(
        model_for('categories'), prompts.CATEGORY_SYSTEM, payload,
        max_tokens=150, fallback=fallback_for('categories'),
        mock_payload={'accion': 'crear', 'nombre': propuesta[:40].title(),
                      'slug': slugify(propuesta)[:40]})
    if datos.get('accion') == 'usar':
        cat = Category.objects.filter(slug=datos.get('slug', '')).first()
        if cat:
            return cat.slug, (f'Tu propuesta «{propuesta}» encaja en la '
                              f'categoría existente «{cat.name}».')
    if datos.get('accion') == 'crear':
        slug = slugify(datos.get('slug') or datos.get('nombre') or propuesta)[:40]
        nombre = (datos.get('nombre') or propuesta).strip()[:40]
        if slug and nombre:
            cat, creada = Category.objects.get_or_create(
                slug=slug, defaults={'name': nombre, 'created_by_agent': True})
            return cat.slug, (f'Categoría nueva creada: «{cat.name}».' if creada
                              else f'Tu propuesta encaja en «{cat.name}».')
    return None


@login_required
def submit(request):
    # Puerta abierta (Fase 3.9 §4): SOLO login + email verificado. Los niveles
    # limitan la CUOTA diaria y los votos, nunca la capacidad de analizar.
    from .models import Category
    if not request.user.email_verified:
        messages.error(request, 'Verifica tu email para poder analizar (revisa tu buzón o pide un reenvío).')
        return redirect('index')
    arbol = Category.tree()
    if request.method != 'POST':
        return render(request, 'analysis/submit.html', {'arbol': arbol})
    url = request.POST.get('url', '').strip()
    # 5.23-E (ENMIENDA de David al README): la categoria es OBLIGATORIA y sale
    # del arbol de subforos. Si ninguna encaja, el usuario PROPONE una: el post
    # nace pendiente de aprobacion (sin analisis, invisible) hasta que
    # moderacion lo apruebe — y puede encajarlo o crear la categoria nueva.
    topic = request.POST.get('topic', '').strip()
    propuesta = ' '.join(request.POST.get('topic_new', '').split())[:40]
    if not Category.objects.filter(slug=topic).exclude(slug=Category.ROOT_SLUG).exists():
        topic = ''
    if not topic and not propuesta:
        messages.error(request, 'Elige una categoría del listado o propón una nueva.')
        return render(request, 'analysis/submit.html',
                      {'arbol': arbol, 'url_previa': url,
                       'tags_previas': request.POST.get('tags', '')[:200],
                       'opinion_previa': request.POST.get('opinion', '')[:8000]})
    tags = request.POST.get('tags', '').strip()[:200]
    voluntary_offtopic = request.POST.get('offtopic') == 'on'
    author_opinion = request.POST.get('opinion', '').strip()[:8000]  # 4.2 A5
    author_adult_flag = request.POST.get('is_adult') == 'on'
    platform, external_id = detect_platform(url)
    # 5.24-B: el MP3 de un podcast (elegido en la pantalla de alternativas) entra
    # como plataforma 'audio'.
    if not VIDEO_RX.search(url) and platform != 'audio':
        messages.error(request, 'El enlace debe ser de una plataforma soportada: YouTube, TikTok, Twitch o Spotify.')
        return render(request, 'analysis/submit.html', {'arbol': arbol})
    if not platform:
        messages.error(request, 'Plataforma no soportada todavía. Se mostrará como tarjeta-enlace.')
        platform = 'link'
    # 5.19 (orden de David): las fuentes NO ANALIZABLES (Spotify: DRM) ya no se
    # aceptan como post. En su lugar, al pulsar «Analizar» se busca EL MISMO
    # podcast por toda la web y el usuario elige la version analizable, que es
    # la que se convierte en post.
    from apps.embeds.adapters import NON_ANALYZABLE
    if platform in NON_ANALYZABLE:
        alternativas = _alternativas_web(url, platform)
        # 5.24-B (orden de David): ademas, el AUDIO ORIGINAL del podcast por RSS.
        try:
            from apps.embeds.rss import alternativas_rss
            alternativas = alternativas_rss(url) + alternativas
        except Exception:
            pass
        if alternativas:
            messages.info(request, 'Spotify protege su audio (DRM) y no se '
                          'puede analizar. He buscado este mismo contenido '
                          'por la web: elige una versión analizable.')
        else:
            messages.error(request, 'Spotify protege su audio (DRM) y no se '
                           'puede analizar, y no he encontrado este contenido '
                           'en otra plataforma. Si conoces su versión de '
                           'YouTube o su RSS, pega ese enlace.')
        return render(request, 'analysis/submit_alternativas.html',
                      {'alternativas': alternativas, 'original': url,
                       'topic': topic, 'topic_new': propuesta, 'tags': tags,
                       'opinion': author_opinion,
                       'offtopic': voluntary_offtopic,
                       'is_adult': author_adult_flag,
                       'arbol': arbol})

    # 4.3-A.8 (decision de David): ANTES de postear se comprueba el video —
    # titulo (para colocarlo bien), duracion (para el aviso de donacion) y si es
    # +18 (para que nazca ya en la sala cerrada, no despues). Si el pre-chequeo
    # falla, seguimos con lo que haya: nunca se cierra la puerta por eso.
    from apps.embeds.adapters import probe
    ficha = probe(url, platform)
    edad_plataforma = ficha['age_limit'] >= 18
    if platform == 'audio':
        # 5.24-B: titulo y duracion viajan desde la pantalla de alternativas (un
        # MP3 no tiene oEmbed y yt-dlp no siempre lee la duracion de un fichero).
        if not ficha.get('title'):
            ficha['title'] = ' '.join(request.POST.get('titulo', '').split())[:300]
        if not ficha.get('duration_seconds'):
            try:
                ficha['duration_seconds'] = max(0, int(request.POST.get('duracion') or 0))
            except ValueError:
                pass

    pendiente = bool(propuesta)
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
                                                     else 'platform' if edad_plataforma else ''),
                               'status': 'PENDING_APPROVAL' if pendiente else 'NEW',
                               'pending_category': propuesta if pendiente else ''})
        if created and topic and not pendiente:
            # 5.1-D: el contador de uso alimenta el orden del buscador
            Category.objects.filter(slug=topic).update(
                times_used=models.F('times_used') + 1)
        if created and not post.title:
            from apps.embeds.adapters import fetch_title
            title = fetch_title(url, platform)  # I2: titulo inmediato (oEmbed, 4 s max)
            if title:
                post.title = title
                post.save(update_fields=['title'])
        AnalysisRequest.objects.create(post=post, user=request.user,
                                       served_from_cache=not created)
        if not created:
            if post.status == 'PENDING_APPROVAL':
                messages.info(request, 'Ese vídeo ya está propuesto y espera la '
                                       'aprobación de moderación.')
                return redirect('index')
            # Cache: gratis, instantaneo, pero cuenta como solicitante (umbral 5/10/5)
            return redirect('post_detail', pk=post.pk)

    if pendiente:
        # 5.23-E: ni analisis, ni post visible, ni categoria — aviso a TODO el staff.
        _avisar_staff_pendiente(post)
        messages.info(request, f'Has propuesto la categoría «{propuesta}». Un moderador '
                               f'la revisará y, al aprobarla, tu vídeo se publicará y '
                               f'analizará. Te avisaremos por la campana.')
        return redirect('index')
    return _arrancar_post(request, post, voluntary_offtopic, comprobar_cupo=True)


def _avisar_staff_pendiente(post):
    """5.23-E: campana (y email segun preferencia) a moderadores y superusuario."""
    from django.db.models import Q
    from apps.accounts.models import User
    from apps.accounts.services import notify
    destino = f'/pendiente/{post.slug or post.pk}/'
    titulo = (post.title or post.url)[:70]
    for u in User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(level='MOD')):
        notify(u, f'Post pendiente de aprobación (categoría propuesta «{post.pending_category}»): {titulo}',
               destino, kind='moderation')


def _arrancar_post(request, post, voluntary_offtopic, comprobar_cupo=True):
    """La cola de salida de un post recien creado (o recien aprobado, 5.23-E):
    Off-Topic voluntario, cupo del autor, avisos de presupuesto y duracion,
    cola por presupuesto o arranque de la fase barata."""
    from .models import Post as _Post
    if voluntary_offtopic:
        post.category = 'OFFTOPIC'
        post.status = 'OFFTOPIC_RAW'  # coste CERO hasta reunir 10 votos
        post.save()
        return redirect('post_detail', pk=post.pk)

    if comprobar_cupo and not post.author.can_spend_credit():
        post.delete()
        messages.error(request, 'Has agotado tu cupo diario de análisis.')
        return redirect('index')
    # 4.3-F: el aviso de "presupuesto agotado" comparaba con settings.DAILY_BUDGET_EUR,
    # una cifra CABLEADA (3,00 €) que ya no era la de nadie. El presupuesto vivo
    # se calcula desde el panel; dos fuentes de verdad para el mismo número es
    # justo el fallo que el operador cazó en 98d3442.
    from .services import budget_left_today
    if budget_left_today() <= 0:
        waiting = _Post.objects.filter(status='NEW').count() + 1
        messages.info(request, f'Presupuesto diario agotado (proyecto sin ánimo de '
                      f'lucro). Tu análisis es el nº {waiting} de mañana. '
                      f'Si donas, el depósito crece.')
    AnalysisCredit.objects.create(user=post.author, post=post)  # sin devolucion

    # 4.3-A.8: los dos avisos del pre-chequeo. Son AVISOS, no muros: la puerta de
    # submit sigue siendo login + email verificado (decision congelada).
    if post.is_adult and post.adult_flag_source == 'platform':
        messages.warning(request, 'La plataforma marca este vídeo como +18: el análisis '
                         'irá a la sala para mayores de edad y no aparecerá en portada.')
    from .services import free_minutes, suggested_donation_eur, video_minutes
    donacion = suggested_donation_eur(post)
    # 5.13-C (reporte de David): con la duracion DESCONOCIDA se reservaba el
    # maximo y el mensaje MENTIA («dura 90 minutos»). La reserva prudente se
    # queda; el mensaje dice la verdad.
    dur_conocida = bool(post.duration_seconds)
    if donacion and dur_conocida:
        messages.info(request, f'Este vídeo dura {video_minutes(post)} minutos y se '
                      f'analizará entero. Por encima de {free_minutes()} minutos el coste '
                      f'lo sostienen las donaciones: si puedes, una de {donacion:.2f} € '
                      f'cubre este análisis. No es obligatoria y tu vídeo ya está en cola.')
    elif donacion:
        messages.info(request, f'No he podido leer la duración de este contenido: se '
                      f'reserva el máximo ({video_minutes(post)} minutos) y lo no usado '
                      f'se libera al transcribir. Si puedes, una donación de hasta '
                      f'{donacion:.2f} € ayuda a costearlo. No es obligatoria.')

    # 4.3-F (decisión de David): si el vídeo se lleva más de media asignación
    # diaria, NO se analiza al momento. Entra en cola y se lanza cuando haya
    # depósito, o antes si alguien lo apadrina. Nunca se rechaza, y el aviso
    # explica exactamente por qué y cuánto.
    from .services import needs_sponsorship
    a_la_cola, coste, sugerida = needs_sponsorship(post)
    if a_la_cola:
        post.status = 'AWAITING_BUDGET'
        post.save(update_fields=['status'])
        aprox = 'unos' if dur_conocida else 'como máximo'
        messages.info(request, f'Este vídeo se lleva más de media asignación diaria '
                      f'(cuesta {aprox} {coste:.2f} €), así que entra en cola: se '
                      f'analizará solo en cuanto haya depósito, normalmente mañana. '
                      f'Si quieres que salga antes, puedes apadrinarlo aquí abajo: '
                      f'esa donación queda atada a ESTE análisis.')
        return redirect('post_detail', pk=post.pk)

    run_cheap_phase.delay(post.pk)
    return redirect('post_detail', pk=post.pk)


# ---------------- 5.23-E: posts pendientes de aprobacion (orden de David) ----------------

@login_required
def pending_list(request):
    """Solo staff: los posts con categoria propuesta que esperan revision."""
    if not _require_mod(request.user):
        return redirect('index')
    posts = Post.objects.filter(status='PENDING_APPROVAL').order_by('created_at')
    return render(request, 'analysis/pendientes.html', {'posts': posts})


@login_required
def pending_review(request, slug):
    """Solo staff, en /pendiente/<titulo>/: revisar lo que rellenó el autor
    (título, categoría propuesta, etiquetas, opinión), encajarlo en una
    categoría existente o CREAR la nueva (con su padre en el árbol), y aprobar
    — momento en el que el post se publica y arranca su análisis — o rechazar."""
    from django.http import Http404
    from django.utils import timezone as _tz
    from django.utils.text import slugify
    from apps.panel.models import AuditLog
    from apps.accounts.services import notify
    from .models import Category
    if not _require_mod(request.user):
        return redirect('index')
    post = Post.objects.filter(slug=slug).first()
    if not post and str(slug).isdigit():
        post = Post.objects.filter(pk=int(slug)).first()
    if not post:
        raise Http404
    if post.status != 'PENDING_APPROVAL':
        return redirect(post.get_absolute_url())
    arbol = Category.tree()
    if request.method == 'POST':
        accion = request.POST.get('accion')
        titulo = (post.title or post.url)[:80]
        if accion == 'rechazar':
            motivo = request.POST.get('motivo', '').strip()[:200]
            AuditLog.objects.create(user=request.user, action='pending_rejected',
                                    detail=f'post {post.pk} «{titulo}»: {motivo}')
            notify(post.author, f'Tu vídeo «{titulo}» no se ha publicado'
                                + (f': {motivo}' if motivo else '.'), '/', kind='post_phase')
            post.delete()
            messages.success(request, 'Propuesta rechazada y avisado el autor.')
            return redirect('pending_list')
        if accion != 'aprobar':
            return redirect('pending_review', slug=slug)
        # datos que el moderador puede haber corregido
        nuevo_titulo = ' '.join(request.POST.get('title', '').split())[:300]
        if len(nuevo_titulo) >= 3:
            post.title = nuevo_titulo
        post.tags = request.POST.get('tags', '').strip()[:200]
        if request.POST.get('crear') == 'on':
            nombre = ' '.join(request.POST.get('nombre', '').split())[:40] or post.pending_category
            padre = Category.objects.filter(slug=request.POST.get('parent', '')).first() \
                or Category.root()
            base = slugify(nombre)[:36] or 'categoria'
            cand, n = base, 1
            while Category.objects.filter(slug=cand).exists():
                n += 1
                cand = f'{base}-{n}'
            cat = Category.objects.create(name=nombre, slug=cand, parent=padre)
            detalle_cat = f'categoría NUEVA «{cat.path_label()}»'
        else:
            cat = Category.objects.filter(slug=request.POST.get('topic', '')) \
                .exclude(slug=Category.ROOT_SLUG).first()
            if not cat:
                messages.error(request, 'Elige una categoría existente o marca «crear la nueva».')
                return redirect('pending_review', slug=slug)
            detalle_cat = f'encajado en «{cat.path_label()}»'
        post.topic = cat.slug
        post.pending_category = ''
        post.status = 'NEW'
        post.approved_by = request.user
        post.approved_at = _tz.now()
        post.save()
        Category.objects.filter(pk=cat.pk).update(times_used=models.F('times_used') + 1)
        AuditLog.objects.create(user=request.user, action='pending_approved',
                                detail=f'post {post.pk} «{titulo}»: {detalle_cat}')
        notify(post.author, f'Tu vídeo «{titulo}» ha sido aprobado en «{cat.name}» y ya se analiza',
               post.get_absolute_url(), kind='post_phase')
        messages.success(request, f'Aprobado ({detalle_cat}): el análisis arranca ahora.')
        return _arrancar_post(request, post, post.voluntary_offtopic, comprobar_cupo=False)
    from apps.embeds.adapters import build_embed
    try:
        embed = build_embed(post)
    except Exception:
        embed = ''
    return render(request, 'analysis/pendiente.html',
                  {'post': post, 'arbol': arbol, 'embed': embed,
                   'pendientes': Post.objects.filter(status='PENDING_APPROVAL').count()})


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
    posts = Post.objects.publicos().filter(is_adult=True).fijados_primero()[:50]
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
                           waiting_for_identification, min_identified_percent, votes_needed)
    topic_obj = get_topic_for_post(post)
    is_mod = bool(u and (u.is_staff or u.level == 'MOD'))
    # 4.4-G: aviso visible cuando la identificacion frena la verificacion, y las
    # cuatro etapas de la llave inglesa (solo se pintan para moderacion).
    waiting_ident = waiting_for_identification(post)[0]
    relaunch_rows = relaunch_options(post) if is_mod else []
    # 4.3-F: cifras del cartel de la cola (solo se pintan si el post está en ella).
    _en_cola, queue_cost, queue_sponsor = needs_sponsorship(post)
    thread_messages, page_obj, first_unread_pk, newest_pk = _thread_page(
        topic_obj, u, request, incluir_borrados=is_mod)
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
    # 5.23-C: karma con flechas — recuentos del post y de cada mensaje
    from apps.forum.karma import decorar_mensajes, recuento
    from apps.forum.models import Vote
    decorar_mensajes(thread_messages, u)
    p_ups, p_downs, p_mio = recuento(Vote, {'post': post}, u)
    votos_post = {'ups': p_ups, 'downs': p_downs, 'mine': p_mio,
                  'own': bool(u and post.author_id == u.pk)}
    # 5.23-D: el menu de tres puntos necesita el arbol para «Mover de categoria»
    from .models import Category
    categorias = Category.elegibles() if is_mod else []
    return {
        'votos_post': votos_post, 'categorias': categorias,
        'costes_filas': costes_filas, 'costes_total': costes_total,
        'post': post, 'segments': segments, 'embed': build_embed(post),
        'hide_opinions': hide_opinions,
        'votes_validate': post.distinct_validation_votes('VALIDATE'),
        'votes_needed': votes_needed(post),          # 5.27-A
        'suggested_cat': (Category.objects.filter(slug=post.suggested_topic).first()
                          if post.suggested_topic else None),   # 5.27-D
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
        # 5.7-A: la huella del analisis que vigila el navegador (vigia_post.js)
        'estado_analisis': _huella_analisis(post)[0],
        # 5.22 (orden de David): el semaforo del post bajo el titulo, clicable.
        'semaforo_post': _semaforo_del_post(post),
    }


def _semaforo_del_post(post):
    """5.22: los claims del post en CUATRO cubos — verde, ambar, rojo y sin
    respuesta — con su marca temporal, para la barra clicable bajo el titulo."""
    if post.status != 'DONE':
        return None
    from apps.wiki.models import ClaimAppearance
    cubos = {'GREEN': [], 'AMBER': [], 'RED': [], 'SIN': []}
    vistos = set()
    for ap in (ClaimAppearance.objects.filter(segment__post=post)
               .select_related('claim', 'segment')
               .order_by('segment__start_seconds')):
        if ap.claim_id in vistos:
            continue
        vistos.add(ap.claim_id)
        cubo = ap.claim.color if ap.claim.color in ('GREEN', 'AMBER', 'RED') else 'SIN'
        cubos[cubo].append({
            's': int(ap.segment.start_seconds or 0),
            'texto': (ap.claim.title or ap.claim.text_original)[:110],
            'slug': ap.claim.slug or ap.claim.pk})
    if not vistos:
        return None
    return {'verde': cubos['GREEN'], 'ambar': cubos['AMBER'],
            'rojo': cubos['RED'], 'sin': cubos['SIN'], 'total': len(vistos)}


def _huella_analisis(post):
    """5.7-A (orden de David): «por cada cambio en un post la pagina se
    recargara automaticamente mostrando un mensaje sobre el cambio».
    La huella condensa el estado del analisis; si cambia, cambio hubo.
    Devuelve (huella, descripcion del ultimo cambio)."""
    from apps.wiki.models import ClaimVersion
    ultima = (ClaimVersion.objects
              .filter(claim__appearances__segment__post=post)
              .order_by('-pk').select_related('claim').first())
    huella = f'{post.status}:{ultima.pk if ultima else 0}:' \
             f'{post.transcript_segments.count()}'
    if ultima:
        texto = (f'Verificación actualizada ({ultima.claim.get_color_display()}): '
                 f'«{(ultima.claim.title or ultima.claim.text_original)[:70]}»')
    else:
        texto = f'El análisis avanzó: {post.get_status_display()}'
    return huella, texto


def post_estado(request, pk):
    """5.7-A: el pulso que sondea el navegador — JSON minusculo, sin coste."""
    from django.http import JsonResponse
    post = get_object_or_404(Post, pk=pk)
    huella, texto = _huella_analisis(post)
    from apps.forum.machina_glue import get_topic_for_post
    topic_obj = get_topic_for_post(post)
    newest = 0
    if topic_obj:
        newest = (topic_obj.posts.filter(approved=True)
                  .order_by('-pk').values_list('pk', flat=True).first() or 0)
    return JsonResponse({'a': huella, 'txt': texto, 'm': newest})


def post_detail(request, pk=None, slug=None):
    # 5.0-D: canonica /post/<slug>/ (sin numero). La numerica /post/<pk>/ y la
    # forma historica /post/<slug>/<pk>/ hacen 301 conservando ?pagina= y demas.
    if pk is not None:
        post = get_object_or_404(Post, pk=pk)
    else:
        post = get_object_or_404(Post, slug=slug)
    if post.slug and (pk is not None or slug != post.slug):
        destino = post.get_absolute_url()
        if request.META.get('QUERY_STRING'):
            destino += '?' + request.META['QUERY_STRING']
        return HttpResponsePermanentRedirect(destino)
    if _adult_blocked(request, post):
        return render(request, 'analysis/adult_blocked.html', status=403)
    es_staff = _require_mod(request.user)
    # 5.23-D (precision de David): un post censurado queda INACCESIBLE para
    # todos los usuarios; solo el staff lo ve (marcado) para poder revertirlo.
    if post.censored and not es_staff:
        return render(request, 'analysis/censurado.html', {'post': post}, status=403)
    # 5.23-E: un post pendiente de aprobacion no existe para el publico.
    if post.status == 'PENDING_APPROVAL':
        if es_staff:
            return redirect('pending_review', slug=post.slug or post.pk)
        from django.http import Http404
        raise Http404
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


def _thread_page(topic_obj, u, request, per_page=20, incluir_borrados=False):
    """4.3-A J4: pagina del hilo (foro clasico: 20/pagina) + primer no leido.
    Registra el punto de lectura del usuario (TopicRead) al servir la pagina.
    5.23-D: el staff ve tambien los comentarios eliminados (no aprobados), como
    muñon restaurable."""
    from django.core.paginator import Paginator
    if not topic_obj:
        return [], None, None, 0
    qs = topic_obj.posts.select_related('poster').order_by('created')
    if not incluir_borrados:
        qs = qs.filter(approved=True)
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
        m.deleted = not m.approved
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
    thread_messages, page_obj, _first, newest_pk = _thread_page(
        topic_obj, u, request, incluir_borrados=is_mod)
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
    from apps.forum.karma import decorar_mensajes
    decorar_mensajes(thread_messages, u)   # 5.23-C
    # 5.7-B (orden de David): scroll infinito — las paginas siguientes se
    # APILAN bajo las anteriores (solo mensajes + centinela, sin barras).
    plantilla = ('partials/thread_messages_apilar.html'
                 if request.GET.get('apilar') else 'partials/thread_messages.html')
    resp = render(request, plantilla,
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
    # 5.18 (orden de David): el SUPERUSUARIO relanza cualquier fase
    # independientemente del coste — sin fusible diario. El gasto real se
    # apunta al libro igual, y el AuditLog deja constancia del salto.
    sin_fusible = bool(request.user.is_superuser)
    detalle = f'post {post.pk} etapa {stage} ({opcion["cost"]:.2f} EUR estimados)' \
              + (' SIN FUSIBLE (superusuario)' if sin_fusible else '')
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
        run_cheap_phase.delay(post.pk, skip_charge=sin_fusible)
        messages.success(request, 'Relanzado: transcripción y voces se regenerarán en unos minutos.')
    elif stage == 'dating':
        from .tasks import redate_post
        redate_post.delay(post.pk, skip_charge=sin_fusible)
        messages.success(request, 'Relanzada la datación del suceso.')
    elif stage == 'verdicts':
        from .tasks import reverify_post
        reverify_post.delay(post.pk, skip_charge=sin_fusible)
        messages.success(request, 'Relanzados los veredictos: los hablantes se conservan.')
    else:
        from .tasks import opus_rescan
        opus_rescan.delay(post.pk, forced=True, skip_charge=sin_fusible)
        messages.success(request, 'Relanzado el análisis profundo con el modelo del panel.')
    AuditLog.objects.create(user=request.user, action=f'relaunch_{stage}', detail=detalle)
    return redirect('post_detail', pk=pk)


# ---------------- 5.20: gestion del post (moderacion) ----------------

@login_required
def post_mod_note(request, pk):
    """5.20: nota interna de moderacion sobre el post."""
    from .models import PostModNote
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    texto = request.POST.get('text', '').strip()[:2000]
    if texto:
        PostModNote.objects.create(post=post, author=request.user, text=texto)
        messages.success(request, 'Nota de moderación guardada.')
    return redirect('post_detail', pk=pk)


@login_required
def post_censor(request, pk):
    """5.20: censurar/descensurar el post ENTERO — cortina con motivo; el
    lector puede elegir verlo igualmente (orden de David)."""
    from django.utils import timezone as _tz
    from apps.panel.models import AuditLog
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    if post.censored:
        post.censored = False
        post.censored_reason = ''
        post.censored_by = None
        post.censored_at = None
        accion, aviso = 'post_uncensor', 'Censura retirada.'
    else:
        post.censored = True
        post.censored_reason = request.POST.get('reason', '').strip()[:200]
        post.censored_by = request.user
        post.censored_at = _tz.now()
        # 5.23-D (precision de David): censurado = INACCESIBLE para todos los
        # usuarios, marcado, reversible y SIN analisis (las tareas lo saltan).
        accion, aviso = 'post_censor', ('Post censurado: inaccesible para los '
                                        'usuarios y sin análisis hasta que se retire.')
    post.save(update_fields=['censored', 'censored_reason',
                             'censored_by', 'censored_at'])
    AuditLog.objects.create(user=request.user, action=accion,
                            detail=f'post {post.pk}: {post.censored_reason[:80]}')
    messages.success(request, aviso)
    return redirect('post_detail', pk=pk)


@login_required
def post_delete(request, pk):
    """5.20: eliminar el post (con su hilo del foro). Accion irreversible:
    exige confirmacion y deja rastro en AuditLog."""
    from apps.panel.models import AuditLog
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect('post_detail', pk=pk)
    if request.POST.get('confirm') != post.pk.__str__():
        messages.error(request, 'Confirmación incorrecta: escribe el número '
                                'del post para eliminarlo.')
        return redirect('post_detail', pk=pk)
    from apps.forum.machina_glue import get_topic_for_post
    titulo = (post.title or post.url)[:120]
    topic = get_topic_for_post(post)
    AuditLog.objects.create(user=request.user, action='post_delete',
                            detail=f'post {post.pk} «{titulo}»')
    if topic:
        topic.delete()
    post.delete()
    messages.success(request, f'Post «{titulo}» eliminado.')
    return redirect('index')


# ---------------- 5.23-D: el menu de tres puntos (orden de David) ----------------

def _accion_staff(request, pk):
    """Comprobaciones comunes de las acciones del menu: POST + moderacion."""
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or not _require_mod(request.user):
        return post, redirect('post_detail', pk=pk)
    return post, None


def _volver(request, post):
    """Al post, o a la pagina desde la que se actuo (foro, portada)."""
    ref = request.META.get('HTTP_REFERER', '')
    if ref and '/pendiente/' not in ref and post.get_absolute_url() not in ref:
        return redirect(ref)
    return redirect(post.get_absolute_url())


@login_required
def post_toggle_comments(request, pk):
    """Cerrar/abrir los comentarios nuevos del hilo (clasico de foro)."""
    from apps.panel.models import AuditLog
    post, salida = _accion_staff(request, pk)
    if salida:
        return salida
    post.comments_closed = not post.comments_closed
    post.save(update_fields=['comments_closed'])
    AuditLog.objects.create(user=request.user, detail=f'post {post.pk}',
                            action='comments_closed' if post.comments_closed else 'comments_opened')
    messages.success(request, 'Comentarios cerrados: nadie puede responder.'
                     if post.comments_closed else 'Comentarios abiertos de nuevo.')
    return _volver(request, post)


@login_required
def post_toggle_pin(request, pk):
    """Fijar arriba en los listados (y desfijar)."""
    from apps.panel.models import AuditLog
    post, salida = _accion_staff(request, pk)
    if salida:
        return salida
    post.pinned = not post.pinned
    post.save(update_fields=['pinned'])
    AuditLog.objects.create(user=request.user, detail=f'post {post.pk}',
                            action='post_pinned' if post.pinned else 'post_unpinned')
    messages.success(request, 'Post fijado arriba.' if post.pinned else 'Post desfijado.')
    return _volver(request, post)


@login_required
def post_toggle_adult(request, pk):
    """Contenido sensible (+18): el post pasa a la sala cerrada o vuelve."""
    from apps.panel.models import AuditLog
    post, salida = _accion_staff(request, pk)
    if salida:
        return salida
    post.is_adult = not post.is_adult
    post.adult_flag_source = 'mod' if post.is_adult else ''
    post.save(update_fields=['is_adult', 'adult_flag_source'])
    AuditLog.objects.create(user=request.user, detail=f'post {post.pk}',
                            action='post_adult_on' if post.is_adult else 'post_adult_off')
    messages.success(request, 'Marcado como contenido sensible (+18): solo en la sala cerrada.'
                     if post.is_adult else 'Ya no está marcado como contenido sensible.')
    return _volver(request, post)


@login_required
def post_move_category(request, pk):
    """Mover el post a otra categoria del arbol."""
    from apps.panel.models import AuditLog
    from .models import Category
    post, salida = _accion_staff(request, pk)
    if salida:
        return salida
    slug = request.POST.get('topic', '').strip()
    cat = Category.objects.filter(slug=slug).exclude(slug=Category.ROOT_SLUG).first()
    if not cat:
        messages.error(request, 'Categoría no válida.')
        return _volver(request, post)
    antes = post.topic
    if antes != cat.slug:
        Category.objects.filter(slug=antes).update(times_used=models.F('times_used') - 1)
        Category.objects.filter(slug=cat.slug).update(times_used=models.F('times_used') + 1)
        post.topic = cat.slug
    # 5.27-D: mover (a donde sea) cierra la sugerencia del bibliotecario.
    post.suggested_topic = ''
    post.suggested_topic_note = ''
    post.save(update_fields=['topic', 'suggested_topic', 'suggested_topic_note'])
    AuditLog.objects.create(user=request.user, action='post_moved',
                            detail=f'post {post.pk}: {antes} -> {cat.slug}')
    messages.success(request, f'Post movido a «{cat.path_label()}».')
    return _volver(request, post)


@login_required
def post_topic_suggestion_dismiss(request, pk):
    """5.27-D: moderacion descarta la sugerencia de subforo del bibliotecario."""
    from apps.panel.models import AuditLog
    post, salida = _accion_staff(request, pk)
    if salida:
        return salida
    AuditLog.objects.create(user=request.user, action='topic_suggestion_dismissed',
                            detail=f'post {post.pk}: {post.suggested_topic}')
    post.suggested_topic = ''
    post.suggested_topic_note = ''
    post.save(update_fields=['suggested_topic', 'suggested_topic_note'])
    messages.success(request, 'Sugerencia descartada.')
    return _volver(request, post)


@login_required
def post_edit_title(request, pk):
    """Editar el titulo (y el asunto del hilo). La URL (slug) NO cambia: las
    direcciones compartidas no se rompen (decision 5.0-D)."""
    from apps.panel.models import AuditLog
    post, salida = _accion_staff(request, pk)
    if salida:
        return salida
    titulo = ' '.join(request.POST.get('title', '').split())[:300]
    if len(titulo) < 3:
        messages.error(request, 'El título es demasiado corto.')
        return _volver(request, post)
    antes = post.title
    post.title = titulo
    post.save(update_fields=['title'])
    from apps.forum.machina_glue import get_topic_for_post
    topic = get_topic_for_post(post)
    if topic:
        type(topic).objects.filter(pk=topic.pk).update(subject=titulo[:100])
    AuditLog.objects.create(user=request.user, action='post_title_edited',
                            detail=f'post {post.pk}: «{antes[:60]}» -> «{titulo[:60]}»')
    messages.success(request, 'Título actualizado.')
    return _volver(request, post)


@login_required
def message_delete_toggle(request, mpost_id):
    """Eliminar un comentario (reversible: queda como no aprobado y solo lo ve
    el staff, que puede restaurarlo). AuditLog siempre."""
    from machina.core.db.models import get_model
    from apps.panel.models import AuditLog
    MPost = get_model('forum_conversation', 'Post')
    m = get_object_or_404(MPost, pk=mpost_id)
    destino = request.META.get('HTTP_REFERER') or '/'
    if request.method != 'POST' or not _require_mod(request.user):
        return redirect(destino)
    m.approved = not m.approved
    m.save()
    AuditLog.objects.create(user=request.user, detail=f'mensaje {m.pk}',
                            action='message_restored' if m.approved else 'message_deleted')
    messages.success(request, 'Comentario restaurado.' if m.approved
                     else 'Comentario eliminado (el staff puede restaurarlo).')
    return redirect(destino.split('#')[0] + f'#msg-{m.pk}')


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
    # 5.29-B (decision de David, 2026-09-11): el voto de moderacion sigue
    # relanzando en solitario, pero UNA sola vez por frase. Para repetirlo
    # esta la llave inglesa del post (con coste y confirmacion).
    if value == -1 and es_admin and seg.opus_rescanned:
        messages.info(request, 'Esta frase ya tuvo su reanálisis profundo. Para repetirlo, '
                               'usa la llave inglesa del post.')
    elif value == -1 and es_admin:
        from .tasks import opus_rescan_segment
        opus_rescan_segment.delay(seg.pk)
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
    # 5.23-D: comentarios cerrados por moderacion (el staff sigue pudiendo)
    if post.comments_closed and not _require_mod(request.user):
        messages.error(request, 'Los comentarios de este post están cerrados.')
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
    from apps.wiki.models import COLORS
    from .models import Category
    MPost = get_model('forum_conversation', 'Post')
    q = request.GET.get('q', '').strip()
    scope = request.GET.get('scope', 'all')
    # 5.1-B.1 (orden de David): filtros por tipo de claim (semaforo) y por
    # categoria del post. Funcionan CON texto o SOLOS (filtrar sin escribir).
    # 5.1-D: las categorias salen de la taxonomia VIVA — el buscador se puebla
    # solo con cada categoria nueva que se añada.
    temas_vivos = [(c.slug, c.name) for c in Category.elegibles()]   # 5.23-E: sin la raiz
    color = request.GET.get('color', '').strip()
    if color not in dict(COLORS):
        color = ''
    tema = request.GET.get('tema', '').strip()
    if tema not in dict(temas_vivos):
        tema = ''
    results = {'posts': [], 'claims': [], 'segments': [], 'messages': []}
    if q or color or tema:
        query = SearchQuery(q, config='spanish') if q else None
        if scope in ('all', 'posts'):
            # 4.3-A.8: el buscador era la puerta de atras de la sala +18.
            visibles = Post.objects.publicos()   # 5.23-D: ni censurados ni pendientes
            if not _can_see_adult(request):
                visibles = visibles.exclude(is_adult=True)
            if tema:
                visibles = visibles.filter(topic=tema)
            if query:
                visibles = visibles.annotate(
                    sv=SearchVector('title', 'tags', 'topic', config='spanish')
                ).filter(sv=query)
            elif tema:
                visibles = visibles.order_by('-created_at')
            else:
                visibles = visibles.none()
            results['posts'] = visibles[:20]
        if scope in ('all', 'forum') and query:
            # El contenido machina es MarkupText: se busca su texto crudo.
            results['messages'] = (MPost.objects.filter(approved=True).annotate(
                sv=SearchVector('content', config='spanish')).filter(sv=query)
                .select_related('topic', 'poster')[:20])
        if scope in ('all', 'wiki'):
            claims = Claim.objects.all()
            if color:
                claims = claims.filter(color=color)
            if query:
                claims = claims.annotate(
                    sv=SearchVector('text_original', 'what_is_claimed',
                                    'what_evidence_says', config='spanish')
                ).filter(sv=query)
            elif color:
                claims = claims.order_by('-updated_at')
            else:
                claims = claims.none()
            results['claims'] = claims[:20]
        if scope in ('all', 'transcripts') and query:
            results['segments'] = TranscriptSegment.objects.annotate(
                sv=SearchVector('text', config='spanish')).filter(sv=query
            ).select_related('post')[:20]
    return render(request, 'analysis/search.html',
                  {'q': q, 'scope': scope, 'results': results,
                   'color': color, 'tema': tema,
                   'colores': COLORS, 'temas': temas_vivos})



@login_required
def resolve_attribution(request, segment_id):
    """4.4-I: un usuario con sesion resuelve una frase de atribucion incierta:
    le pone la voz que corresponde. Sin JS (form POST). Queda en la nota de la
    frase quien la resolvio, y se vuelve a probar el piloto automatico porque
    la puerta del 65 % puede haberse abierto."""
    from .models import TranscriptSegment
    from .services import try_launch_full
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
    try_launch_full(seg.post)
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
    """Voto positivo (ruta historica /upvote/): desde el 5.23-C es la flecha
    arriba del voto con karma."""
    return post_vote_karma(request, pk, 'up')


@login_required
def post_vote_karma(request, pk, direction):
    """5.23-C (ENMIENDA de David al README): ▲/▼ en el post — cada voto suma o
    resta 1 al karma del autor; positivos y negativos se ven en numero. Nadie
    vota lo suyo. Trending y el reescaneo de Opus siguen mirando SOLO los ▲."""
    from apps.forum.models import Vote
    from apps.forum.karma import aplicar_voto
    post = get_object_or_404(Post, pk=pk)
    if request.method != 'POST' or direction not in ('up', 'down'):
        return redirect('post_detail', pk=pk)
    if post.author_id == request.user.pk:
        messages.error(request, 'No puedes votar tu propio post.')
        return redirect('post_detail', pk=pk)
    value = 1 if direction == 'up' else -1
    delta = aplicar_voto(Vote, {'post': post}, request.user, value, post.author)
    if delta < 0 or value == -1:
        if post.trending_notified and not post.is_trending():
            post.trending_notified = False  # se rearma al caer del umbral
            post.save(update_fields=['trending_notified'])
    if delta > 0 and value == 1:
        from apps.accounts.services import notify as _notify
        _notify(post.author, f'{request.user.username} ha votado tu post: '
                             f'{(post.title or post.url)[:80]}',
                f'/post/{post.pk}/', kind='post_votes')
        # 4.2 D4: al CRUZAR el umbral (no en cada voto) avisa una sola vez.
        if not post.trending_notified and post.is_trending():
            post.trending_notified = True
            post.save(update_fields=['trending_notified'])
            from .tasks import notify_post_event
            notify_post_event(post, 'trending', '🔥 El post está en Trending')
    if value == -1:
        # 5.29-D (corrección de David): el reanálisis profundo del post lo piden
        # los votos EN CONTRA — de la comunidad (umbral del panel) o de moderación.
        from .tasks import maybe_trigger_opus_rescan
        if maybe_trigger_opus_rescan(post, request.user):  # unica puerta (Fase 3.4 §6)
            messages.info(request, 'Muchos usuarios discuten este contenido: '
                                   're-verificación con el modelo mayor en marcha.')
    return redirect('post_detail', pk=pk)


@login_required
def message_vote(request, mpost_id, direction):
    """5.23-C (orden de David): ▲/▼ en cada comentario del hilo, con karma para
    su autor. Sin votarse a uno mismo."""
    from machina.core.db.models import get_model
    from apps.forum.models import MessageVote
    from apps.forum.karma import aplicar_voto
    MPost = get_model('forum_conversation', 'Post')
    m = get_object_or_404(MPost, pk=mpost_id)
    destino = request.META.get('HTTP_REFERER') or '/'
    try:
        destino = f"/post/{int(m.topic.slug.split('-')[1])}/"
    except (IndexError, ValueError, AttributeError):
        pass
    destino = destino.split('#')[0] + f'#msg-{m.pk}'
    if request.method != 'POST' or direction not in ('up', 'down'):
        return redirect(destino)
    if m.poster_id == request.user.pk:
        messages.error(request, 'No puedes votar tu propio comentario.')
        return redirect(destino)
    aplicar_voto(MessageVote, {'machina_post_id': m.pk}, request.user,
                 1 if direction == 'up' else -1, m.poster)
    return redirect(destino)


def donations_page(request):
    """Pagina publica de donaciones: objetivo, progreso, PayPal (Bizum ONG llegara con la asociacion)."""
    from apps.panel.models import Donation, SystemSetting
    # 5.24-E: vuelta desde el boton alojado (return / cancel_return)
    if request.GET.get('gracias'):
        messages.success(request, '¡Gracias por tu donación! PayPal nos la confirma en unos '
                                  'segundos y se suma al depósito del mes.')
    elif request.GET.get('cancelado'):
        messages.info(request, 'Donación cancelada. Aquí sigues teniendo todas las opciones.')
    from apps.panel.services import live_monthly_cap
    cap, donated, base = live_monthly_cap()
    goal = SystemSetting.get_int('donation_goal_eur', 60)
    paypal_url = SystemSetting.get_str('paypal_url', '')
    return render(request, 'analysis/donations.html', {
        'donated': donated, 'goal': goal, 'base': base, 'cap': cap,
        'paypal_url': paypal_url,
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


# ------------------- 5.3-A: donaciones vivas y gastos a la vista -------------------

@csrf_exempt
def donation_capture(request):
    """El boton PayPal del banner captura en el navegador; hasta hoy nadie lo
    anotaba y el «Faltan X EUR» no se movia. Ahora el navegador avisa aqui.
    La donacion entra SIN verificar (un desconocido no puede inflar el tope de
    gasto con un POST): David la confirma en su panel contra su cuenta PayPal."""
    import json as _json
    from decimal import Decimal, InvalidOperation
    from apps.panel.models import Donation
    if request.method != 'POST':
        return redirect('donations')
    try:
        datos = _json.loads(request.body.decode() or '{}')
        cantidad = Decimal(str(datos.get('amount', '')))
        orden = str(datos.get('order', ''))[:60]
    except (ValueError, InvalidOperation):
        return HttpResponsePermanentRedirect('/donaciones/')
    if not (Decimal('1') <= cantidad <= Decimal('10000')) or not orden:
        from django.http import JsonResponse
        return JsonResponse({'ok': False}, status=400)
    nota = f'paypal-web:{orden}'
    from django.http import JsonResponse
    if Donation.objects.filter(note=nota).exists():   # idempotente
        return JsonResponse({'ok': True, 'dup': True})
    # 5.15 (orden de David): con credenciales en el .env, el pedido se
    # contrasta contra la API de PayPal — un curl con un pedido inventado
    # muere aqui. Sin credenciales, el circuito de siempre (riesgo en docs/85).
    from .paypal_check import verify_order
    veredicto_pp = verify_order(orden, cantidad)
    if veredicto_pp is False:
        from apps.panel.models import AuditLog
        AuditLog.objects.create(user=None, action='donation_reject',
                                detail=f'pedido no verificado: {orden[:40]} '
                                       f'({cantidad} EUR)')
        return JsonResponse({'ok': False, 'motivo': 'pedido no verificable'},
                            status=400)
    # 5.13-C (orden de David): el apadrinamiento queda ATADO a su post — al
    # verificarla David, si lo donado cubre el coste, el analisis se lanza solo.
    post_ap = None
    try:
        pk_ap = int(datos.get('post') or 0)
        if pk_ap:
            post_ap = Post.objects.filter(pk=pk_ap).first()
    except (TypeError, ValueError):
        post_ap = None
    d = Donation.objects.create(amount_eur=cantidad, method='PAYPAL',
                                note=nota, verified=False, post=post_ap)
    # 5.14-A (orden de David, revierte el paso previo del 5.13): «sin
    # verificación. Una vez el usuario done para el análisis del vídeo, que se
    # haga». El analisis SALE al donar; la donacion sigue entrando sin
    # verificar para el TOPE (solo lo verificado sube presupuesto) y David la
    # ve en su panel — si fuera falsa, la descarta y queda el rastro.
    if post_ap and post_ap.status == 'AWAITING_BUDGET':
        from django.db.models import Sum
        from .services import needs_sponsorship
        _, coste, _ = needs_sponsorship(post_ap)
        atado = float(Donation.objects.filter(post=post_ap)
                      .aggregate(s=Sum('amount_eur'))['s'] or 0)
        if atado >= float(coste):
            from .tasks import run_cheap_phase
            post_ap.status = 'PENDING'
            post_ap.save(update_fields=['status'])
            run_cheap_phase.delay(post_ap.pk)
    return JsonResponse({'ok': True})


# ---------------- 5.24-A (orden de David): donar sin ventana emergente ----------------

def _importe_donacion(raw):
    from decimal import Decimal, InvalidOperation
    try:
        v = Decimal(str(raw).replace(',', '.').strip())
    except (InvalidOperation, ValueError):
        return None
    if not (Decimal('1') <= v <= Decimal('10000')):
        return None
    return v.quantize(Decimal('0.01'))


def donation_start(request):
    """El formulario del banner (o del apadrinamiento) llega aqui: el servidor
    crea el pedido en PayPal y manda al usuario a pagar a paypal.com a pantalla
    completa. Sin credenciales, enlace clasico de PayPal (paypal_url del panel)."""
    from django.urls import reverse
    from apps.panel.models import SystemSetting
    from .paypal_check import create_order, credenciales_ok
    if request.method != 'POST':
        return redirect('donations')
    cantidad = _importe_donacion(request.POST.get('amount', ''))
    if cantidad is None:
        messages.error(request, 'Cantidad no válida: mínimo 1 €.')
        return redirect('donations')
    post_ap = None
    try:
        pk_ap = int(request.POST.get('post') or 0)
        post_ap = Post.objects.filter(pk=pk_ap).first() if pk_ap else None
    except (TypeError, ValueError):
        post_ap = None
    # 5.24-E: si las credenciales REST no valen (no hay, son de Sandbox o son
    # invalidas), la donacion va al BOTON ALOJADO de PayPal con la cantidad
    # puesta; el aviso IPN la anotara. Asi se puede donar aunque falten las Live.
    from .paypal_check import comprobar
    if not credenciales_ok() or comprobar() != 'ok':
        from urllib.parse import urlencode
        from django.urls import reverse as _rev
        from apps.panel.models import AuditLog
        business = SystemSetting.get_str('paypal_business', '').strip()
        url = SystemSetting.get_str('paypal_url', '')
        extra = {'amount': f'{cantidad:.2f}', 'currency_code': 'EUR'}
        if post_ap:
            extra['custom'] = f'post:{post_ap.pk}'
        if business:
            # 5.25-B (reporte de David: el alojado abria a 0 €): la URL de donacion
            # por ID de comerciante PRECARGA el importe (medido: donationAmount=7.00,
            # type=fixed) y admite las variables clasicas (retorno, IPN, custom).
            extra.update({
                'business': business,
                'item_name': ('Apadrinar el análisis de un vídeo en esestocierto?' if post_ap
                              else 'Donación a esestocierto? (fact-checking comunitario)'),
                'no_shipping': '1',
                'lc': 'en_US' if getattr(request, 'LANGUAGE_CODE', 'es') == 'en' else 'es_ES',
                'return': request.build_absolute_uri(_rev('donations')) + '?gracias=1',
                'cancel_return': request.build_absolute_uri(_rev('donations')) + '?cancelado=1',
                'notify_url': request.build_absolute_uri(_rev('donation_ipn')),
            })
            destino = 'https://www.paypal.com/donate?' + urlencode(extra)
        elif url:
            destino = url + ('&' if '?' in url else '?') + urlencode(extra)
        else:
            messages.error(request, 'PayPal no está configurado todavía.')
            return redirect('donations')
        AuditLog.objects.create(user=request.user if request.user.is_authenticated else None,
                                action='donation_started_hosted',
                                detail=f'{cantidad} EUR' + (f' post {post_ap.pk}' if post_ap else ''))
        return redirect(destino)
    locale = 'en-US' if getattr(request, 'LANGUAGE_CODE', 'es') == 'en' else 'es-ES'
    order_id, approve = create_order(
        cantidad, return_url=request.build_absolute_uri(reverse('donation_return')),
        cancel_url=request.build_absolute_uri(reverse('donations')) + '?cancelado=1',
        custom_id=f'post:{post_ap.pk}' if post_ap else 'donacion', locale=locale)
    if not approve:
        messages.error(request, 'PayPal no ha respondido; inténtalo en un minuto.')
        return redirect(post_ap.get_absolute_url() if post_ap else 'donations')
    from apps.panel.models import AuditLog
    AuditLog.objects.create(user=request.user if request.user.is_authenticated else None,
                            action='donation_started',
                            detail=f'{cantidad} EUR pedido {order_id}'
                                   + (f' post {post_ap.pk}' if post_ap else ''))
    return redirect(approve)


def donation_return(request):
    """PayPal devuelve aqui con ?token=<pedido>. El servidor CAPTURA (asi la
    donacion nace VERIFICADA: la ha cobrado el propio servidor), la anota una
    sola vez y, si estaba atada a un post en cola, lanza su analisis
    (5.14-A: «sin verificación, que se haga»)."""
    from decimal import Decimal
    from apps.panel.models import AuditLog, Donation
    from .paypal_check import capture_order
    order_id = (request.GET.get('token') or '')[:60]
    if not order_id:
        return redirect('donations')
    nota = f'paypal-web:{order_id}'
    previa = Donation.objects.filter(note=nota).first()
    if previa:   # idempotente: recargar la pagina de retorno no duplica
        messages.success(request, 'Esa donación ya estaba anotada. ¡Gracias!')
        return redirect(previa.post.get_absolute_url() if previa.post else 'donations')
    datos = capture_order(order_id)
    if not datos or datos.get('status') not in ('COMPLETED', 'APPROVED') or not datos.get('amount'):
        AuditLog.objects.create(user=None, action='donation_reject',
                                detail=f'captura fallida: {order_id}')
        messages.error(request, 'PayPal no ha confirmado el pago. Si te ha cobrado, '
                                'escríbenos a webmaster@esestocierto.com con la referencia '
                                f'{order_id}.')
        return redirect('donations')
    post_ap = None
    custom = datos.get('custom_id') or ''
    if custom.startswith('post:'):
        try:
            post_ap = Post.objects.filter(pk=int(custom.split(':', 1)[1])).first()
        except ValueError:
            post_ap = None
    cantidad = Decimal(str(datos['amount'])).quantize(Decimal('0.01'))
    d = Donation.objects.create(amount_eur=cantidad, method='PAYPAL', note=nota,
                                verified=True, post=post_ap)
    AuditLog.objects.create(user=None, action='donation_captured',
                            detail=f'{cantidad} EUR pedido {order_id}'
                                   + (f' post {post_ap.pk}' if post_ap else ''))
    if post_ap and post_ap.status == 'AWAITING_BUDGET':
        from django.db.models import Sum
        from .services import needs_sponsorship
        _, coste, _ = needs_sponsorship(post_ap)
        atado = float(Donation.objects.filter(post=post_ap)
                      .aggregate(s=Sum('amount_eur'))['s'] or 0)
        if atado >= float(coste):
            from .tasks import run_cheap_phase
            post_ap.status = 'PENDING'
            post_ap.save(update_fields=['status'])
            run_cheap_phase.delay(post_ap.pk)
            messages.success(request, f'¡Gracias! Donación de {cantidad} € recibida: el '
                                      f'análisis apadrinado arranca ahora mismo.')
            return redirect(post_ap.get_absolute_url())
        messages.success(request, f'¡Gracias! Donación de {cantidad} € atada a este análisis '
                                  f'(faltan {max(0.0, float(coste) - atado):.2f} € para cubrirlo).')
        return redirect(post_ap.get_absolute_url())
    messages.success(request, f'¡Gracias! Donación de {cantidad} € recibida y sumada al '
                              f'depósito del mes.')
    return redirect(post_ap.get_absolute_url() if post_ap else 'donations')


@csrf_exempt
def donation_ipn(request):
    """5.24-E: notify_url del boton ALOJADO de PayPal. PayPal manda un POST por
    cada pago; se le devuelve el cuerpo para que lo VERIFIQUE (VERIFIED) y solo
    entonces se anota la donacion (verificada, idempotente por txn_id, en EUR y
    Completed). Si `custom` trae post:<pk> y ese post espera en cola, se lanza
    su analisis (5.14-A). Siempre 200: PayPal reintenta lo que no sea 200."""
    from decimal import Decimal, InvalidOperation
    from django.http import HttpResponse
    from apps.panel.models import AuditLog, Donation
    from .paypal_check import verificar_ipn
    if request.method != 'POST':
        return HttpResponse(status=405)
    cuerpo = request.body          # ANTES de tocar request.POST (si no, RawPostDataException)
    datos = request.POST
    txn = (datos.get('txn_id') or '')[:60]
    if not txn:
        return HttpResponse('sin txn', status=200)
    nota = f'paypal-ipn:{txn}'
    if Donation.objects.filter(note=nota).exists():
        return HttpResponse('dup', status=200)
    if not verificar_ipn(cuerpo):
        AuditLog.objects.create(user=None, action='donation_reject',
                                detail=f'IPN no verificado: {txn}')
        return HttpResponse('invalid', status=200)
    if datos.get('payment_status') != 'Completed' or datos.get('mc_currency') != 'EUR':
        return HttpResponse('ignorado', status=200)
    try:
        cantidad = Decimal(str(datos.get('mc_gross', ''))).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return HttpResponse('importe', status=200)
    if cantidad < Decimal('0.01'):
        return HttpResponse('importe', status=200)
    post_ap = None
    custom = datos.get('custom') or ''
    if custom.startswith('post:'):
        try:
            post_ap = Post.objects.filter(pk=int(custom.split(':', 1)[1])).first()
        except ValueError:
            post_ap = None
    Donation.objects.create(amount_eur=cantidad, method='PAYPAL', note=nota,
                            verified=True, post=post_ap)
    AuditLog.objects.create(user=None, action='donation_captured',
                            detail=f'{cantidad} EUR IPN {txn}' + (f' post {post_ap.pk}' if post_ap else ''))
    if post_ap and post_ap.status == 'AWAITING_BUDGET':
        from django.db.models import Sum
        from .services import needs_sponsorship
        _, coste, _ = needs_sponsorship(post_ap)
        atado = float(Donation.objects.filter(post=post_ap).aggregate(s=Sum('amount_eur'))['s'] or 0)
        if atado >= float(coste):
            from .tasks import run_cheap_phase
            post_ap.status = 'PENDING'
            post_ap.save(update_fields=['status'])
            run_cheap_phase.delay(post_ap.pk)
    return HttpResponse('ok', status=200)


def _base_mensual():
    from apps.panel.services import live_monthly_cap
    return live_monthly_cap()[2]


def spending_page(request, ym=None):
    """5.3-A (orden de David): «en que se va gastando todo» — datos REALES del
    libro de cuentas, por tecnologia, del mes en curso (se reinicia solo cada
    dia 1 porque se agrupa por mes) y con el historico enlazado."""
    from collections import OrderedDict
    from django.utils import timezone as tz
    from django.http import Http404
    from .models import CostEntry
    from apps.panel.models import Donation, SystemSetting
    NOMBRES = {'anthropic': 'Claude (Anthropic) — análisis IA',
               'qwen': 'Qwen (Alibaba) — análisis IA y búsquedas',
               'assemblyai': 'AssemblyAI — transcripción y voces',
               'runpod': 'Runpod — GPU de audio',
               'brevo': 'Brevo — emails'}
    hoy = tz.localdate()
    actual = hoy.strftime('%Y-%m')
    ym = ym or actual
    try:
        year, month = int(ym[:4]), int(ym[5:7])
        assert 1 <= month <= 12 and ym[4] == '-'
    except (ValueError, AssertionError, IndexError):
        raise Http404
    filas = OrderedDict()
    total = 0.0
    for e in CostEntry.objects.filter(created_at__year=year,
                                      created_at__month=month):
        clave = e.provider
        filas.setdefault(clave, {'nombre': NOMBRES.get(clave, clave),
                                 'eur': 0.0, 'apuntes': 0})
        filas[clave]['eur'] += float(e.eur)
        filas[clave]['apuntes'] += 1
        total += float(e.eur)
    donado = sum(float(d.amount_eur) for d in Donation.objects.filter(
        created_at__year=year, created_at__month=month, verified=True))
    meses = sorted({e.strftime('%Y-%m') for e in
                    CostEntry.objects.dates('created_at', 'month')}, reverse=True)
    # 5.23-A (orden de David): trabajos de GPU completados y fallidos del mes.
    from .costs import gpu_jobs_month
    gpu_ok, gpu_fallos = gpu_jobs_month(year, month)
    return render(request, 'analysis/gastos.html', {
        'ym': ym, 'es_actual': ym == actual,
        'gpu_ok': gpu_ok, 'gpu_fallos': gpu_fallos,
        'filas': filas.values(), 'total': total, 'donado': donado,
        # 5.5-B: el objetivo es el presupuesto base del panel (ver banner)
        'objetivo': _base_mensual(),
        'meses': meses})
