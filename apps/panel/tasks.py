"""Generacion masiva de codigos: 1 a 1.000.000, txt descargable (README v2 §7)."""
import io
from celery import shared_task
from django.core.files.base import ContentFile

BATCH_BG_THRESHOLD = 10000  # por encima: segundo plano con aviso


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
