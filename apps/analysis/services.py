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


def open_validation_window(post):
    days = SystemSetting.get_int('validation_window_days', 3)
    post.status = 'PENDING_VALIDATION'
    post.validation_deadline = timezone.now() + timezone.timedelta(days=days)
    post.save(update_fields=['status', 'validation_deadline'])


# (should_opus_rescan eliminada en Fase 3.4 §6: la unica puerta al reescaneo es
#  apps.analysis.tasks.maybe_trigger_opus_rescan, con el candado de 50 usuarios.)
