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
# id                       nombre visible        tier  in$/M  out$/M  web
CATALOG = [
    ('claude-haiku-4-5-20251001', 'Haiku 4.5',      1,   1.0,   5.0,  True),
    ('claude-sonnet-4-6',         'Sonnet 4.6',     2,   3.0,  15.0,  True),
    ('claude-opus-4-6',           'Opus 4.6',       3,   5.0,  25.0,  True),
    ('claude-opus-4-7',           'Opus 4.7',       3,   5.0,  25.0,  True),
    ('claude-opus-4-8',           'Opus 4.8',       4,   5.0,  25.0,  True),
    ('claude-fable-5',            'Fable 5',        5,  10.0,  50.0,  True),
]

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
    arriba = [m for m in CATALOG if m[2] > tier(model_id)
              and (not need_web or m[5])]
    if not arriba:
        return ''
    return min(arriba, key=lambda m: m[3])[0]


# =========================================================================
# Las seis tareas
# =========================================================================
# clave        etiqueta                         por defecto            veces por vídeo
TASKS = [
    ('sweep',     'Barrido de afirmaciones', 'claude-haiku-4-5-20251001', 'decenas'),
    ('classify',  'Clasificador factual/opinión (segunda opinión)', 'claude-sonnet-4-6',
                  'solo si la regla dice opinión'),
    ('dating',    'Fecha del suceso',        'claude-haiku-4-5-20251001', 'una'),
    ('attribution', 'Pasada de sentido (quién dijo cada frase)', 'claude-haiku-4-5-20251001',
                  'una por cada 120 frases'),
    ('verdict',   'Veredictos con fuentes',  'claude-sonnet-4-6',         'una por afirmación'),
    ('moderation', 'Moderación del foro',    'claude-haiku-4-5-20251001', 'una por mensaje'),
    ('deep',      'Reanálisis profundo',     'claude-opus-4-8',           'solo si se vota'),
]
TASK_KEYS = [t[0] for t in TASKS]
TASK_DEFAULTS = {t[0]: t[2] for t in TASKS}

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


def warning_for(task):
    """El aviso de «te estás disparando en el pie», si procede."""
    # 4.4-E (peticion literal de David): la advertencia de los modelos ciegos.
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
