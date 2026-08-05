"""Configuracion Django de isthistrue. / escierto. — Hito 2A revisado."""
import os
from pathlib import Path
from dotenv import load_dotenv
from machina import MACHINA_MAIN_TEMPLATE_DIR, MACHINA_MAIN_STATIC_DIR

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'inseguro-solo-desarrollo')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
STAGING_MODE = os.getenv('STAGING_MODE', 'false').lower() == 'true'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost').split(',')]

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django_otp', 'django_otp.plugins.otp_totp',
    'django_prometheus',
    # --- Foro django-machina (decision congelada: componentes OSS dentro de Django) ---
    'mptt', 'haystack', 'widget_tweaks',
    'machina',
    'machina.apps.forum',
    'machina.apps.forum_conversation',
    'machina.apps.forum_conversation.forum_attachments',
    'machina.apps.forum_conversation.forum_polls',
    'machina.apps.forum_feeds',
    'machina.apps.forum_member',
    'machina.apps.forum_moderation',
    'machina.apps.forum_permission',
    'machina.apps.forum_search',
    'machina.apps.forum_tracking',
    # --- Apps propias ---
    'apps.accounts', 'apps.analysis', 'apps.agents', 'apps.wiki',
    'apps.forum', 'apps.panel', 'apps.embeds',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'machina.apps.forum_permission.middleware.ForumPermissionMiddleware',
    'config.middleware.HostLanguageMiddleware',
    'config.middleware.StagingAccessMiddleware',  # espejo: solo invitados
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates', MACHINA_MAIN_TEMPLATE_DIR],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'machina.core.context_processors.metadata',
        'config.context_processors.quota_banner',  # cupos publicos + donaciones
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('POSTGRES_DB', 'isthistrue'),
    'USER': os.getenv('POSTGRES_USER', 'isthistrue'),
    'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
    'HOST': os.getenv('POSTGRES_HOST', 'db'),
    'PORT': os.getenv('POSTGRES_PORT', '5432'),
}}

CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'machina_attachments': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
                            'LOCATION': '/tmp/machina_attachments'},
}
HAYSTACK_CONNECTIONS = {'default': {'ENGINE': 'haystack.backends.simple_backend.SimpleEngine'}}
MACHINA_FORUM_NAME = 'isthistrue.'
MACHINA_MARKUP_LANGUAGE = ('markdown2.markdown', {'safe_mode': 'escape'})  # Markdown basico, HTML escapado
MACHINA_MARKUP_WIDGET = 'django.forms.Textarea'

AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'

LANGUAGE_CODE = 'es'
LANGUAGES = [('es', 'Castellano'), ('en', 'English')]
LOCALE_PATHS = [BASE_DIR / 'locale']  # i18n real: makemessages / compilemessages
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static', MACHINA_MAIN_STATIC_DIR]
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Celery ---
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_BROKER_TRANSPORT_OPTIONS = {'priority_steps': list(range(10)), 'queue_order_strategy': 'priority'}
CELERY_TASK_DEFAULT_PRIORITY = 5
PRIORITY_MANIPULATION = 9

# --- Agentes / economia (60 EUR/mes, 2 EUR/dia: decidido) ---
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
MODEL_CHEAP = os.getenv('MODEL_CHEAP', 'claude-haiku-4-5-20251001')
MODEL_VERDICT = os.getenv('MODEL_VERDICT', 'claude-sonnet-4-6')
MODEL_OFFTOPIC = os.getenv('MODEL_OFFTOPIC', MODEL_CHEAP)
_mock = os.getenv('MOCK_AGENTS', 'auto').lower()
MOCK_AGENTS = (_mock == 'true') or (_mock == 'auto' and DEBUG and not ANTHROPIC_API_KEY)
if STAGING_MODE:
    MOCK_AGENTS = True  # el espejo JAMAS gasta deposito
DAILY_BUDGET_EUR = float(os.getenv('DAILY_BUDGET_EUR', '2.0'))
MONTHLY_CAP_EUR = float(os.getenv('MONTHLY_CAP_EUR', '60'))
SEARXNG_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
SEARCHES_PER_CLAIM = int(os.getenv('SEARCHES_PER_CLAIM', '3'))
SEARCHES_PER_CLAIM_AMBIGUOUS = int(os.getenv('SEARCHES_PER_CLAIM_AMBIGUOUS', '5'))
EMBEDDINGS_MODEL = os.getenv('EMBEDDINGS_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')
EMBEDDINGS_DIM = 384  # MiniLM multilingue; congelado (antes 1024)
HF_TOKEN = os.getenv('HF_TOKEN', '')

# --- Turnstile / email ---
TURNSTILE_SITE_KEY = os.getenv('TURNSTILE_SITE_KEY', '')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
if os.getenv('EMAIL_HOST_USER'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST'); EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER'); EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@localhost')

ADMIN_ALERT_EMAIL = os.getenv('ADMIN_ALERT_EMAIL', 'contact@xyztserver.com')
PROMETHEUS_EXPORT_MIGRATIONS = False
OCR_FRAME_INTERVAL = int(os.getenv('OCR_FRAME_INTERVAL', '5'))
USE_BATCH_API = os.getenv('USE_BATCH_API', 'true').lower() == 'true' and not MOCK_AGENTS
