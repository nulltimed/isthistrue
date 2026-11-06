"""6.3 (orden de David, 2026-11-06): el registro en DOS CARRILES.

- Persona FISICA: triage ligero y barato, SIN investigar su identidad (el
  candado de particulares de la wiki, aplicado a la puerta): solo correos
  desechables. Se la juzga por su comportamiento dentro, con la moderacion
  que ya existe.
- Persona JURIDICA: el mismo escrutinio por IA de la API (apps/api/vetting),
  con las exclusiones de David (formaciones politicas y organismos contra la
  esencia de la web).
Toda denegacion es reclamable y la reclamacion cae en la bandeja de los
superusuarios, que tienen la ultima palabra.
"""
import logging

from django.contrib import messages
from django.shortcuts import redirect

logger = logging.getLogger('accounts.signup')

# Dominios de correo desechable mas comunes (triage, no dogma: lo denegado se
# reclama y lo decide una persona).
DISPOSABLE = {
    'mailinator.com', 'guerrillamail.com', '10minutemail.com', 'yopmail.com',
    'temp-mail.org', 'tempmail.com', 'trashmail.com', 'getnada.com',
    'sharklasers.com', 'dispostable.com', 'maildrop.cc', 'mintemail.com',
    'throwawaymail.com', 'fakeinbox.com', 'mohmal.com', 'tempinbox.com',
}


def route_new_signup(user, cleaned, request):
    """Decide el carril tras crear la cuenta. Devuelve una respuesta (redirect)
    si el flujo normal NO debe continuar, o None para seguir como siempre."""
    from .models import SignupVetting
    kind = cleaned.get('kind') or 'PERSON'
    vet = SignupVetting.objects.create(
        user=user, kind=kind,
        org_name=(cleaned.get('org_name') or '').strip()[:200],
        org_website=(cleaned.get('org_website') or '').strip()[:200])

    if kind == 'PERSON':
        dominio = user.email.split('@')[-1].lower()
        if dominio in DISPOSABLE:
            user.is_active = False
            user.save(update_fields=['is_active'])
            vet.status = 'DENIED'
            vet.verdict = {'reasons': ['Correo de un dominio desechable: necesitamos '
                                       'poder avisarte (verificación, avisos de '
                                       'moderación).'],
                           'category': 'triage', 'confidence': 'alta'}
            vet.save()
            messages.error(request, 'Registro denegado: el correo es de un dominio '
                                    'desechable. Si crees que es un error, reclama '
                                    'aquí mismo y lo revisará una persona.')
            return redirect('signup_appeal', pk=vet.pk, token=vet.appeal_token)
        # Triage superado: carril normal (verificacion de email de siempre).
        return None

    # Persona juridica: cuenta inactiva hasta el veredicto del escrutinio.
    user.is_active = False
    user.save(update_fields=['is_active'])
    vet.status = 'PENDING'
    vet.save(update_fields=['status'])
    from .tasks import vet_org_signup
    vet_org_signup.delay(vet.pk)
    messages.success(request, 'Cuenta de organización creada: el escrutinio '
                              'automático tarda unos minutos y el resultado llega '
                              'a vuestro correo. Si se deniega, podréis reclamar.')
    return redirect('login')


def resolve_org_vetting(vet_pk):
    """La pasada del agente para una persona juridica (llamada por la tarea)."""
    from django.utils import timezone
    from apps.api.vetting import vet as ai_vet
    from .models import SignupVetting
    from .verification import send_verification_email
    v = SignupVetting.objects.select_related('user').get(pk=vet_pk)
    if v.status != 'PENDING':
        return v.status
    dominio = v.user.email.split('@')[-1] if '@' in v.user.email else ''
    veredicto = ai_vet(v.org_name or v.user.username, 'ORG', v.org_website,
                       'registro como organización en la comunidad de esestocierto? '
                       'para publicar, comentar y pedir análisis', dominio)
    v.verdict = veredicto
    if veredicto['approve']:
        v.status = 'OK'
        v.user.is_active = True
        v.user.save(update_fields=['is_active'])
        v.save()
        send_verification_email(v.user)
    else:
        v.status = 'DENIED'
        v.save()
        _mail_denegacion(v)
    return v.status


def _mail_denegacion(v):
    from django.conf import settings
    from django.core.mail import send_mail
    motivos = '\n- '.join(v.verdict.get('reasons') or ['Sin detalle'])
    try:
        send_mail('esestocierto? — resultado de vuestro registro',
                  f'El escrutinio automático ha DENEGADO el registro de '
                  f'«{v.org_name or v.user.username}».\n\nMotivos:\n- {motivos}\n\n'
                  f'Si no estáis de acuerdo, reclamad aquí y lo revisará una persona:\n'
                  f'{settings.SITE_URL}/accounts/escrutinio/{v.pk}/{v.appeal_token}/',
                  settings.DEFAULT_FROM_EMAIL, [v.user.email])
    except Exception:
        logger.warning('No se pudo enviar el correo de denegacion del registro %s',
                       v.pk, exc_info=True)
