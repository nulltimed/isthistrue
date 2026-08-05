"""
Pipeline Celery en DOS fases (README v2 §5):
  fase barata (transcripcion + Haiku + algoritmo) -> validacion -> fase cara (Sonnet).
"""
import os, shutil, tempfile
from celery import shared_task
from django.conf import settings
from django.utils import timezone

COST_CHEAP_EUR = 0.01
COST_FULL_EUR = 0.07  # estimacion conservadora con tope adaptativo


@shared_task(bind=True, max_retries=2)
def run_cheap_phase(self, post_id):
    """Transcripcion faster-whisper (primer tramo) + barrido Haiku + clasificacion."""
    from .models import Post, TranscriptSegment, DailyBudget
    from apps.agents import sweep, algorithm

    post = Post.objects.get(pk=post_id)
    if not DailyBudget.try_spend(COST_CHEAP_EUR):
        post.status = 'NEW'  # se reintentara cuando haya deposito
        post.save(update_fields=['status'])
        return 'budget_exhausted'

    post.status = 'CHEAP_RUNNING'
    post.save(update_fields=['status'])

    tmpdir = tempfile.mkdtemp(prefix='istt_audio_')
    try:
        segments, audio_path = _transcribe_first_tranche(post, tmpdir)
        objs = [TranscriptSegment.objects.create(post=post, **seg) for seg in segments]
        # Diarizacion local (2B): hablantes sin identidades; el nombrado es participativo
        from apps.agents.diarization import diarize, label_segments
        if audio_path or settings.MOCK_AGENTS:
            label_segments(objs, diarize(audio_path))
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
    if verdict == 'OPINION':
        post.category = 'OFFTOPIC'
        post.status = 'OFFTOPIC_SIGNALED'
        post.save()
        from apps.forum.machina_glue import create_topic_for_post
        create_topic_for_post(post)
        archive_wayback.delay(post.pk)
        return 'relegated'

    post.save()
    from .services import open_validation_window
    open_validation_window(post)
    from apps.forum.machina_glue import create_topic_for_post
    create_topic_for_post(post)
    archive_wayback.delay(post.pk)  # preservacion: TODO post (decidido)
    return 'pending_validation'


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
    if not DailyBudget.try_spend(COST_FULL_EUR):
        return 'budget_exhausted'  # beat lo reintentara; cola congelada si corte mensual

    post.status = 'FULL_RUNNING'
    post.save(update_fields=['status'])
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
    post.save(update_fields=['status'])
    return 'done'


@shared_task
def relegate_expired_validations():
    """Beat horario: sin 5 votos en 3 dias -> Off-Topic conservando señales."""
    from .models import Post
    expired = Post.objects.filter(status='PENDING_VALIDATION',
                                  validation_deadline__lt=timezone.now())
    for post in expired:
        post.category = 'OFFTOPIC'
        post.status = 'OFFTOPIC_SIGNALED'
        post.relegation_reason = 'Sin validación comunitaria en plazo'
        post.save(update_fields=['category', 'status', 'relegation_reason'])
    return expired.count()


def _transcribe_first_tranche(post, tmpdir):
    """yt-dlp audio -> faster-whisper small-int8 (CPU) del primer tramo de 20 min.
    En MOCK_AGENTS devuelve segmentos ficticios para probar sin descargar nada."""
    if settings.MOCK_AGENTS:
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
            'download_ranges': yt_dlp.utils.download_range_func(None, [(0, 1200)])}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([post.url])
    audio = next((os.path.join(tmpdir, f) for f in os.listdir(tmpdir)), None)
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
    from apps.agents.ocr import extract_names_from_video
    from apps.agents.wikidata import photo_for
    post = Post.objects.get(pk=post_id)
    labels = list(post.transcript_segments.exclude(speaker_label='')
                  .values_list('speaker_label', flat=True).distinct())
    if not labels:
        return 'no_speakers'
    candidates = dict(extract_names_from_video(post.url, post.duration_seconds or 1200))
    title_names = {}
    from apps.agents.ocr import NAME_RX
    for m in NAME_RX.findall(post.title or ''):
        title_names[m] = title_names.get(m, 0) + 5  # el titulo pesa mas
    for n, c in title_names.items():
        candidates[n] = candidates.get(n, 0) + c
    for label in labels:
        for name in sorted(candidates, key=candidates.get, reverse=True)[:4]:
            SpeakerNameProposal.objects.get_or_create(
                post=post, speaker_label=label, candidate_name=name,
                defaults={'photo_url': photo_for(name), 'source': 'ocr'})
    return f'{len(candidates)} candidatos'
