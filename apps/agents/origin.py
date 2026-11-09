"""6.1 (orden de David, 2026-11-06): el RASTREADOR DE ORIGEN.

«En el análisis quiero que se busque el origen directo de la afirmación. Es
decir, si en un vídeo una persona dice algo, ese algo se buscará hasta su
origen, y ello se demostrará en la wiki de una manera visual y sencilla.»

Persigue la cadena de difusion HACIA ATRAS (video <- red social <- prensa <-
nota de prensa <- estudio/declaracion oficial) y la guarda en
Claim.origin_chain como eslabones {kind, date, title, url, note}. Honestidad
estructural: se muestra el «origen mas antiguo DOCUMENTADO», jamas se finge
haber llegado al origen absoluto.

Cuando corre: automatico tras los veredictos para los claims ROJOS y AMBAR
(ajuste `origin_trace_auto`, 1 de fabrica) — es donde importa saber quien
torcio que. Para verdes/grises, bajo demanda gastando creditos
(`origin_trace_credits`). Usa la rueda 'deep' del panel (como el
clarificador): no anade rueda nueva al panel de David.
"""
import logging

from apps.agents import client

logger = logging.getLogger('agents.origin')

KINDS = ('study', 'official', 'press', 'social', 'video', 'other')

ORIGIN_SYSTEM = (
    'Eres el rastreador de origen de un verificador de hechos. Dada una '
    'afirmación oída en un vídeo, tu misión NO es juzgarla (ya está juzgada): '
    'es reconstruir su CADENA DE DIFUSIÓN hacia atrás en el tiempo hasta el '
    'origen más antiguo que puedas DOCUMENTAR con una URL real: el estudio, '
    'la declaración oficial, la nota de prensa o la publicación donde nació. '
    'Busca en español y en inglés. Cada eslabón necesita URL real y fecha (o '
    '"aprox."). Si un eslabón distorsionó el mensaje, dilo en su "note" '
    'citando en qué cambió. NUNCA inventes URLs ni fechas: menos eslabones '
    'verdaderos valen más que una cadena larga dudosa.\n'
    'Responde ÚNICAMENTE con un objeto JSON: {"chain": [{"kind": '
    '"study|official|press|social|video|other", "date": "YYYY-MM-DD o aprox.", '
    '"title": "...", "url": "https://...", "note": "qué aportó o torció este '
    'eslabón (<=300 caracteres)", "twisted": true SOLO si en ESTE eslabón el '
    'mensaje cambió de significado respecto al anterior (omitir en el resto)}], '
    '"summary": "una frase: dónde nació y '
    'dónde se torció (<=300 caracteres)"}. La cadena va del ORIGEN (primero) '
    'al vídeo analizado (último, kind "video", url del post). Máximo 6 '
    'eslabones. Si no encuentras nada anterior al vídeo: {"chain": [], '
    '"summary": "sin origen documentado anterior al vídeo"}.')

# Mock para la suite y el espejo (MOCK_AGENTS=true): cadena fija verificable.
MOCK_ORIGIN = {
    'chain': [
        {'kind': 'study', 'date': '2013-02-25', 'title': 'Estudio PREDIMED',
         'url': 'https://example.org/predimed', 'note': 'El estudio real: reduce riesgo, no cura.'},
        {'kind': 'press', 'date': '2013-03-01', 'title': 'Titular de prensa',
         'url': 'https://example.org/prensa', 'twisted': True,
         'note': 'Aquí «reduce» se convirtió en «cura».'},
    ],
    'summary': 'Nació en un estudio real y se torció en un titular.',
}

# Fusible por claim (el gasto REAL lo apunta el cliente en el libro igualmente).
COST_PER_CLAIM_EUR = 0.04


def _tope():
    from apps.agents.catalog import web_searches_per_claim
    return max(5, web_searches_per_claim())


def _payload(claim, ap):
    post = ap.segment.post
    fecha = post.event_date.isoformat() if post.event_date else 'desconocida'
    return (f'AFIRMACIÓN (ya verificada, color {claim.color}): '
            f'«{claim.text_original}»\n'
            f'DÓNDE SE OYÓ: {post.title or post.url} (fecha del suceso: {fecha}; '
            f'URL del vídeo: {post.url})\n'
            f'LO QUE DICE LA EVIDENCIA: {claim.what_evidence_says[:600]}\n\n'
            f'Reconstruye la cadena de difusión hacia atrás. Tienes hasta '
            f'{_tope()} búsquedas.')


def _sane(v):
    """Valida el contrato: lista de eslabones con kind conocido y url http."""
    chain = v.get('chain')
    if not isinstance(chain, list):
        return None
    limpio = []
    for e in chain[:6]:
        if not isinstance(e, dict):
            continue
        url = str(e.get('url', ''))
        if not url.startswith('http'):
            continue
        limpio.append({
            'kind': e.get('kind') if e.get('kind') in KINDS else 'other',
            'date': str(e.get('date', ''))[:20],
            'title': str(e.get('title', ''))[:200],
            'url': url[:500],
            'note': str(e.get('note', ''))[:300],
            # 6.1-c (David, 2026-11-06): el eslabón donde el mensaje cambió de
            # significado se marca y la ficha lo resalta en ámbar.
            'twisted': bool(e.get('twisted')),
        })
    return limpio


def trace_claim(claim):
    """Una pasada de rastreo. Devuelve True si quedo cadena guardada."""
    from apps.agents.catalog import models_for_post
    ap = claim.appearances.select_related('segment__post').first()
    if not ap:
        return False
    post = ap.segment.post
    _m, _fb = models_for_post('deep', post)
    # 6.5 (tanda real del 2026-11-08: 16 de 31 fallaron con json_parse): seis
    # eslabones con notas de 300 caracteres NO caben en 3000 tokens y el JSON
    # llegaba truncado — la misma leccion del clarificador. Mas aire, y el
    # cliente ya repara los truncados que queden (_salvage_json).
    v, usado = client.call_search_json(
        _m, ORIGIN_SYSTEM, _payload(claim, ap), max_tokens=5000,
        mock_payload=MOCK_ORIGIN, max_searches=_tope(), fallback=_fb)
    if 'error' in v:
        logger.warning('Rastreador: el modelo fallo con el claim %s (%s)',
                       claim.pk, v.get('error'))
        claim.origin_status = 'FAILED'
        claim.save(update_fields=['origin_status'])
        return False
    chain = _sane(v)
    if chain is None:
        claim.origin_status = 'FAILED'
        claim.save(update_fields=['origin_status'])
        return False
    claim.origin_chain = chain
    claim.origin_status = 'DONE'
    claim.save(update_fields=['origin_chain', 'origin_status'])
    logger.info('Rastreo de origen del claim %s: %d eslabon(es) (%s)',
                claim.pk, len(chain), usado)
    return True


def run_pending(post, limit=15):
    """Tras los veredictos: rastrear el origen de los ROJOS y AMBAR del post.
    Fail-soft y con el fusible del presupuesto por claim."""
    from apps.panel.models import SystemSetting
    from apps.wiki.models import Claim
    from apps.analysis.models import DailyBudget
    if SystemSetting.get_int('origin_trace_auto', 1) <= 0:
        return 0
    claims = (Claim.objects.filter(appearances__segment__post=post,
                                   color__in=('RED', 'AMBER'), origin_status='')
              .distinct()[:limit])
    hechos = 0
    for c in claims:
        if not DailyBudget.try_spend(COST_PER_CLAIM_EUR):
            logger.info('Rastreo de origen: sin presupuesto hoy; quedan claims sin rastrear.')
            break
        try:
            hechos += 1 if trace_claim(c) else 0
        except Exception:
            logger.warning('El rastreador fallo en el claim %s', c.pk, exc_info=True)
    return hechos
