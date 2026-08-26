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
# HTTPS termina en el Nginx del host: sin esto, los POST de navegador fallan con CSRF 403
# (el navegador manda Origin https:// y Django creia estar en http). Fase 3.4 §1.
CSRF_TRUSTED_ORIGINS = [f'https://{h}' for h in ALLOWED_HOSTS
                        if h not in ('localhost', '127.0.0.1')]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# YouTube exige Referer en el embed (error 153 sin el): enviamos SOLO el origen
# a terceros (equilibrio privacidad/compatibilidad; jamas 'unsafe-url'). Pase 4.2 A1.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # sirve /static/ en produccion (DEBUG=False)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'machina.apps.forum_permission.middleware.ForumPermissionMiddleware',
    # HostLanguageMiddleware eliminado (Fase 3.9): idioma = cookie del selector →
    # Accept-Language del navegador → 'es' (LocaleMiddleware, ya arriba en la cadena).
    'config.middleware.UserLanguageMiddleware',   # 4.4-A: el idioma del perfil manda
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
        'config.context_processors.logo_variant',   # logo por DOMINIO (4.2 C6)
        'config.context_processors.unread_notifications',  # campana (4.2 D2)
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
# Sin esto, Django acepta '1234' como contraseña (faltaba desde el Hito 2A;
# detectado en el checklist 64 del pase 3.7 — el formulario "mudo" era doble:
# ni mostraba errores NI habia validadores que los generasen):
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.EmailOrUsernameBackend',
                           'django.contrib.auth.backends.ModelBackend']
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'  # salir -> portada, nunca la pantalla de Django (4.2 A6)

LANGUAGE_CODE = 'es'
LANGUAGES = [('es', 'Español'), ('en', 'English')]
LOCALE_PATHS = [BASE_DIR / 'locale']  # i18n real: makemessages / compilemessages
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static', MACHINA_MAIN_STATIC_DIR]
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Celery ---
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_BROKER_TRANSPORT_OPTIONS = {'priority_steps': list(range(10)), 'queue_order_strategy': 'priority'}
CELERY_TASK_DEFAULT_PRIORITY = 5
PRIORITY_MANIPULATION = 9
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# --- Agentes / economia (100 EUR/mes, ~3 EUR/dia: decidido por David en Fase 3.3) ---
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
MODEL_CHEAP = os.getenv('MODEL_CHEAP', 'claude-haiku-4-5-20251001')
MODEL_VERDICT = os.getenv('MODEL_VERDICT', 'claude-sonnet-4-6')
MODEL_OFFTOPIC = os.getenv('MODEL_OFFTOPIC', MODEL_CHEAP)
# Clasificador critico (manipulacion + hecho/opinion): Sonnet por decision de David (conmutable)
MODEL_CLASSIFIER = os.getenv('MODEL_CLASSIFIER', 'claude-sonnet-4-6')
# Reescaneo premium al superar el 40% de votos: Opus
MODEL_PREMIUM = os.getenv('MODEL_PREMIUM', 'claude-opus-4-8')
# Reparto DEFINITIVO (README §25): moderacion SOLO Haiku (moderation.py usa MODEL_CHEAP);
# MODERATION_TRIAGE_MODEL y MODEL_RESCAN (ronda v2) retirados: nada los leia.
_mock = os.getenv('MOCK_AGENTS', 'auto').lower()
MOCK_AGENTS = (_mock == 'true') or (_mock == 'auto' and DEBUG and not ANTHROPIC_API_KEY)
if STAGING_MODE:
    MOCK_AGENTS = True  # el espejo JAMAS gasta deposito
DAILY_BUDGET_EUR = float(os.getenv('DAILY_BUDGET_EUR', '3.0'))
MONTHLY_CAP_EUR = float(os.getenv('MONTHLY_CAP_EUR', '100'))
SEARXNG_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
SEARCHES_PER_CLAIM = int(os.getenv('SEARCHES_PER_CLAIM', '3'))
SEARCHES_PER_CLAIM_AMBIGUOUS = int(os.getenv('SEARCHES_PER_CLAIM_AMBIGUOUS', '5'))
# 4.3-A.7 (fallo de raiz del primer analisis REAL): el barrido mandaba la
# transcripcion ENTERA en una sola llamada con max_tokens=2000. Con el mock
# (3 frases) cabia; un video real trae cientos y el JSON volvia CORTADO ->
# JSONDecodeError -> claims=[] -> CERO señales y CERO veredictos, en silencio.
# Ahora se trocea. Ambos limites se editan en el .env sin tocar codigo.
SWEEP_BATCH_SIZE = int(os.getenv('SWEEP_BATCH_SIZE', '40'))    # frases por llamada
SWEEP_MAX_TOKENS = int(os.getenv('SWEEP_MAX_TOKENS', '8000'))  # techo de respuesta

# 4.3-A.7 (peticion de David): TODOS los umbrales vivos se pueden fijar desde el
# .env. Reparto de papeles, para que no haya dos jefes discutiendo:
#   .env  = la FABRICA. Siembra el valor la primera vez (seed_settings) y, con
#           `seed_settings --force`, pisa lo que haya. Cambiarlo pide Regla de Oro.
#   panel = el MANDO EN VIVO. Una vez sembrado, lo que se guarde en /panel/settings/
#           manda sobre el .env (decision congelada: umbrales en SystemSetting).
# Si una clave nunca se sembro, get_int cae aqui: el .env sigue siendo la verdad.
SETTING_DEFAULTS = {k: os.getenv(k.upper(), v) for k, v in {
    'opinion_ratio_percent': '70',
    'minutes_per_factual_claim': '5',
    'votes_to_validate': '5',
    'votes_to_rescue': '10',
    'validation_window_days': '3',
    'startup_mode_min_users': '50',
    'mod_vote_weight': '5',
    'name_confirm_points': '5',
    'budget_base_eur': '100',
    'budget_hard_ceiling_eur': '200',
    'paypal_url': '',
    'opus_rescan_percent': '40',
    'opus_rescan_min_users': '50',
    'donation_goal_eur': '100',
    'trending_votes_threshold': '5',
    'trending_window_days': '7',
    'segment_opus_downvotes': '5',
    'message_sensitive_reports': '5',
    'registration_open': '1',
    'lang_es': '1', 'lang_en': '1',
    # 4.4-C: el modelo y el metodo de envio de cada tarea (panel de modelos).
    'model_sweep': 'claude-haiku-4-5-20251001',
    'model_classify': 'claude-sonnet-4-6',
    'model_dating': 'claude-haiku-4-5-20251001',
    'model_attribution': 'claude-haiku-4-5-20251001',   # 4.4-I
    'model_verdict': 'claude-sonnet-4-6',
    'model_moderation': 'claude-haiku-4-5-20251001',
    'model_deep': 'claude-opus-4-8',
    'delivery_sweep': 'direct', 'delivery_classify': 'direct',
    'delivery_dating': 'direct', 'delivery_verdict': 'direct', 'delivery_attribution': 'direct',
    'delivery_moderation': 'direct', 'delivery_deep': 'direct',
    'full_transcript_verdict': '1',     # decision de David: transcripcion entera
    'web_searches_per_claim': '3',      # 4.4-E: tope de busquedas del modelo por afirmacion
    # 4.4-B: el semaforo.
    'auto_verify_daily_cap': '5',       # videos que se verifican solos al dia
    'search_retries': '2',              # reintentos cuando los motores se suspenden
    'search_retry_seconds': '20',       # espera entre reintentos
    'deep_scan_votes': '5',             # votos para el reanalisis profundo
    'official_sources': ('ine.es,europa.eu,boe.es,bde.es,aemet.es,seg-social.es,'
                         'sepe.es,who.int,un.org,oecd.org'),
    # 4.3-A.7: ventana de contexto del semaforo (frases del mismo hablante).
    'verdict_context_before': '1',
    'verdict_context_after': '1',
    # 4.3-A.8 (decision de David): cualquier usuario puede postear hasta N minutos
    # sin mas; por encima se le AVISA de la donacion que sostiene ese analisis
    # (nunca se le bloquea: la puerta de submit es login + email verificado y esa
    # decision esta congelada). El precio va en CENTIMOS por minuto para que el
    # ajuste siga siendo un entero editable en el panel.
    'analysis_free_minutes': '20',
    'cents_per_video_minute': '12',
    # 4.3-C: las fichas de persona nacen con el freno de indexacion puesto.
    'wiki_index_people': '0',
    # 4.3-E: minimo de hablantes identificados para poder validar como factual.
    'min_identified_speakers_percent': '65',   # 4.4-G (David): del 50 al 65, y frena TODO
    'diarize_second_pass_skew_percent': '20',
    'attribution_sense_pass': '1',             # 4.4-I: Haiku revisa quien dijo cada frase (0 apaga)  # 4.4-H: voz minoritaria por debajo -> segunda pasada (0 apaga)
    # 4.3-F: porcentaje del deposito diario a partir del cual un video espera en
    # cola en vez de analizarse al momento.
    'queue_threshold_percent': '50',
}.items()}

# 4.3-A.8: el video se transcribe ENTERO hasta este techo (antes: 1200 s fijos en
# el codigo, y un video de una hora se analizaba al 33% sin avisar a nadie).
# David: "se tienen que procesar igual que los videos de 5 minutos".
TRANSCRIBE_MAX_SECONDS = int(os.getenv('TRANSCRIBE_MAX_SECONDS', '5400'))
# 4.3-E: horas que un analisis puede llevar "en marcha" antes de darlo por
# atascado y relanzarlo. Con el techo de 90 min de video y pyannote en CPU, un
# analisis legitimo puede pasar de dos horas: 6 deja margen de sobra.
STUCK_ANALYSIS_HOURS = int(os.getenv('STUCK_ANALYSIS_HOURS', '6'))
PROBE_TIMEOUT_SECONDS = int(os.getenv('PROBE_TIMEOUT_SECONDS', '12'))
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
# 4.4-G (B.2): USE_BATCH_API ya NO decide nada en el codigo — el metodo de envio
# lo manda el panel (catalog.delivery_for). Queda como semilla de compatibilidad:
# si el .env no trae DELIVERY_VERDICT y trae USE_BATCH_API=true, la siembra
# arranca en «por correo». Sin USE_BATCH_API, de fabrica es «mostrador».
USE_BATCH_API = os.getenv('USE_BATCH_API', 'false').lower() == 'true' and not MOCK_AGENTS
if os.getenv('DELIVERY_VERDICT') is None and USE_BATCH_API:
    SETTING_DEFAULTS['delivery_verdict'] = 'batch'
