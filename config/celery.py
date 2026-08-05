import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('isthistrue')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    # Relegar a Off-Topic los posts cuya validacion (5 votos / 3 dias) caduco:
    'relegar-validaciones-caducadas': {
        'task': 'apps.analysis.tasks.relegate_expired_validations',
        'schedule': 3600.0,
    },
    'advertencias-48h': {
        'task': 'apps.forum.moderation.resolve_expired_warnings',
        'schedule': 3600.0,
    },
    'resumen-diario-notificaciones': {
        'task': 'apps.accounts.tasks.send_daily_digests',
        'schedule': 86400.0,
    },
}
