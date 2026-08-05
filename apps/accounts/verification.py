"""Verificacion y bienvenida con diseño (multipart texto+HTML), enviadas via Brevo."""
from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

SALT = 'email-verify'
MAX_AGE = 72 * 3600


def _site_host():
    for h in settings.ALLOWED_HOSTS:
        if 'escierto' in h:
            return h
    return settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost'


def send_verification_email(user):
    token = signing.dumps({'uid': user.pk}, salt=SALT)
    url = f'https://{_site_host()}/accounts/verify/{token}/'
    ctx = {'username': user.username, 'url': url}
    text = (f'Hola {user.username}:\n\nPulsa para verificar tu cuenta:\n{url}\n\n'
            'El enlace caduca en 72 horas. Si no creaste esta cuenta, ignora este mensaje.')
    msg = EmailMultiAlternatives('Verifica tu cuenta — escierto. / isthistrue.',
                                 text, settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(render_to_string('emails/verify.html', ctx), 'text/html')
    msg.send(fail_silently=not settings.DEBUG)


def send_welcome_email(user):
    ctx = {'username': user.username, 'host': _site_host()}
    text = (f'¡Bienvenido/a, {user.username}!\n\nTu cuenta está verificada. Qué puedes hacer ya:\n'
            '- Analizar contenidos: pega un enlace y el sistema extrae y clasifica sus afirmaciones.\n'
            '- Votar validaciones cuando llegues a Contribuidor (50 de karma o un código de invitación).\n'
            '- Seguir claims en la wiki para enterarte si cambian de color.\n\n'
            'Recuerda: verificamos afirmaciones, nunca personas. Metodología pública en /metodologia/.\n'
            'Proyecto open source (AGPL) sin ánimo de lucro: si donas, los cupos de análisis suben.')
    msg = EmailMultiAlternatives('Cuenta verificada — bienvenido/a',
                                 text, settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(render_to_string('emails/welcome.html', ctx), 'text/html')
    msg.send(fail_silently=True)


def verify_token(token):
    from .models import User
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        return User.objects.filter(pk=data.get('uid')).first()
    except signing.BadSignature:
        return None
