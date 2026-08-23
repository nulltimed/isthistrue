"""Verificacion y bienvenida con diseño (multipart texto+HTML), enviadas via Brevo.

4.4-A.2: el correo se escribe en el idioma de QUIEN LO RECIBE, no en el del
servidor. Un correo de verificacion en un idioma que el destinatario no lee es
un registro perdido: es el unico paso obligatorio de todo el alta.
"""
from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _

SALT = 'email-verify'
MAX_AGE = 72 * 3600


def _lang_for(user):
    """Idioma del destinatario.

    1) Lo que eligio en Ajustes, si eligio algo.
    2) Si no, el idioma ACTIVO: el de la web que esta viendo mientras se
       registra, que es la mejor pista disponible sobre que idioma lee.
    3) Fuera de una peticion (una tarea de fondo), el del sitio.
    """
    return getattr(user, 'language', '') or translation.get_language() \
        or settings.LANGUAGE_CODE


def _site_host():
    for h in settings.ALLOWED_HOSTS:
        if 'escierto' in h:
            return h
    return settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost'


def send_verification_email(user):
    token = signing.dumps({'uid': user.pk}, salt=SALT)
    url = f'https://{_site_host()}/accounts/verify/{token}/'
    ctx = {'username': user.username, 'url': url}
    with translation.override(_lang_for(user)):
        text = _('Hola %(username)s:\n\nPulsa para verificar tu cuenta:\n%(url)s\n\n'
                 'El enlace caduca en 72 horas. Si no creaste esta cuenta, ignora '
                 'este mensaje.') % {'username': user.username, 'url': url}
        msg = EmailMultiAlternatives(
            _('Verifica tu cuenta — escierto. / isthistrue.'),
            text, settings.DEFAULT_FROM_EMAIL, [user.email])
        msg.attach_alternative(render_to_string('emails/verify.html', ctx), 'text/html')
    msg.send(fail_silently=not settings.DEBUG)


def send_welcome_email(user):
    ctx = {'username': user.username, 'host': _site_host()}
    with translation.override(_lang_for(user)):
        text = _('¡Bienvenido/a, %(username)s!\n\nTu cuenta está verificada. Qué puedes '
                 'hacer ya:\n'
                 '- Analizar contenidos: pega un enlace y el sistema extrae y clasifica '
                 'sus afirmaciones.\n'
                 '- Votar validaciones cuando llegues a Contribuidor (50 de karma o un '
                 'código de invitación).\n'
                 '- Seguir afirmaciones en la wiki para enterarte si cambian de color.\n\n'
                 'Recuerda: verificamos afirmaciones, nunca personas. Metodología pública '
                 'en /metodologia/.\n'
                 'Proyecto open source (AGPL) sin ánimo de lucro: si donas, los cupos de '
                 'análisis suben.') % {'username': user.username}
        msg = EmailMultiAlternatives(_('Cuenta verificada — bienvenido/a'),
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
