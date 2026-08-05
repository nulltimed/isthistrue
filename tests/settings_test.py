"""Ajustes para el robot de tests: mock forzado, sin machina (aisla lo critico)."""
from config.settings import *  # noqa

MOCK_AGENTS = True
CELERY_TASK_ALWAYS_EAGER = True  # las tareas corren en el acto, sin worker
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # tests rapidos
STAGING_MODE = False  # los tests no dependen del entorno: en el espejo (STAGING_MODE=true) el middleware devolvia 302 en la API publica
