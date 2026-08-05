"""Notificaciones (campana + Brevo segun preferencia) y anonimizado RGPD."""
from django.conf import settings
from django.core.mail import send_mail
from .models import Notification


def notify(user, text, url=''):
    Notification.objects.create(user=user, text=text, url=url)
    if user.notify_mode == 'INSTANT' and user.email:
        try:
            send_mail(f'isthistrue: {text[:60]}', f'{text}\n\n{url}',
                      settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
        except Exception:
            pass
    # DAILY: la tarea beat send_daily_digests agrupa las no leidas


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
