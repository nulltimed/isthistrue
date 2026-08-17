"""Logica de votacion, modo arranque y lanzamiento de fases (README v2 §5)."""
from django.conf import settings
from django.utils import timezone
from apps.panel.models import SystemSetting


def startup_mode_active():
    """Modo arranque: mientras usuarios activos < N, valida 1 voto de moderador/David."""
    from apps.accounts.models import User
    n = SystemSetting.get_int('startup_mode_min_users', 50)
    active = User.objects.filter(is_active=True, email_verified=True).count()
    return active < n


def cast_vote(post, user, kind):
    """Registra voto Contribuidor+ y dispara la fase cara si se alcanza el umbral.
    Devuelve (ok, mensaje)."""
    from .models import ValidationVote
    from .tasks import launch_full_analysis

    is_mod = user.effective_level() == 'MOD' or user.is_superuser
    if not (user.is_contrib_plus() or is_mod):
        return False, 'Necesitas nivel Contribuidor o superior para votar.'

    ValidationVote.objects.get_or_create(post=post, user=user, kind=kind)

    if kind == 'VALIDATE' and post.status == 'PENDING_VALIDATION':
        needed = 1 if (startup_mode_active() and is_mod) \
            else SystemSetting.get_int('votes_to_validate', 5)
        if post.distinct_validation_votes('VALIDATE') >= needed:
            post.status = 'FULL_QUEUED'
            post.save(update_fields=['status'])
            launch_full_analysis(post)
            warn_unnamed_speakers(post)   # 4.3-C
            warn_long_video(post)         # 4.3-D
            return True, 'Validado: análisis completo lanzado.'
        return True, 'Voto registrado.'

    if kind == 'RESCUE' and post.category == 'OFFTOPIC':
        needed = 1 if (startup_mode_active() and is_mod) \
            else SystemSetting.get_int('votes_to_rescue', 10)
        if post.distinct_validation_votes('RESCUE') >= needed:
            # El analisis de rescate lo paga el presupuesto global (modo simple).
            post.category = 'MAIN'
            post.status = 'FULL_QUEUED'
            post.save(update_fields=['category', 'status'])
            from apps.forum.machina_glue import move_topic
            move_topic(post)
            launch_full_analysis(post)
            return True, 'Rescatado: análisis completo lanzado.'
        return True, 'Voto de rescate registrado.'

    return False, 'Voto no aplicable al estado actual del post.'


def unnamed_speakers(post):
    """Etiquetas de hablante de este post que NO tienen nombre confirmado.
    Sin nombre no hay ficha en la wiki: sus afirmaciones se quedan en el vídeo."""
    from apps.wiki.models import SpeakerNameProposal
    etiquetas = set(post.transcript_segments.exclude(speaker_label='')
                    .values_list('speaker_label', flat=True))
    nombradas = set(SpeakerNameProposal.objects
                    .filter(post=post, confirmed=True)
                    .values_list('speaker_label', flat=True))
    return sorted(etiquetas - nombradas)


def warn_unnamed_speakers(post):
    """4.3-C (decisión de David): en el momento en que un análisis reúne los votos
    y arranca la fase de veredictos, se avisa a quienes votaron y a quienes siguen
    el post de que hay hablantes sin identificar — porque sin nombre no habrá
    página en la wiki. Campana siempre; email según las preferencias de cada uno
    (silencio nocturno, pausa y resumen diario los respeta notify()).
    """
    from apps.accounts.services import notify
    from .models import ValidationVote
    pendientes = unnamed_speakers(post)
    if not pendientes:
        return 0
    titulo = post.title or post.url
    texto = (f'«{titulo}» ya tiene los votos y va a generar veredictos, pero '
             f'{len(pendientes)} hablante(s) siguen sin identificar. Sin nombre no '
             f'habrá página en la wiki: si sabes quién habla, propónlo o vota una '
             f'propuesta.')
    destinatarios = {v.user for v in ValidationVote.objects.filter(post=post)
                     .select_related('user')}
    destinatarios |= {s.user for s in post.subscriptions.select_related('user')}
    destinatarios.add(post.author)
    for u in destinatarios:
        notify(u, texto, url=f'/post/{post.pk}/', kind='speakers_unnamed')
    return len(destinatarios)


def warn_long_video(post):
    """4.3-D (decision A2 de docs/33): AVISO, nunca muro. Cuando el analisis caro
    arranca sobre un video que pasa del tramo gratuito, se avisa a quienes votaron,
    a los suscritos y al autor de lo que cuesta y de la donacion que lo sostiene.
    El gasto entra en el presupuesto normal: nadie se queda sin analisis por esto,
    y el aviso sale DESPUES de lanzarlo, para que se note que no es un peaje.
    """
    from apps.accounts.services import notify
    from .models import ValidationVote
    donacion = suggested_donation_eur(post)
    if not donacion:
        return 0
    minutos = video_minutes(post)
    coste = cost_cheap_eur(post) + cost_full_eur(post)
    texto = (f'«{post.title or post.url}» dura {minutos} minutos y se analiza entero: '
             f'cuesta unos {coste:.2f} € en total, con {free_minutes()} minutos '
             f'gratuitos. Si puedes, una donación de {donacion:.2f} € cubre este '
             f'análisis. Es voluntaria: el análisis ya está en marcha.')
    destinatarios = {v.user for v in ValidationVote.objects.filter(post=post)
                     .select_related('user')}
    destinatarios |= {s.user for s in post.subscriptions.select_related('user')}
    destinatarios.add(post.author)
    for u in destinatarios:
        notify(u, texto, url='/donaciones/', kind='long_video_cost')
    return len(destinatarios)


def open_validation_window(post):
    days = SystemSetting.get_int('validation_window_days', 3)
    post.status = 'PENDING_VALIDATION'
    post.validation_deadline = timezone.now() + timezone.timedelta(days=days)
    post.save(update_fields=['status', 'validation_deadline'])


# (should_opus_rescan eliminada en Fase 3.4 §6: la unica puerta al reescaneo es
#  apps.analysis.tasks.maybe_trigger_opus_rescan, con el candado de 50 usuarios.)


# --- 4.3-A.8: el dinero se cuenta por MINUTOS de video -------------------------
# David: "al final todo va al presupuesto diario y mensual". Con el coste fijo
# (0,05 + 0,07 EUR) el contador MENTIA: un video de una hora gasta 4-6 veces mas
# que uno de cinco minutos y el fusible saltaba tarde. Ahora cada fase reserva lo
# que de verdad va a costar, y el techo diario/mensual protege de verdad.
CHEAP_SHARE = 0.35   # el barrido de clasificacion es ~1/3 del gasto de un post
FULL_SHARE = 0.65    # los veredictos (con busquedas y lotes) son el resto


def video_minutes(post):
    """Minutos que se van a analizar de verdad: la duracion, con el techo de
    transcripcion. Si la duracion es desconocida (0), se asume el techo — es lo
    prudente: reservar de mas y devolver, nunca gastar sin haber reservado."""
    from django.conf import settings as dj
    segundos = post.duration_seconds or dj.TRANSCRIBE_MAX_SECONDS
    return max(1, min(int(segundos), dj.TRANSCRIBE_MAX_SECONDS) // 60)


def cents_per_minute():
    from apps.panel.models import SystemSetting
    return max(0, SystemSetting.get_int('cents_per_video_minute', 12))


def cost_cheap_eur(post):
    return round(video_minutes(post) * cents_per_minute() / 100.0 * CHEAP_SHARE, 4)


def cost_full_eur(post):
    return round(video_minutes(post) * cents_per_minute() / 100.0 * FULL_SHARE, 4)


def free_minutes():
    from apps.panel.models import SystemSetting
    return max(0, SystemSetting.get_int('analysis_free_minutes', 20))


def suggested_donation_eur(post):
    """Donacion sugerida por pasarse del tramo gratuito. Se cobra SOLO el exceso
    y se redondea hacia arriba a medios euros (pedir 0,37 EUR es ridiculo).
    Devuelve 0.0 si el video cabe en el tramo gratuito."""
    import math
    extra = video_minutes(post) - free_minutes()
    if extra <= 0:
        return 0.0
    euros = extra * cents_per_minute() / 100.0
    return round(math.ceil(euros * 2) / 2.0, 2) or 0.5
