"""4.4-C: el vigía nocturno de los modelos."""
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger('panel.models')


@shared_task
def check_models():
    """Una llamada mínima a cada modelo configurado. Coste: céntesimas de céntimo.

    Si uno cae, se anota y se avisa por email. La web NO se para: cuando llegue el
    momento de usarlo, el cliente ya sabe caer al suplente (client.call_full).
    """
    from apps.agents import catalog
    from apps.agents.client import call_full
    from .models import ModelHealth

    caidos = []
    for clave in catalog.TASK_KEYS:
        modelo = catalog.model_for(clave)
        try:
            call_full(modelo, 'Responde OK.', 'ping', max_tokens=5,
                      mock_payload={'ok': True}, allow_substitute=False)
            ok, detalle = True, ''
        except Exception as exc:
            ok, detalle = False, repr(exc)[:200]
            caidos.append(modelo)
        ModelHealth.objects.update_or_create(
            model_id=modelo, defaults={'ok': ok, 'detail': detalle})

    if caidos:
        logger.error('Modelos que no responden: %s', ', '.join(caidos))
        try:
            from django.core.mail import send_mail
            lista = '\n'.join(f'  · {catalog.label(m)} → suplente: '
                               f'{catalog.label(catalog.substitute(m)) or "(ninguno)"}'
                               for m in caidos)
            send_mail('[isthistrue] Modelos que no responden',
                      'La comprobación diaria ha encontrado modelos caídos:\n\n'
                      + lista +
                      '\n\nLa web sigue funcionando con los suplentes. Los veredictos '
                      'que emitan quedan marcados con su modelo.\n'
                      'Panel: /panel/modelos/',
                      settings.DEFAULT_FROM_EMAIL,
                      [getattr(settings, 'ADMIN_ALERT_EMAIL', '')], fail_silently=True)
        except Exception:
            pass
    return f'{len(catalog.TASK_KEYS)} comprobados, {len(caidos)} caídos'
