"""Serie 6.15 (2026-11-09): puente de registro para el worker.

`poll_verdict_batch` vive en batch.py, que el worker solo importaba si ÉL
mismo había ejecutado antes `_submit_batch` (import perezoso): un worker
recién reiniciado que recibiera el sondeo de un lote en vuelo lo descartaría
como «unregistered task» y los veredictos del lote se perderían en silencio.
Mismo mal que apps/forum (ver apps/forum/tasks.py y tests/test_serie615.py).
"""
from .batch import poll_verdict_batch  # noqa: F401
