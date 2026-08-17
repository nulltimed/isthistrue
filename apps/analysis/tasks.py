"""
Pipeline Celery en DOS fases (README v2 §5):
  fase barata (transcripcion + Haiku + algoritmo) -> validacion -> fase cara (Sonnet).
"""
import logging
import os, re, shutil, tempfile
from celery import shared_task
from django.conf import settings
from django.utils import timezone

# 4.3-D — FALLO LATENTE EN PRODUCCION, corregido aqui: este modulo usaba
# `logger.info(...)` en _transcribe_first_tranche (rama de subtitulos VTT
# oficiales) SIN que `logger` existiera. Entro en el pase 4.3-A (c1887d3) y
# nadie lo vio porque esa rama solo se pisa cuando el video TIENE subtitulos con
# cues; en modo simulado no se ejecuta jamas. Un NameError ahi tumba la fase
# barata entera y el post se queda en CHEAP_RUNNING tras agotar los reintentos.
logger = logging.getLogger('analysis.tasks')

# 4.3-A.8: estos dos numeros eran el coste FIJO de cualquier post, durase 3 min o
# una hora. Se conservan como SUELO (un video corto no cuesta menos que esto) y el
# precio real lo calcula services.cost_cheap_eur/cost_full_eur por minutos.
COST_CHEAP_EUR = 0.05  # suelo del clasificador Sonnet; en mock tambien se contabiliza: INTENCIONAL (permite probar banner y candados sin gastar)
COST_FULL_EUR = 0.07  # suelo de los veredictos
COST_OPUS_RESCAN_EUR = 0.40  # Opus: 5-7x Sonnet; solo posts muy votados, 1 vez
# (4.3-A.7: estaba definida DOS veces en este archivo, 0.35 aqui y 0.40 mas abajo;
#  mandaba la segunda. Se conserva el valor vigente y se borra el duplicado.)


@shared_task(bind=True, max_retries=2)
def run_cheap_phase(self, post_id):
    """Transcripcion faster-whisper (primer tramo) + barrido Haiku + clasificacion."""
    from .models import Post, TranscriptSegment, DailyBudget
    from apps.agents import sweep, algorithm

    post = Post.objects.get(pk=post_id)
    from .services import cost_cheap_eur
    if not DailyBudget.try_spend(max(COST_CHEAP_EUR, cost_cheap_eur(post))):
        post.status = 'NEW'  # se reintentara cuando haya deposito
        post.save(update_fields=['status'])
        return 'budget_exhausted'

    post.status = 'CHEAP_RUNNING'
    # 4.3-D: cronometro. Sin esto, medir un video de una hora es un experimento
    # suelto que no se puede repetir (peticion del operador, docs/33 C2).
    post.cheap_started_at = timezone.now()
    post.save(update_fields=['status', 'cheap_started_at'])

    tmpdir = tempfile.mkdtemp(prefix='istt_audio_')
    try:
        # 4.2 F1: _transcribe_first_tranche guarda titulo y duracion del video
        # (extract_info) — el titulo sustituye al enlace en bruto en pagina, foro,
        # portada y campana ("suscrito a 10 posts, saber cual habla de un plumazo").
        import time as _time
        _t0 = _time.monotonic()
        segments, audio_path = _transcribe_first_tranche(post, tmpdir)
        post.transcribe_seconds = round(_time.monotonic() - _t0, 1)
        # Diarizacion ANTES de crear segmentos: hace falta el hablante para agrupar.
        from apps.agents.diarization import diarize
        _t1 = _time.monotonic()
        turns = diarize(audio_path) if (audio_path or settings.MOCK_AGENTS) else []
        post.diarize_seconds = round(_time.monotonic() - _t1, 1)
        post.save(update_fields=['transcribe_seconds', 'diarize_seconds'])
        logger.info('Post %s: transcribir %.1fs · diarizar %.1fs (%d min de vídeo)',
                    post.pk, post.transcribe_seconds, post.diarize_seconds,
                    round((post.duration_seconds or 0) / 60))
        # 4.2 D1 (decision de David): la unidad de transcripcion y de ANALISIS es la
        # FRASE COMPLETA por hablante; el timestamp es el inicio de esa frase.
        merged = merge_into_sentences(segments, turns)
        for seg in merged:
            TranscriptSegment.objects.create(post=post, **seg)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)  # audio SIEMPRE borrado
    generate_name_proposals.delay(post.pk)  # OCR de rotulos + contexto -> candidatos

    # Barrido universal Haiku: claims + señales + clickbait + adulto
    result = sweep.run(post)
    post.is_adult = post.is_adult or result['is_adult']
    if result['is_adult'] and not post.adult_flag_source:
        post.adult_flag_source = 'agent'
    post.manipulation_detected = result['manipulation']

    verdict = algorithm.classify(post, result)  # 'FACTUAL' | 'OPINION'
    # 4.2 A2 (decision de David): el clasificador YA NO relega. Solo sugiere;
    # el post nace SIEMPRE en Principal y relegar es accion manual de moderador.
    # 4.3-A.7: si el barrido volvio ilegible, "sin afirmaciones extraibles" es
    # MENTIRA (no las leimos, no es que no existan): no se sugiere Off-Topic.
    if verdict == 'OPINION' and not result.get('sweep_failed'):
        post.offtopic_suggested = True

    post.save()
    from .services import open_validation_window
    open_validation_window(post)
    from apps.forum.machina_glue import create_topic_for_post
    create_topic_for_post(post)
    archive_wayback.delay(post.pk)  # preservacion: TODO post (decidido)
    post.cheap_finished_at = timezone.now()
    post.save(update_fields=['cheap_finished_at'])
    notify_post_event(post, 'analysis', 'Transcripción y señales listas (pendiente de validación)')
    return 'pending_validation'


def notify_post_event(post, kind, text):
    """4.2 D2/D3: una notificacion de campana (y navegador via sondeo) para el
    autor y para los suscriptores del tipo que toque. kind: analysis|messages|trending."""
    from apps.accounts.services import notify
    from .models import PostSubscription
    url = f'/post/{post.pk}/'
    # El autor recibe SIEMPRE los avisos de analisis y de Trending (D4: "aviso a
    # autor/suscritos"); en 'messages' el aviso lo gestiona add_reply directamente.
    recipients = {} if kind == 'messages' else {post.author_id: post.author}
    field = {'analysis': 'on_analysis', 'messages': 'on_messages',
             'trending': 'on_trending'}[kind]
    for sub in (PostSubscription.objects.filter(post=post, **{field: True})
                .select_related('user')):
        recipients[sub.user_id] = sub.user
    title = (post.title or post.url)[:80]
    pref_key = {'analysis': 'post_phase', 'messages': 'thread_replies',
                'trending': 'trending'}[kind]
    for user in recipients.values():
        notify(user, f'{text}: {title}', url, kind=pref_key)


def launch_full_analysis(post):
    """Cola con prioridad: manipulacion con claims = paciente grave, primero."""
    prio = settings.PRIORITY_MANIPULATION if post.manipulation_detected \
        else settings.CELERY_TASK_DEFAULT_PRIORITY
    run_full_analysis.apply_async(args=[post.pk], priority=prio)


@shared_task(bind=True, max_retries=1)
def run_full_analysis(self, post_id):
    """Sonnet + SearXNG adaptativo + wiki + reincidencia. Solo tras validacion."""
    from .models import Post, DailyBudget
    from apps.agents import verdict as verdict_agent

    post = Post.objects.get(pk=post_id)
    from .services import cost_full_eur
    if not DailyBudget.try_spend(max(COST_FULL_EUR, cost_full_eur(post))):
        return 'budget_exhausted'  # beat lo reintentara; cola congelada si corte mensual

    post.status = 'FULL_RUNNING'
    post.full_started_at = timezone.now()
    post.save(update_fields=['status', 'full_started_at'])
    if settings.USE_BATCH_API:
        import json as _json
        from apps.agents.batch import submit_verdict_batch, poll_verdict_batch
        from apps.agents.verdict import _claims_from_segments
        claims = [c for c in _claims_from_segments(post) if c.get('kind') == 'FACTUAL']
        if claims:
            try:
                batch_id = submit_verdict_batch(post, claims)
                poll_verdict_batch.apply_async(args=[batch_id, post.pk, _json.dumps(claims)],
                                               countdown=120)
                return 'batch_submitted'  # poll_verdict_batch pondra DONE
            except Exception:
                pass  # si el lote falla, caemos a llamadas directas
    verdict_agent.run(post)  # crea/actualiza claims wiki, fuentes, colores
    post.status = 'DONE'
    post.full_finished_at = timezone.now()
    post.save(update_fields=['status', 'full_finished_at'])
    notify_post_event(post, 'analysis', 'Veredictos publicados')
    return 'done'


@shared_task
def launch_queued_analyses():
    """4.3-F: vacia la cola de los videos que esperaban presupuesto.

    Cada hora, por orden de llegada: si lo que queda del deposito de hoy cubre el
    coste estimado, se lanza. Si no cabe, se PARA — no se salta al siguiente aunque
    sea mas barato: quien llego antes, va antes. Una cola que adelanta a los
    pequenos condena a los grandes a no analizarse jamas.

    La donacion desatasca esto sola: sube el techo mensual y con el el deposito
    diario, asi que al ciclo siguiente ya cabe.
    """
    from .models import Post
    from .services import budget_left_today, cost_cheap_eur, cost_full_eur
    lanzados = 0
    for post in Post.objects.filter(status='AWAITING_BUDGET').order_by('created_at'):
        coste = cost_cheap_eur(post) + cost_full_eur(post)
        if coste > budget_left_today():
            break
        post.status = 'NEW'
        post.save(update_fields=['status'])
        run_cheap_phase.delay(post.pk)
        logger.info('Post %s sale de la cola de presupuesto (coste estimado %.2f EUR)',
                    post.pk, coste)
        lanzados += 1
    return lanzados


@shared_task
def relaunch_stuck_analyses():
    """4.3-E (decision de David: "que se relancen automaticamente").

    Un analisis puede quedarse clavado si el worker muere a mitad: Celery acusa
    recibo del mensaje ANTES de ejecutarlo (acks_late=False), asi que ese trabajo
    no se reintenta solo — el post se queda en CHEAP_RUNNING o FULL_RUNNING para
    siempre, con la rueda girando y sin que nadie se entere.

    Cada hora se buscan los que llevan atascados mas de STUCK_ANALYSIS_HOURS y se
    relanzan. Candado importante: se compara contra el reloj del propio analisis
    (4.3-D), no contra created_at, para no relanzar un video de una hora que
    simplemente esta TARDANDO. Y se relanza la fase que corresponde, no siempre
    la barata: repetir la transcripcion de un post que ya la tiene es tirar dinero.
    """
    from django.utils import timezone as tz
    from .models import Post
    limite = tz.now() - tz.timedelta(hours=settings.STUCK_ANALYSIS_HOURS)
    relanzados = 0
    for post in Post.objects.filter(status='CHEAP_RUNNING',
                                    cheap_started_at__lt=limite):
        logger.warning('Post %s atascado en CHEAP_RUNNING desde %s: relanzando',
                       post.pk, post.cheap_started_at)
        post.transcript_segments.all().delete()   # la transcripcion quedo a medias
        post.status = 'NEW'
        post.save(update_fields=['status'])
        run_cheap_phase.delay(post.pk)
        relanzados += 1
    for post in Post.objects.filter(status='FULL_RUNNING',
                                    full_started_at__lt=limite):
        logger.warning('Post %s atascado en FULL_RUNNING desde %s: relanzando',
                       post.pk, post.full_started_at)
        post.status = 'FULL_QUEUED'
        post.save(update_fields=['status'])
        run_full_analysis.apply_async(args=[post.pk])
        relanzados += 1
    # Los que se quedaron sin reloj (anteriores al 4.3-D) no se tocan: sin fecha
    # de arranque no se puede distinguir "atascado" de "recien empezado".
    return relanzados


@shared_task
def relegate_expired_validations():
    """Beat horario. 4.2 A2: YA NO relega — marca la sugerencia para moderadores
    (relegar es siempre accion humana). El nombre se conserva: beat lo referencia."""
    from .models import Post
    expired = Post.objects.filter(status='PENDING_VALIDATION',
                                  validation_deadline__lt=timezone.now())
    n = expired.count()
    for post in expired:
        post.status = 'VALIDATION_EXPIRED'
        post.offtopic_suggested = True
        post.relegation_reason = 'Sin validación comunitaria en plazo'
        post.save(update_fields=['status', 'offtopic_suggested', 'relegation_reason'])
    return n


_VTT_TIME = re.compile(r'(\d+):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})[.,](\d{3})')


def _parse_vtt(text):
    """4.2.1 I4: WebVTT -> segmentos {'start_seconds','end_seconds','text'}.
    Formato simple: linea de tiempos + lineas de texto; cabecera y notas fuera."""
    cues, cur = [], None
    for raw in text.splitlines():
        line = re.sub(r'<[^>]+>', '', raw).strip()
        m = _VTT_TIME.match(line)
        if m:
            h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
            cur = {'start_seconds': h1 * 3600 + m1 * 60 + s1 + ms1 / 1000,
                   'end_seconds': h2 * 3600 + m2 * 60 + s2 + ms2 / 1000, 'text': ''}
            cues.append(cur)
        elif cur is not None and line and not line.startswith(('WEBVTT', 'NOTE', 'Kind:', 'Language:')):
            cur['text'] = (cur['text'] + ' ' + line).strip()
    return [c for c in cues if c['text']]


_SENTENCE_END = re.compile(r'[.!?…]["»›)\]]?\s*$')


def merge_into_sentences(raw_segments, turns, max_chars=600):
    """4.2 D1: agrupa los fragmentos de whisper en FRASES COMPLETAS por hablante.
    Corta cuando: (a) la frase termina en . ! ? …, (b) cambia el hablante, o
    (c) se supera max_chars (candado anti-parrafada). El timestamp del grupo es
    el inicio del PRIMER fragmento: clic-para-saltar aterriza donde empezo la frase."""
    def speaker_of(seg):
        best, best_overlap = '', 0.0
        for (ts, te, label) in turns:
            overlap = min(seg['end_seconds'], te) - max(seg['start_seconds'], ts)
            if overlap > best_overlap:
                best, best_overlap = label, overlap
        return best

    merged, current = [], None
    for seg in raw_segments:
        spk = speaker_of(seg)
        text = seg['text'].strip()
        if not text:
            continue
        if (current is not None and current['speaker_label'] == spk
                and not _SENTENCE_END.search(current['text'])
                and len(current['text']) + len(text) < max_chars):
            current['text'] = f"{current['text']} {text}"
            current['end_seconds'] = seg['end_seconds']
        else:
            if current is not None:
                merged.append(current)
            current = {'start_seconds': seg['start_seconds'],
                       'end_seconds': seg['end_seconds'],
                       'text': text, 'speaker_label': spk}
    if current is not None:
        merged.append(current)
    return merged


def _transcribe_first_tranche(post, tmpdir):
    """yt-dlp audio -> faster-whisper small-int8 (CPU) del tramo inicial del video
    (techo settings.TRANSCRIBE_MAX_SECONDS; 4.3-A.8: 90 min, antes 20 cableados).
    En MOCK_AGENTS devuelve segmentos ficticios para probar sin descargar nada."""
    if settings.MOCK_AGENTS:
        if not post.title:  # 4.2 F1: tambien el espejo enseña titulo, no enlace
            post.title = '[SIMULADO] Vídeo de prueba del espejo'
            post.save(update_fields=['title'])
        return ([
            {'start_seconds': 0.0, 'end_seconds': 8.0,
             'text': '[SIMULADO] Hoy os voy a contar la verdad que nadie quiere que sepais.'},
            {'start_seconds': 8.0, 'end_seconds': 16.0,
             'text': '[SIMULADO] La torre Eiffel mide 300 metros y se termino en 1889.'},
            {'start_seconds': 16.0, 'end_seconds': 24.0,
             'text': '[SIMULADO] Yo creo que esto va a cambiar el mundo el año que viene.'},
        ], None)
    import yt_dlp
    from faster_whisper import WhisperModel
    outpath = os.path.join(tmpdir, 'audio.%(ext)s')
    opts = {'format': 'bestaudio/best', 'outtmpl': outpath, 'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            # 4.2.1 I4 (decision de David): si el video trae subtitulos HUMANOS,
            # ellos mandan sobre el oido de whisper (pronunciaciones dificiles).
            # Los automaticos NO (son otro ASR, sin ventaja). El audio se baja
            # igual: la diarizacion lo necesita para separar voces.
            'writesubtitles': True, 'writeautomaticsub': False,
            'subtitleslangs': ['es', 'gl', 'en'], 'subtitlesformat': 'vtt',
            # 4.3-A.8: el tramo ya no son 1200 s cableados (video de 1 h analizado
            # al 33% en silencio). Techo configurable en el .env.
            'download_ranges': yt_dlp.utils.download_range_func(
                None, [(0, settings.TRANSCRIBE_MAX_SECONDS)])}
    with yt_dlp.YoutubeDL(opts) as ydl:
        # 4.2 F1 (decision de David): el TITULO sustituye al enlace en bruto en la
        # pagina, el foro y las notificaciones. extract_info descarga Y devuelve
        # metadatos; antes se tiraban a la basura y post.title quedaba vacio siempre.
        info = ydl.extract_info(post.url, download=True) or {}
    updates = []
    if info.get('title') and not post.title:
        post.title = str(info['title'])[:300]
        updates.append('title')
    if info.get('duration') and not post.duration_seconds:
        post.duration_seconds = int(info['duration'])
        updates.append('duration_seconds')
    if updates:
        post.save(update_fields=updates)
    files = sorted(os.listdir(tmpdir))
    audio = next((os.path.join(tmpdir, f) for f in files if not f.endswith('.vtt')), None)
    vtt = next((os.path.join(tmpdir, f) for f in files if f.endswith('.vtt')), None)
    if vtt:
        with open(vtt, encoding='utf-8', errors='replace') as f:
            cues = _parse_vtt(f.read())
        if cues:
            logger.info('Transcripción tomada de subtítulos oficiales (%d cues, %s)',
                        len(cues), os.path.basename(vtt))
            return (cues, audio)
    model = WhisperModel('small', device='cpu', compute_type='int8')
    segs, _info = model.transcribe(audio, vad_filter=True)
    return ([{'start_seconds': s.start, 'end_seconds': s.end, 'text': s.text.strip()}
             for s in segs], audio)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def archive_wayback(self, post_id):
    """Preservacion legal por terceros: Internet Archive guarda la URL bajo su
    paraguas, no el nuestro. Nunca almacenamos multimedia."""
    import httpx
    from .models import Post
    post = Post.objects.get(pk=post_id)
    if settings.MOCK_AGENTS:
        return 'mock'
    try:
        httpx.get(f'https://web.archive.org/save/{post.url}', timeout=60,
                  follow_redirects=True)
        return 'archived'
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task
def generate_name_proposals(post_id):
    """Candidatos a nombre por hablante: OCR de rotulos + titulo/descripcion (contexto).
    Foto SOLO de Wikipedia (licencia libre); sin ficha -> sin foto."""
    from .models import Post
    from apps.wiki.models import SpeakerNameProposal
    # 4.3-A.1 K3 (decision de David 2026-08-16): los candidatos AUTOMATICOS quedan
    # DESACTIVADOS — el OCR pescaba creditos de edicion y ruido. Quien propone es
    # la comunidad (caja "¿Quien crees que es?"); la foto de Wikipedia se busca al
    # proponer. La funcion se conserva (la llama run_cheap_phase) como no-op.
    return 'auto_candidates_disabled'


@shared_task
def opus_rescan_segment(segment_id):
    """4.2 H5: una ORACION muy downvoteada se re-analiza con Opus (MODEL_PREMIUM).
    Candados: una vez por oracion, solo posts DONE, y presupuesto (try_spend)."""
    from .models import TranscriptSegment, DailyBudget
    seg = TranscriptSegment.objects.select_related('post').get(pk=segment_id)
    if seg.opus_rescanned or seg.post.status != 'DONE':
        return 'skip'
    if not DailyBudget.try_spend(0.10):  # una oracion, no el post entero
        return 'budget_exhausted'
    seg.opus_rescanned = True
    seg.save(update_fields=['opus_rescanned'])
    from apps.agents import search, client, prompts
    from apps.agents.verdict import MOCK_VERDICT
    from apps.wiki.services import upsert_claim
    results, sources_ok = search.search_with_status(seg.text, max_results=5)
    context = '\n'.join(f"- {r.get('title','')}: {r.get('url','')}\n  {r.get('content','')[:300]}"
                        for r in results)
    payload = f"CLAIM: {seg.text}\n\nRESULTADOS DE BUSQUEDA:\n{context or '(sin resultados)'}"
    v = client.call_json(settings.MODEL_PREMIUM, prompts.VERDICT_SYSTEM,
                         payload, max_tokens=1500, mock_payload=MOCK_VERDICT)
    if 'error' not in v:
        idx = list(seg.post.transcript_segments.all()).index(seg)
        upsert_claim(seg.post, {'text': seg.text, 'segment_index': idx},
                     v, sources_ok=sources_ok)
        notify_post_event(seg.post, 'analysis',
                          'Una oración muy discutida fue re-verificada con el modelo premium')
    return 'rescanned'


@shared_task
def opus_rescan(post_id):
    """Reescaneo premium (decidido por David): si los votos ▲ superan el
    opus_rescan_percent (40%) de los usuarios del foro, el post se re-verifica con
    MODEL_PREMIUM (Opus). Candados: minimo opus_rescan_min_users (50), UNA vez por
    post, y presupuesto. Los claims ganan nueva version en su historial."""
    from .models import Post, DailyBudget
    post = Post.objects.get(pk=post_id)
    if post.opus_rescanned or post.status != 'DONE':
        return 'skip'
    if not DailyBudget.try_spend(COST_OPUS_RESCAN_EUR):
        return 'budget_exhausted'
    post.opus_rescanned = True
    post.save(update_fields=['opus_rescanned'])
    from apps.agents import verdict as verdict_agent
    verdict_agent.run(post, model=settings.MODEL_PREMIUM)  # la firma real es run(post, model=None)
    from apps.panel.services import alert_admin
    alert_admin('Reescaneo Opus ejecutado',
                f'Post {post.pk} supero el umbral de votos y fue re-verificado con Opus.')
    return 'rescanned'


def maybe_trigger_opus_rescan(post):
    from apps.accounts.models import User
    from apps.panel.models import SystemSetting
    min_users = SystemSetting.get_int('opus_rescan_min_users', 50)
    percent = SystemSetting.get_int('opus_rescan_percent', 40)
    total = User.objects.filter(is_active=True, email_verified=True).count()
    if total < min_users or post.opus_rescanned or post.status != 'DONE':
        return False
    votes = post.votes.count()
    if votes * 100 > total * percent:
        opus_rescan.delay(post.pk)
        return True
    return False
