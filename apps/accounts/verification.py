"""Verificacion de email con token firmado (72 h de validez)."""
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

SALT = 'email-verify'
MAX_AGE = 72 * 3600


def send_verification_email(user):
    token = signing.dumps({'uid': user.pk}, salt=SALT)
    host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost'
    for h in settings.ALLOWED_HOSTS:
        if 'escierto' in h:
            host = h
            break
    url = f'https://{host}/accounts/verify/{token}/'
    send_mail('Verifica tu cuenta — isthistrue / escierto',
              f'Hola {user.username}:\n\nPulsa para verificar tu cuenta:\n{url}\n\n'
              'El enlace caduca en 72 horas. Si no creaste esta cuenta, ignora este mensaje.',
              settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=not settings.DEBUG)


def verify_token(token):
    from .models import User
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        return User.objects.filter(pk=data.get('uid')).first()
    except signing.BadSignature:
        return None
