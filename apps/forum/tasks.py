"""Serie 6.15 (2026-11-09): el PUENTE que faltaba hacia el worker.

Celery autodiscover solo importa el `tasks.py` de cada app. Las tareas del
foro vivían en `moderation.py` y el worker JAMÁS las registró: beat
programaba `resolve_expired_warnings` cada hora y el worker la descartaba
(«Received unregistered task», visto en producción el 09-11), y cada mensaje
nuevo del foro mandaba `moderate_machina_post` a la basura — el triaje de
moderación (Haiku) no corría. El CI no podía verlo: con ALWAYS_EAGER todo
corre en línea, en el proceso web, donde el módulo ya estaba importado.

Importarlas aquí las registra en el worker. Candado: tests/test_serie615.py
(toda @shared_task de apps/ debe estar registrada tras el arranque).
"""
from .moderation import moderate_machina_post, resolve_expired_warnings  # noqa: F401
