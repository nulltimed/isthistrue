"""Ajustes para el robot de tests: mock forzado, sin machina (aisla lo critico)."""
from config.settings import *  # noqa

MOCK_AGENTS = True
CELERY_TASK_ALWAYS_EAGER = True  # las tareas corren en el acto, sin worker
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # tests rapidos
STAGING_MODE = False  # los tests no dependen del entorno: en el espejo (STAGING_MODE=true) el middleware devolvia 302 en la API publica
# Los tests de logo-por-dominio usan HTTP_HOST reales (RequestFactory):
ALLOWED_HOSTS = list(ALLOWED_HOSTS) + ['testserver', 'escierto.xyztserver.com',
                                       'isthistrue.xyztserver.com', 'wikitrue.xyztserver.com', 'wiki.testserver']

# 4.4-B: los reintentos de búsqueda duermen `search_retry_seconds` (20 por
# defecto) cuando SearXNG devuelve vacío porque los motores están suspendidos.
# En el banco de pruebas eso son esperas REALES: la suite pasó de 5 s a 326 s en
# el CI. Aquí la espera baja al mínimo — se sigue ejercitando el camino del
# reintento, pero sin castigar cada ciclo del ritual con cinco minutos.
SETTING_DEFAULTS = {**SETTING_DEFAULTS, 'search_retry_seconds': '0'}
