"""6.2: escrutinio asincrono de las solicitudes de clave + correo del resultado."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger('api.tasks')


@shared_task
def vet_api_key(pk):
    from .models import ApiKey
    from .vetting import vet
    sol = ApiKey.objects.get(pk=pk)
    if sol.status != 'PENDING':
        return 'ya decidida'
    dominio = sol.contact_email.split('@')[-1] if '@' in sol.contact_email else ''
    v = vet(sol.entity_name, sol.kind, sol.website, sol.purpose, dominio)
    sol.ai_verdict = v
    if v['approve']:
        clave = sol.approve()
        _mail(sol, f'Tu clave de la API de esestocierto? está aprobada.\n\n'
                   f'Clave: {clave}\n\n'
                   f'Se envía en la cabecera X-API-Key. Nivel gratuito: '
                   f'{sol.daily_limit()} peticiones/día con atribución obligatoria '
                   f'(«Datos de esestocierto?», enlazado). Documentación: /api/')
    else:
        from django.utils import timezone
        sol.status = 'DENIED'
        sol.decided_at = timezone.now()
        sol.save()
        motivos = '\n- '.join(v.get('reasons') or ['Sin detalle'])
        _mail(sol, f'Tu solicitud de clave de la API de esestocierto? ha sido '
                   f'DENEGADA por el escrutinio automático.\n\nMotivos:\n- {motivos}\n\n'
                   f'Si no estás de acuerdo, reclama aquí y lo revisará una persona:\n'
                   f'{settings.SITE_URL}/api/reclamar/{sol.pk}/{sol.appeal_token}/')
    return sol.status


def _mail(sol, cuerpo):
    try:
        send_mail('API de esestocierto? — resultado de tu solicitud', cuerpo,
                  settings.DEFAULT_FROM_EMAIL, [sol.contact_email])
    except Exception:
        logger.warning('No se pudo enviar el correo de la solicitud %s', sol.pk,
                       exc_info=True)
