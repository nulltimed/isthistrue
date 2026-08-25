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
        # 4.3-E: la puerta del 50% se comprueba ANTES de registrar nada, para que
        # el usuario vea el motivo y no un voto que no sirve de nada.
        puede, motivo = identification_gate(post)
        if not puede:
            ValidationVote.objects.filter(post=post, user=user, kind=kind).delete()
            return False, motivo
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


def speaker_identification(post):
    """(identificados, total) de hablantes de un post. Sin diarizacion, (0, 0)."""
    from apps.wiki.models import SpeakerNameProposal
    etiquetas = set(post.transcript_segments.exclude(speaker_label='')
                    .values_list('speaker_label', flat=True))
    nombradas = set(SpeakerNameProposal.objects.filter(post=post, confirmed=True)
                    .values_list('speaker_label', flat=True)) & etiquetas
    return len(nombradas), len(etiquetas)


def identification_gate(post):
    """4.3-E (decision de David): para marcar un video como factual —y con ello
    lanzar los veredictos y los semaforos— al menos la MITAD de los hablantes
    tienen que estar identificados.

    Por que tiene sentido: la wiki se puebla por personas. Gastar en veredictos
    sobre frases que no se pueden atribuir a nadie es pagar por algo que no
    llegara nunca a una ficha.

    Devuelve (puede_votarse, mensaje). Si el video no tiene diarizacion (cero
    etiquetas) la puerta NO se aplica: no se puede exigir identificar a nadie
    cuando el sistema no ha separado voces.
    """
    identificados, total = speaker_identification(post)
    if total == 0:
        return True, ''
    minimo = min_identified_percent()
    hacen_falta = -(-total * minimo // 100)     # techo, sin float
    if identificados >= hacen_falta:
        return True, ''
    return False, (f'Antes de marcarlo como factual hay que identificar al menos al '
                   f'{minimo}% de los hablantes: van {identificados} de {total} '
                   f'(hacen falta {hacen_falta}). Propón o vota un nombre en '
                   f'«¿Quién habla?» — sin nombre no hay página en la wiki.')


def min_identified_percent():
    """4.4-G (nota de David, 2026-08-24): la puerta sube del 50 al 65 %."""
    from apps.panel.models import SystemSetting
    return max(0, min(100, SystemSetting.get_int('min_identified_speakers_percent', 65)))


def try_autopilot(post, factual=None):
    """4.4-G (nota de David: la puerta del 65 % «frena TODO», el voto Y el piloto
    automatico). Aqui vive el piloto automatico del 4.4-B con la puerta delante:
    un video factual pasa solo a la verificacion con fuentes si (1) sigue
    pendiente de validacion, (2) hay cupo diario y (3) los hablantes
    identificados llegan al minimo.

    Y lo que hace que la puerta sea una ESPERA y no un muro: se vuelve a llamar
    cada vez que se CONFIRMA un nombre (naming._confirm). Sin esta segunda
    llamada, ningun video con dos voces se verificaria solo jamas — la puerta
    siempre esta cerrada al terminar la fase barata, porque nadie ha tenido
    tiempo de nombrar a nadie. Es el patron «mecanismo montado y puerta tapiada».

    `factual`: lo dice la fase barata al terminar; en las llamadas posteriores
    se deduce de la sugerencia del clasificador (Off-Topic sugerido = opinion).
    Devuelve True si lanzo la fase cara.
    """
    from .tasks import auto_verify_slot_free, launch_full_analysis, notify_post_event
    if post.status != 'PENDING_VALIDATION':
        return False
    if factual is None:
        factual = not post.offtopic_suggested
    if not factual or not identification_gate(post)[0] or not auto_verify_slot_free():
        return False
    post.status = 'FULL_QUEUED'
    post.save(update_fields=['status'])
    launch_full_analysis(post)
    notify_post_event(post, 'analysis', 'Analizado: verificando con fuentes')
    return True


def waiting_for_identification(post):
    """4.4-G (nota de David): AVISO visible cuando es la identificacion lo que
    frena la verificacion con fuentes. Devuelve (espera, identificados, total,
    minimo) — espera=True solo si el video es factual, sigue pendiente y la
    puerta esta cerrada."""
    identificados, total = speaker_identification(post)
    minimo = min_identified_percent()
    espera = (post.status == 'PENDING_VALIDATION' and not post.offtopic_suggested
              and total > 0 and not identification_gate(post)[0])
    return espera, identificados, total, minimo


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


def queue_threshold_eur():
    """Cuanto puede costar un analisis antes de mandarlo a la cola: un porcentaje
    del deposito del DIA (4.3-F, decision de David: 50%)."""
    from apps.panel.models import SystemSetting
    from apps.panel.services import live_daily_budget
    pct = max(0, min(100, SystemSetting.get_int('queue_threshold_percent', 50)))
    return live_daily_budget() * pct / 100.0


def needs_sponsorship(post):
    """4.3-F: (va_a_la_cola, coste_estimado, donacion_sugerida).

    Regla de David: si un video se lleva mas de la mitad de la asignacion diaria,
    no se analiza al momento. Entra en cola y se lanza solo cuando haya deposito
    —normalmente al dia siguiente— o antes si alguien lo apadrina donando.

    Ojo con el porque: cobrar no hace aparecer el dinero. El fusible mira el
    deposito, no el bolsillo de quien envia. Lo que desatasca la cola es que la
    donacion SUBE el techo mensual (live_monthly_cap = base + donaciones), y con
    el, el deposito diario. Por eso el apadrinamiento funciona y un pago suelto
    no serviria de nada.
    """
    import math
    coste = cost_cheap_eur(post) + cost_full_eur(post)
    umbral = queue_threshold_eur()
    if umbral <= 0 or coste <= umbral:
        return False, coste, 0.0
    sugerida = round(math.ceil(coste * 2) / 2.0, 2) or 0.5   # a medios euros
    return True, round(coste, 2), sugerida


def budget_left_today():
    """Euros que quedan hoy. Se usa para decidir si la cola puede avanzar."""
    from apps.panel.services import live_daily_budget
    from .models import DailyBudget
    from django.utils import timezone as tz
    fila = DailyBudget.objects.filter(date=tz.localdate()).first()
    gastado = float(fila.spent_eur) if fila else 0.0
    return max(0.0, live_daily_budget() - gastado)


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


def cost_dating_eur(post):
    """4.4-G: lo que cuesta volver a datar un video (llave inglesa, etapa b).
    Tokens de la transcripcion (12.000 caracteres como mucho) al precio del
    modelo de datacion: centimos."""
    from apps.agents.catalog import model_for, prices, USD_EUR
    pin, pout = prices(model_for('dating'))
    tokens_in = 3500 + 600           # ~12.000 caracteres + cabecera
    return round(((tokens_in * pin + 400 * pout) / 1e6) * USD_EUR, 4)


def cost_deep_eur(post):
    """4.4-G: reserva del reanalisis profundo. Antes era un fijo (0,40 EUR) sin
    mirar la duracion; ahora escala como la fase cara por el precio relativo del
    modelo profundo frente al de veredictos, con el fijo como suelo."""
    from apps.agents.catalog import model_for, prices
    from .tasks import COST_OPUS_RESCAN_EUR
    pin_v, _ = prices(model_for('verdict'))
    pin_d, _ = prices(model_for('deep'))
    ratio = (pin_d / pin_v) if pin_v else 1.0
    return round(max(COST_OPUS_RESCAN_EUR, cost_full_eur(post) * ratio), 4)


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
