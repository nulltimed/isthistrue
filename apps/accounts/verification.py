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
    # 6.7 (orden de David, 2026-11-09): si el alta trajo credito de regalo,
    # que el primer correo lo diga — de nada sirve un regalo que no se conoce.
    from django.db.models import Sum
    regalo = user.credit_moves.filter(reason='WELCOME') \
                 .aggregate(s=Sum('delta'))['s'] or 0
    ctx = {'username': user.username, 'url': url, 'regalo': regalo}
    with translation.override(_lang_for(user)):
        text = _('Hola %(username)s:\n\nPulsa para verificar tu cuenta:\n%(url)s\n\n'
                 'El enlace caduca en 72 horas. Si no creaste esta cuenta, ignora '
                 'este mensaje.') % {'username': user.username, 'url': url}
        if regalo:
            text += '\n\n' + _('Dentro te espera %(n)s crédito(s) de regalo: '
                               'sirven para adelantar un análisis sin esperar '
                               'la cola.') % {'n': regalo}
        msg = EmailMultiAlternatives(
            _('Verifica tu cuenta — esestocierto?'),
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
                 # 6.7: las donaciones murieron con la 6.1 — este correo aun las pedia.
                 'Proyecto open source (AGPL). Los votos son gratis siempre; los créditos '
                 'solo compran inmediatez.') % {'username': user.username}
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
