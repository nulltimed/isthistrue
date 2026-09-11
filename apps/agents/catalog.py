"""4.4-C · Catálogo de modelos y tareas. LISTA CERRADA.

Decisión de David (ronda 2, 2026-08-23): la lista la trae Fable en cada pase. NO
se descubren modelos solos — el catálogo de Anthropic no se puede consultar de
forma fiable con la clave del proyecto, y una lista que se rellena sola puede
quedarse callada sin que sea culpa de nadie. Lo que SÍ es automático es el vigía
nocturno (§tasks.check_models): comprueba a diario que los modelos configurados
siguen respondiendo.

PRECIOS: dólares por millón de tokens, consultados el 2026-08-23. Sirven para
ESTIMAR en el panel, no para facturar. Si Anthropic los cambia, actualízalos aquí
y solo aquí.

TIER: el escalón de calidad. Se usa para elegir suplente: cuando un modelo cae, el
sistema baja... no, SUBE (David: «suplente un escalón por encima en calidad, nunca
por debajo»). Un veredicto flojo publicado en una web de verificación hace más
daño que un vídeo que espera; un suplente bueno no hace daño ninguno.
"""

# 4.4-E (decision de David, 2026-08-23): "todo por Claude". Las fuentes ya no
# las trae SearXNG (bloqueado por los buscadores): las busca EL PROPIO MODELO con
# la herramienta de busqueda web de Anthropic — 10 $/1.000 busquedas + los tokens
# de los resultados. Se paga mas por busqueda, pero desaparecen los portazos:
# eres cliente identificado, no un robot anonimo.
#
# La columna `web` dice si el modelo ADMITE esa herramienta. Las tareas de
# WEB_TASKS la NECESITAN: elegir para ellas un modelo sin busqueda deja los
# veredictos ciegos, y el panel lo advierte en rojo (peticion literal de David:
# «Este modelo no permite búsqueda web»).
#
# 5.2-A (orden de David, 2026-09-06): la familia Qwen3 de Alibaba es el motor
# PRINCIPAL y Claude queda de RESPALDO por tarea (rueda «respaldo» del panel).
# Precios Qwen: portal internacional, consultados el 2026-09-06 en fuentes
# publicas (Alibaba no publica la tabla en la pagina fetchable); AJUSTAR aqui
# cuando la consola de David muestre la tarifa exacta. La columna `web` en los
# Qwen = enable_search de DashScope (fuentes en search_info; estrategia agent
# a 10 $/1.000 busquedas, como Anthropic).
#
# id                       nombre visible        tier  in$/M  out$/M  web
CATALOG = [
    # 5.26-A: precios REALES de la ficha de Alibaba (region Singapur, la de
    # dashscope-intl, leida el 2026-09-11): Flash 0,15/0,47; Plus 0,40/1,60
    # (hasta 256k de contexto). Antes: 0,11/0,80 y 0,39/2,34 (estimados), es
    # decir, el libro sobreestimaba la salida de Plus un 45 %.
    ('qwen3.8-flash',             'Qwen3.8 Flash',  1,  0.15,   0.47, True),
    # 5.6-D (reporte de David: «faltan modelos de Qwen»): la familia de texto
    # completa segun el listado REAL de /compatible-mode/v1/models de su cuenta
    # (2026-09-07). Precios estimados por escalon; ajustar con la consola.
    ('qwen3.7-flash',             'Qwen3.7 Flash',  1,  0.10,   0.68, True),
    ('qwen3.7-plus',              'Qwen3.7 Plus',   2,  0.40,   1.60, True),
    ('qwen3.7-max',               'Qwen3.7 Max',    3,  0.62,   3.10, True),
    # 5.10-F: precios REALES del extracto de Alibaba de septiembre (linea a
    # linea, 2026-09-07): input 2 $/M, output 6 $/M (cache-in 0,25 $/M). La
    # busqueda a 10 $/1K = el centimo que asumiamos (confirmado en factura).
    ('qwen3.8-max',               'Qwen3.8 Max',    4,  2.00,   6.00, True),
    # 5.5-D (pregunta de David hecha orden): los ojos de la familia — para
    # contrastar lo que se VE en pantalla con lo que se DICE. Precios estimados
    # de fuentes publicas; ajustar con la consola. Sin busqueda web.
    ('qwen3-vl-flash',            'Qwen3 VL Flash (ojos)', 1, 0.10, 0.40, False),
    ('qwen3-vl-plus',             'Qwen3 VL Plus (ojos)',  2, 0.40, 1.20, False),
    ('qwen3-vl-235b-a22b-instruct', 'Qwen3 VL 235B (ojos grandes)',
                                                    3,  0.70,   2.80, False),
    ('claude-haiku-4-5-20251001', 'Haiku 4.5',      1,   1.0,   5.0,  True),
    ('claude-sonnet-4-6',         'Sonnet 4.6',     2,   3.0,  15.0,  True),
    ('claude-opus-4-6',           'Opus 4.6',       3,   5.0,  25.0,  True),
    ('claude-opus-4-7',           'Opus 4.7',       3,   5.0,  25.0,  True),
    ('claude-opus-4-8',           'Opus 4.8',       4,   5.0,  25.0,  True),
    ('claude-fable-5',            'Fable 5',        5,  10.0,  50.0,  True),
]


def provider(model_id):
    return 'qwen' if model_id.startswith('qwen') else 'anthropic'

BY_ID = {m[0]: m for m in CATALOG}

# Tareas que NECESITAN buscar en la web para hacer su trabajo.
WEB_TASKS = ('verdict', 'deep')

# 4.4-G (B.2, encargo del operador): tareas que TIENEN via de lotes en el
# codigo. Las demas no la tienen porque no puede tenerla: el barrido y la
# datacion frenan la tuberia (nadie espera 24 h a ver su transcripcion) y la
# moderacion es en tiempo real (un mensaje del foro no puede esperar un dia a
# saber si se publica). Para esas, `delivery_for` devuelve SIEMPRE 'direct' y
# el panel lo dice en vez de ofrecer un selector que no manda. Un mando que
# muestra un estado distinto del real es peor que no tener mando.
BATCH_TASKS = ('verdict', 'deep')

# 10 $ por 1.000 busquedas (precio Anthropic, verificado 2026-08-23).
USD_PER_SEARCH = 0.01


def supports_web(model_id):
    m = BY_ID.get(model_id)
    return bool(m[5]) if m else False


def is_vision(model_id):
    """5.6-D: ¿es un modelo de OJOS (analisis de imagenes)? Los VL de Qwen no
    tienen acceso web, asi que viven en su propia categoria del panel."""
    return '-vl-' in model_id


def options_for(task):
    """5.6-D (orden de David): cada rueda del panel ofrece SOLO lo que puede
    hacer su trabajo — la categoria de imagenes («La vista») ofrece los VL y
    los Claude (que ven de serie); el resto de tareas, solo modelos de texto.
    Un selector que ofrece un modelo incapaz es un mando que miente."""
    if task == 'vision':
        return [m for m in CATALOG
                if is_vision(m[0]) or provider(m[0]) == 'anthropic']
    return [m for m in CATALOG if not is_vision(m[0])]


def label(model_id):
    return BY_ID[model_id][1] if model_id in BY_ID else model_id


def tier(model_id):
    return BY_ID[model_id][2] if model_id in BY_ID else 0


def prices(model_id):
    """(entrada, salida) en dólares por millón de tokens."""
    m = BY_ID.get(model_id)
    return (m[3], m[4]) if m else (3.0, 15.0)


def substitute(model_id, need_web=False):
    """El suplente: el más barato de los que SUPERAN su escalón de calidad.

    Nunca por debajo (decisión de David). Si el caído ya es el mejor que hay, se
    queda sin suplente: en ese caso la tarea espera, que es lo honesto.
    4.4-E: si la tarea necesita buscar, el suplente también tiene que saber.
    """
    # 5.2-A: el suplente es DEL MISMO proveedor (subir un escalon dentro de la
    # familia). El salto ENTRE proveedores es el respaldo por tarea
    # (fallback_for), que decide David en su panel.
    # 5.6-D: los ojos solo se sustituyen por ojos (y el texto por texto) — un
    # VL caido no puede suplirse con un modelo que no ve, ni al reves.
    arriba = [m for m in CATALOG if m[2] > tier(model_id)
              and provider(m[0]) == provider(model_id)
              and is_vision(m[0]) == is_vision(model_id)
              and (not need_web or m[5])]
    if not arriba:
        return ''
    return min(arriba, key=lambda m: m[3])[0]


# =========================================================================
# Las seis tareas
# =========================================================================
# clave        etiqueta                         por defecto            veces por vídeo
TASKS = [
    ('sweep',     'Barrido de afirmaciones', 'qwen3.8-flash', 'decenas'),
    ('classify',  'Clasificador factual/opinión (segunda opinión)', 'qwen3.7-plus',
                  'solo si la regla dice opinión'),
    ('dating',    'Fecha del suceso',        'qwen3.8-flash', 'una'),
    ('attribution', 'Pasada de sentido (quién dijo cada frase)', 'qwen3.8-flash',
                  'una por cada 120 frases'),
    ('verdict',   'Veredictos con fuentes',  'qwen3.7-plus',         'una por afirmación'),
    ('moderation', 'Moderación del foro',    'qwen3.8-flash', 'una por mensaje'),
    ('deep',      'Reanálisis profundo',     'qwen3.8-max',           'solo si se vota'),
    # 4.8-B (orden de David): la CRIBA FACTUAL de las frases de voces fantasma
    # (¿contiene información verificable?) tiene su propia rueda en el panel.
    ('innocuous', 'Criba factual de frases dudosas', 'qwen3.7-plus',
                  'solo si el separador inventa voces'),
    # 5.1-D (orden de David): al proponer una categoria nueva, Sonnet la
    # contrasta con las existentes para mantener la taxonomia ordenada.
    # 5.26-A (decision de David): rara y sencilla -> Flash.
    ('categories', 'Orden de categorías', 'qwen3.8-flash',
                   'solo al proponer una categoría nueva'),
    # 5.4-D (orden de David): el detector de temas sobre China. Por naturaleza
    # NO puede ser un modelo chino (el zorro no vigila el gallinero).
    ('china_guard', 'Detector de temas sobre China', 'claude-haiku-4-5-20251001',
                    'una por vídeo'),
    # 5.5-D: LA VISTA — ¿la imagen en pantalla sostiene lo que se dice?
    ('vision', 'La vista (imagen vs. audio)', 'qwen3-vl-plus',
               'solo claims con referencia visual'),
]
TASK_KEYS = [t[0] for t in TASKS]

# =========================================================================
# 4.5-C (orden de David, 2026-08-28): «elección de modelos según el caso» —
# el caso también incluye OÍR y SEPARAR VOCES. Estos motores corren en la GPU
# de Runpod (no son modelos de Claude); hasta hoy vivían solo en el .env,
# invisibles para el panel. Resolución: panel > .env > primera opción.
AUDIO_ENGINES = [
    ('whisper_gpu', 'Transcripción (whisper en la GPU)',
     [('large-v3', 'large-v3 — el mejor oído (recomendado)'),
      ('turbo', 'turbo — casi large-v3 y más rápido'),
      ('medium', 'medium — intermedio'),
      ('small', 'small — el de la era CPU')],
     'WHISPER_GPU_MODEL'),
    ('diarize_gpu', 'Separación de voces (pyannote en la GPU)',
     [('pyannote/speaker-diarization-community-1',
       'community-1 — distingue voces parecidas (recomendado)'),
      ('pyannote/speaker-diarization-3.1', '3.1 — el clásico')],
     'DIARIZE_GPU_MODEL'),
]
AUDIO_KEYS = [a[0] for a in AUDIO_ENGINES]


def audio_engine_for(key):
    """Modelo del motor de audio `key`. Panel > .env > primera opción."""
    from django.conf import settings as djsettings
    from apps.panel.models import SystemSetting
    for k, _titulo, opciones, env_attr in AUDIO_ENGINES:
        if k != key:
            continue
        validas = [o for o, _ in opciones]
        valor = SystemSetting.get_str(f'model_{key}', '')
        if valor in validas:
            return valor
        env_val = getattr(djsettings, env_attr, '')
        return env_val if env_val in validas else validas[0]
    raise KeyError(key)
TASK_DEFAULTS = {t[0]: t[2] for t in TASKS}

# 5.2-A: el RESPALDO por tarea — el Claude que entra cuando Qwen falla (error
# de API, clave vacia, JSON roto o negativa). Por defecto, el modelo que cada
# tarea tenia ANTES del cambio; David lo ajusta en su panel (model_fb_<tarea>).
FALLBACK_DEFAULTS = {
    'sweep': 'claude-haiku-4-5-20251001',
    'classify': 'claude-sonnet-4-6',
    'dating': 'claude-haiku-4-5-20251001',
    'attribution': 'claude-haiku-4-5-20251001',
    'verdict': 'claude-sonnet-4-6',
    'moderation': 'claude-haiku-4-5-20251001',
    'deep': 'claude-opus-4-8',
    'innocuous': 'claude-sonnet-4-6',
    'categories': 'claude-haiku-4-5-20251001',   # 5.26-A
    'china_guard': 'claude-haiku-4-5-20251001',
    'vision': 'claude-sonnet-4-6',   # Claude tambien ve
}


def fallback_for(task):
    """Respaldo Claude de la tarea. Panel > default. '' = sin respaldo."""
    from apps.panel.models import SystemSetting
    valor = SystemSetting.get_str(f'model_fb_{task}', '')
    if valor == 'none':
        return ''
    if valor in BY_ID and provider(valor) == 'anthropic':
        return valor
    return FALLBACK_DEFAULTS.get(task, 'claude-sonnet-4-6')


# Métodos de envío (la analogía del correo y el mostrador, §guía)
DELIVERY = [
    ('batch', 'Por correo (lotes): mitad de precio, hasta 24 h de espera'),
    ('direct', 'En el mostrador (directo, con memoria): minutos, y el texto '
               'repetido se paga una sola vez'),
]
DELIVERY_KEYS = [d[0] for d in DELIVERY]


def model_for(task):
    """Modelo configurado para una tarea. Panel > .env > default del catálogo."""
    from apps.panel.models import SystemSetting
    valor = SystemSetting.get_str(f'model_{task}', '')
    return valor if valor in BY_ID else TASK_DEFAULTS.get(task, 'claude-sonnet-4-6')


def delivery_for(task):
    """4.4-G: UNICA fuente de verdad del metodo de envio. Antes,
    `settings.USE_BATCH_API` mandaba por encima del panel en la rama de los
    veredictos y David llevaba dos dias viendo «En el mostrador» mientras el
    sistema usaba «Por correo». Hay candado (test) que prohibe leer
    USE_BATCH_API desde apps/."""
    if task not in BATCH_TASKS:
        return 'direct'
    # 5.2-A: la via de lotes es de la API de Anthropic; con un Qwen como
    # principal, el envio es SIEMPRE directo (el panel lo dice).
    if provider(model_for(task)) == 'qwen':
        return 'direct'
    from apps.panel.models import SystemSetting
    valor = SystemSetting.get_str(f'delivery_{task}', '')
    return valor if valor in DELIVERY_KEYS else 'direct'


def batchable(task):
    return task in BATCH_TASKS


# =========================================================================
# La calculadora del panel
# =========================================================================
# Medido en producción el 2026-08-23: 3,07 c/min reales. Una hora de vídeo son
# ~13.000 tokens de transcripción y ~80 afirmaciones factuales.
TOKENS_TRANSCRIPT_HOUR = 13000
CLAIMS_PER_HOUR = 80
TOKENS_OUT_PER_CLAIM = 350
USD_EUR = 0.865


def full_transcript_enabled_setting():
    """¿Está encendido el envío de la transcripción entera con cada veredicto?"""
    from apps.panel.models import SystemSetting
    return SystemSetting.get_int('full_transcript_verdict', 1) == 1


def cost_per_hour_eur(task=None, full_transcript=True):
    """Coste estimado de UNA HORA de vídeo con la configuración actual.

    No pretende ser exacto: pretende que David vea, antes de guardar, si acaba de
    multiplicar su factura por tres. Un número, no un sermón.
    """
    total = 0.0
    for clave, _lbl, _def, _veces in TASKS:
        if task and clave != task:
            continue
        modelo = model_for(clave)
        envio = delivery_for(clave)
        pin, pout = prices(modelo)
        if envio == 'batch':
            pin, pout = pin / 2, pout / 2      # el lote descuenta la mitad
        if clave == 'verdict':
            # 4.4-E: las busquedas del propio modelo — precio fijo por consulta
            # mas los tokens de los resultados (~1.500 por afirmacion).
            buscadas = web_searches_per_claim() * CLAIMS_PER_HOUR
            total += buscadas * USD_PER_SEARCH
            total += (1500 * CLAIMS_PER_HOUR / 1e6) * pin
            entrada = TOKENS_TRANSCRIPT_HOUR if full_transcript else 1200
            if envio == 'direct' and full_transcript:
                # Con memoria: el texto entero se paga UNA vez (1,25x) y el resto
                # de afirmaciones lo releen al 0,1x. Es la diferencia entre que
                # esta decisión sea asumible o no.
                coste_in = (entrada * 1.25 + entrada * 0.1 * (CLAIMS_PER_HOUR - 1))
            else:
                coste_in = entrada * CLAIMS_PER_HOUR
            total += (coste_in / 1e6) * pin
            total += (TOKENS_OUT_PER_CLAIM * CLAIMS_PER_HOUR / 1e6) * pout
        elif clave == 'sweep':
            total += (TOKENS_TRANSCRIPT_HOUR / 1e6) * pin + (4000 / 1e6) * pout
        elif clave == 'dating':
            total += (TOKENS_TRANSCRIPT_HOUR / 1e6) * pin + (500 / 1e6) * pout
        elif clave == 'attribution':
            # 4.4-I: la transcripcion entera etiquetada (x1,3 por los numeros y
            # etiquetas) y una lista corta de correcciones de vuelta.
            total += (TOKENS_TRANSCRIPT_HOUR * 1.3 / 1e6) * pin + (1500 / 1e6) * pout
        elif clave == 'classify':
            # 4.4-G: la segunda opinion SOLO se pide cuando la regla local dice
            # opinion. Se estima como una llamada por video (techo, no media).
            total += (TOKENS_TRANSCRIPT_HOUR / 1e6) * pin + (300 / 1e6) * pout
    return round(total * USD_EUR, 2)


def web_searches_per_claim():
    """Tope de busquedas que el modelo puede hacer por afirmacion (max_uses)."""
    from apps.panel.models import SystemSetting
    return max(1, SystemSetting.get_int('web_searches_per_claim', 3))


def models_for_post(task, post):
    """5.4-D: (principal, respaldo) de la tarea PARA ESTE VIDEO. Si el video
    involucra a China, el principal pasa a ser el Anthropic de la rueda de
    respaldo (sin caida posterior a Qwen): la censura no analiza."""
    principal, respaldo = model_for(task), fallback_for(task)
    if post is not None and getattr(post, 'china_related', None) and \
            provider(principal) == 'qwen':
        return (respaldo or FALLBACK_DEFAULTS.get(task, 'claude-sonnet-4-6')), ''
    return principal, respaldo


def warning_for(task):
    """El aviso de «te estás disparando en el pie», si procede."""
    # 4.4-E (peticion literal de David): la advertencia de los modelos ciegos.
    # 5.4-D: el zorro no vigila el gallinero.
    if task == 'china_guard' and provider(model_for(task)) == 'qwen':
        return ('Un modelo chino no puede detectar la censura china: elige un '
                'modelo de Anthropic para esta rueda.')
    if task in WEB_TASKS and not supports_web(model_for(task)):
        return ('Este modelo no permite búsqueda web, y esta tarea la necesita: '
                'los veredictos saldrían sin fuentes. Elige un modelo con búsqueda.')
    if task == 'verdict' and delivery_for('verdict') == 'batch':
        return ('Con la transcripción entera y envío por correo, el texto se paga '
                'una vez POR AFIRMACIÓN (unas 80 en una hora de vídeo) y además '
                'las respuestas tardan hasta 24 h. Es lo caro de una opción con lo '
                'lento de la otra.')
    if tier(model_for(task)) >= 4 and task in ('sweep', 'moderation'):
        return ('Esta tarea se ejecuta muchísimas veces. Un modelo de gama alta '
                'aquí multiplica la factura sin mejorar gran cosa.')
    return ''
