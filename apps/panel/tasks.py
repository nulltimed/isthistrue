"""Tareas del panel.

1. Generacion masiva de codigos canjeables: 1 a 1.000.000, txt descargable
   (README v2 §7). RESTAURADA POR EL OPERADOR: el pase 4.4-C reescribio este
   fichero desde cero y se la llevo por delante junto con BATCH_BG_THRESHOLD,
   que apps/panel/views.py importa — el panel ENTERO caia con ImportError.
2. 4.4-C: el vigia nocturno de los modelos.
"""
import io
import logging

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile

BATCH_BG_THRESHOLD = 10000  # por encima: segundo plano con aviso

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


@shared_task
def generate_code_batch(batch_id):
    from apps.accounts.models import RedeemCode
    from .models import CodeBatch
    batch = CodeBatch.objects.get(pk=batch_id)
    try:
        buf = io.StringIO()
        chunk = []
        for i in range(batch.count):
            code = RedeemCode(grants_level=batch.level, batch=f'batch-{batch.pk}')
            chunk.append(code)
            buf.write(code.code + '\n')
            if len(chunk) >= 5000:
                RedeemCode.objects.bulk_create(chunk)
                chunk = []
        if chunk:
            RedeemCode.objects.bulk_create(chunk)
        batch.file.save(f'codigos-{batch.level}-{batch.pk}.txt',
                        ContentFile(buf.getvalue().encode()))
        batch.status = 'READY'
    except Exception as e:
        batch.status = 'FAILED'
        batch.save()
        raise e
    batch.save()
