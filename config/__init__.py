# Carga la app Celery al importar Django, para que las tareas @shared_task
# usen la app configurada (broker Redis, eager en tests) y no la de por defecto.
from .celery import app as celery_app

__all__ = ('celery_app',)
