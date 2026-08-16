"""Notificaciones (campana + Brevo segun preferencia) y anonimizado RGPD."""
from django.conf import settings
from django.core.mail import send_mail
from .models import Notification


def notify(user, text, url='', kind=None):
    """La campana SIEMPRE registra. El email calla si: la campana esta en pausa
    (24 h), es de noche (23-8, si quiet_night) o el tipo esta apagado (4.3-A J2)."""
    from django.utils import timezone
    if kind and hasattr(user, 'wants') and not user.wants(kind):
        return  # tipo apagado por el usuario: ni campana ni email
    Notification.objects.create(user=user, text=text, url=url)
    paused = (user.notifications_paused_until
              and user.notifications_paused_until > timezone.now())
    night = user.quiet_night and timezone.localtime().hour in (23, 0, 1, 2, 3, 4, 5, 6, 7)
    if user.notify_mode == 'INSTANT' and user.email and not paused and not night:
        try:
            send_mail(f'isthistrue: {text[:60]}', f'{text}\n\n{url}',
                      settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        except Exception:
            pass
    # DAILY/WEEKLY: los agrupa la tarea beat send_daily_digests


def anonymize_user(user):
    """Autoborrado RGPD (quiz 3A): la cuenta desaparece; el contenido queda anonimo."""
    user.username = f'usuario-borrado-{user.pk}'
    user.email = ''
    user.first_name = user.last_name = ''
    user.birth_date = None
    if user.avatar:
        user.avatar.delete(save=False)
    user.avatar = None
    user.is_active = False
    user.set_unusable_password()
    user.save()
