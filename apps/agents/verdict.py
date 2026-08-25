"""Fase cara: Sonnet + busquedas adaptativas -> claims wiki con semaforo (README v2 §3)."""
from django.conf import settings
from apps.agents import client, prompts, search, sweep

# 4.4-E: el mock trae fuentes para que el circuito simulado se parezca al real.
MOCK_VERDICT = {
    'color': 'GREEN',
    'what_is_claimed': '[SIMULADO] La torre Eiffel mide 300 m y se terminó en 1889.',
    'what_evidence_says': '[SIMULADO] Las fuentes confirman 300 m (312 con antena original) y 1889.',
    'the_difference': '[SIMULADO] Sin diferencia sustancial.',
    'sources': [{'url': 'https://example.org/fuente-simulada', 'title': '[SIMULADO] Fuente'}],
    'sensitive': None,
}


def full_transcript_enabled():
    """4.4-C: ¿se manda la transcripción entera con cada veredicto?"""
    from apps.panel.models import SystemSetting
    return SystemSetting.get_int('full_transcript_verdict', 1) == 1


def transcript_dossier(post):
    """El expediente que ve el verificador: metadatos + transcripción con marcas
    de tiempo, tal como lo pidió David.

    Va SIEMPRE igual byte a byte dentro de un mismo post: si cambiara entre
    llamadas, la memoria no serviría de nada y se pagaría el texto entero cada vez.
    """
    lineas = [
        '=== FICHA DEL VÍDEO ===',
        f'Título: {post.title or "(sin título)"}',
        f'URL: {post.url}',
        f'Duración: {round((post.duration_seconds or 0) / 60)} min',
        f'Fecha del suceso: {post.event_date.isoformat() if post.event_date else "(no determinada)"}',
        f'Publicado en la plataforma: {post.created_at.date().isoformat() if post.created_at else "?"}',
        '',
        '=== TRANSCRIPCIÓN COMPLETA (marca de tiempo · hablante · frase) ===',
    ]
    confirmadas = dict(post.name_proposals.filter(confirmed=True)
                       .values_list('speaker_label', 'candidate_name'))
    for s in post.transcript_segments.order_by('start_seconds', 'pk'):
        t = int(s.start_seconds or 0)
        quien = confirmadas.get(s.speaker_label) or s.speaker_label or '¿?'
        lineas.append(f'[{t // 60:02d}:{t % 60:02d}] {quien}: {s.text}')
    return '\n'.join(lineas)


def build_payload(c, fecha, tope):
    """4.4-G (B.1): el texto que ve el verificador, UNICO para la via directa y
    la via por lotes. Hasta hoy cada via redactaba el suyo; si divergen, el color
    de una afirmacion depende del camino por el que llego (leccion 4.3-A.7).
    Hay test que vigila que batch.py llame a esta funcion."""
    return (f"CLAIM: {c['text']}\n\n"
            + (f"FECHA DEL SUCESO: {fecha}\n\n" if fecha else '')
            + f"CONTEXTO (frases contiguas del mismo hablante; NO se verifican):\n"
              f"{c.get('context') or c['text']}\n\n"
              f"BUSCA TU MISMO LAS FUENTES (máx. {tope} búsquedas): primero "
              f"organismos oficiales (INE, Eurostat, BOE, bancos centrales, "
              f"OMS...), prensa solo como apoyo. Lista en \"sources\" las URLs "
              f"reales que uses. Si no encuentras nada útil: UNDECIDED.")


def run(post, model=None):
    """4.4-B: dos fallos de raiz arreglados aqui.

    1) LAS OPINIONES SE ESTABAN PAGANDO. La linea `if kind != FACTUAL: pass` no
       hacia nada — literalmente un `pass` vacio — asi que el bucle seguia y
       gastaba una verificacion completa (busquedas + Sonnet) en frases como
       «Cataluña es una nacion», que por definicion no se verifican. En los datos
       de produccion del 2026-08-23 sobraban veredictos en los tres videos: 17
       frases factuales y 32 veredictos en el post 4. Cerca de un tercio del gasto
       de la fase cara se iba en esto, y encima llenaba la wiki de grises.

    2) SIN FUENTES SE PINTABA IGUAL. Si la busqueda volvia vacia se llamaba al
       modelo caro de todas formas, y el modelo — honradamente — decia que no
       tenia datos y salia gris. Pagar Sonnet para que diga que no sabe nada.
       Ahora, sin fuentes no se llama: la afirmacion queda UNDECIDED y el lector
       puede pedir el reanalisis profundo.
    """
    from apps.wiki.services import upsert_claim
    sw = sweep.run(post) if not post.transcript_segments.filter(
        signal__isnull=False).exclude(signal='').exists() else {
        'claims': _claims_from_segments(post)}
    fecha = post.event_date.isoformat() if post.event_date else None
    # 4.4-C (decisión de David): al verificador se le pasa la TRANSCRIPCIÓN ENTERA
    # con sus marcas de tiempo, los metadatos del vídeo, y la frase con su
    # contexto. Sin el debate completo, «estos dos hombres» no se entiende.
    # Va como bloque CACHEABLE: se paga una vez y las 80 afirmaciones lo releen a
    # una décima parte. Sin eso, esta decisión multiplicaría la factura por 2,6.
    expediente = transcript_dossier(post) if full_transcript_enabled() else None
    from apps.agents.catalog import model_for, web_searches_per_claim
    tope = web_searches_per_claim()
    for c in sw['claims']:
        if c.get('kind') != 'FACTUAL':
            continue          # una opinion no se verifica: ni se busca, ni se paga
        # 4.4-E (decision de David): "todo por Claude". Ya no hay documentalista
        # aparte: EL MODELO busca sus fuentes con la herramienta web de Anthropic
        # (10 $/1.000 + tokens), con las fuentes oficiales por delante y el tope
        # del panel. SearXNG queda fuera del circuito de veredictos: los
        # buscadores le cerraban la puerta al servidor y el semaforo se quedaba
        # en 🔍 por falta de papeles.
        payload = build_payload(c, fecha, tope)
        v, usado = client.call_search_json(model or model_for('verdict'),
                                           prompts.VERDICT_SYSTEM, payload,
                                           max_tokens=1500, mock_payload=MOCK_VERDICT,
                                           cacheable=expediente, max_searches=tope)
        if 'error' not in v:
            v['model_used'] = usado
            tiene_fuentes = bool(v.get('sources'))
            # 4.4-B (decision de David): SIN FUENTES NO HAY COLOR. Hasta el 4.4-E la
            # garantia era estructural — si la busqueda volvia vacia no se llamaba al
            # modelo. Ahora que el modelo busca solo, la unica salvaguarda que quedaba
            # era pedirselo en el prompt ("si no encuentras nada util: UNDECIDED"), y
            # un ruego no es un candado: si contesta GREEN sin una sola URL, ese verde
            # se publicaba. Se vuelve a imponer aqui. Lo cazo el test del 4.4-B.
            if not tiene_fuentes:
                v['color'] = 'UNDECIDED'
            upsert_claim(post, c, v, sources_ok=tiene_fuentes)


def context_for(segments, i, before, after):
    """4.3-A.7 (David): la ANTERIOR, la PRESENTE y la SIGUIENTE frase DEL MISMO
    HABLANTE. "Del mismo hablante" no es "la de al lado": si otro interrumpe, se
    salta y se sigue buscando hacia atras/adelante. Sin diarizacion (etiqueta
    vacia) se usan las vecinas inmediatas, que es lo unico que hay."""
    spk = segments[i].speaker_label
    prev, nxt = [], []
    j = i - 1
    while j >= 0 and len(prev) < before:
        if not spk or segments[j].speaker_label == spk:
            prev.append(segments[j])
        j -= 1
    j = i + 1
    while j < len(segments) and len(nxt) < after:
        if not spk or segments[j].speaker_label == spk:
            nxt.append(segments[j])
        j += 1
    lineas = [f'(antes) {s.text}' for s in reversed(prev)]
    lineas.append(f'(ESTA ES LA FRASE VERIFICADA) {segments[i].text}')
    lineas += [f'(despues) {s.text}' for s in nxt]
    return '\n'.join(lineas)


def _claims_from_segments(post):
    """4.3-A.7: el semaforo se decide con la frase EN CONTEXTO, no suelta. Cuantas
    frases entran a cada lado son ajustes vivos (panel) sembrados desde el .env."""
    from apps.panel.models import SystemSetting
    before = max(0, SystemSetting.get_int('verdict_context_before', 1))
    after = max(0, SystemSetting.get_int('verdict_context_after', 1))
    # Orden explicito: los indices que salen de aqui identifican la frase (leccion O1).
    segments = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
    out = []
    for i, s in enumerate(segments):
        if s.signal in ('FACTUAL_UNVERIFIED', 'CONTRADICTS_MODEL'):
            kind, ambiguous = 'FACTUAL', s.signal == 'CONTRADICTS_MODEL'
        elif s.signal == 'OPINION':
            kind, ambiguous = 'OPINION', False
        else:
            continue
        out.append({'segment_index': i, 'text': s.text, 'kind': kind,
                    'ambiguous': ambiguous,
                    'context': context_for(segments, i, before, after)})
    return out
