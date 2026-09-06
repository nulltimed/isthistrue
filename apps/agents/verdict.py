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


def _verificar_uno(c, post, fecha, tope, expediente, model, en_hilo=True):
    """5.21 (orden de David: «paraleliza siempre»): el trabajo CARO de una
    afirmacion — ojos + busquedas del verificador — aislado para correr en un
    hilo del pool. Devuelve (c, v, usado, hallazgo) o None si no toca.
    Higiene de hilo: apuntes con su post y conexion de BD cerrada al salir."""
    from django.db import close_old_connections
    from apps.analysis import costs as _costs
    from apps.agents import vision
    from apps.agents.catalog import models_for_post
    es_opinion = c.get('kind') == 'OPINION'
    if not es_opinion and c.get('kind') != 'FACTUAL':
        return None          # senales vacias o basura: fuera
    _costs.set_post(post)
    try:
        sistema = prompts.OPINION_VERDICT_SYSTEM if es_opinion \
            else prompts.VERDICT_SYSTEM
        payload = build_payload(c, fecha, tope)
        # 5.5-D/G: los ojos miran TODAS las frases; su hallazgo entra en el
        # expediente. Fail-soft.
        hallazgo = None
        try:
            seg_idx = c.get('segment_index')
            segs = list(post.transcript_segments.order_by('start_seconds', 'pk'))
            if seg_idx is not None and 0 <= seg_idx < len(segs):
                hallazgo = vision.mirar(post, c['text'],
                                        segs[seg_idx].start_seconds)
                if hallazgo:
                    payload += (f"\n\nCONTRASTE VISUAL (fotogramas alrededor "
                                f"del instante, {hallazgo['modelo']}): la "
                                f"pantalla {hallazgo['veredicto_visual'].upper()} "
                                f"lo dicho — {hallazgo['detalle'][:400]}")
        except Exception:
            pass
        _m, _fb = models_for_post('verdict', post)
        # 5.22-c: 1500 tokens truncaban el JSON con el contexto 2+2 y el
        # modelo exprimido (la MISMA leccion del clarificador) — mas aire.
        v, usado = client.call_search_json(model or _m,
                                           sistema, payload,
                                           max_tokens=2500, mock_payload=MOCK_VERDICT,
                                           cacheable=expediente, max_searches=tope,
                                           fallback=_fb)
        return (c, v, usado, hallazgo, es_opinion)
    finally:
        _costs.set_post(None)
        # Higiene SOLO en hilos del pool: en linea, cerrar aqui mataria la
        # conexion (y bajo TestCase, la transaccion) del llamante.
        if en_hilo:
            close_old_connections()


def parallel_workers():
    """5.21: cuantas afirmaciones a la vez (ajuste del panel, 4 de fabrica)."""
    from apps.panel.models import SystemSetting
    return max(1, min(12, SystemSetting.get_int('verdict_parallel', 4)))


def run(post, model=None):
    """5.21 (orden de David: «paraleliza siempre»): las llamadas CARAS de cada
    afirmacion (busquedas + ojos) corren EN PARALELO con un pool de hilos; las
    escrituras en la wiki (upsert con dedupe por embedding) van EN SERIE — dos
    hilos upsertando afirmaciones parecidas a la vez resucitarian los
    duplicados del 5.1-B. Historia previa de esta funcion: docs/06 §69-81."""
    from concurrent.futures import ThreadPoolExecutor
    from apps.wiki.services import upsert_claim
    from apps.agents import vision
    sw = sweep.run(post) if not post.transcript_segments.filter(
        signal__isnull=False).exclude(signal='').exists() else {
        'claims': _claims_from_segments(post)}
    fecha = post.event_date.isoformat() if post.event_date else None
    expediente = transcript_dossier(post) if full_transcript_enabled() else None
    from apps.agents.catalog import web_searches_per_claim
    tope = web_searches_per_claim()
    n = parallel_workers()
    if n <= 1:
        # En linea (sin hilos): mismo codigo, cero carreras. Es tambien el modo
        # de los tests — bajo TestCase, un hilo nuevo abre OTRA conexion que no
        # ve los datos de la transaccion del test.
        resultados = [_verificar_uno(c, post, fecha, tope, expediente,
                                     model, en_hilo=False)
                      for c in sw['claims']]
    else:
        with ThreadPoolExecutor(max_workers=n) as pool:
            resultados = list(pool.map(
                lambda c: _verificar_uno(c, post, fecha, tope, expediente, model),
                sw['claims']))
    for r in resultados:
        if r is None:
            continue
        c, v, usado, hallazgo, es_opinion = r
        if 'error' in v:
            continue
        v['model_used'] = usado
        v['kind'] = 'OPINION' if es_opinion else 'FACTUAL'
        tiene_fuentes = bool(v.get('sources'))
        # 4.4-B: SIN FUENTES NO HAY COLOR (GREY de opinion pura, legitimo 5.3-C).
        if not tiene_fuentes:
            if es_opinion and v.get('color') == 'GREY':
                pass
            else:
                v['color'] = 'UNDECIDED'
        claim_obj = upsert_claim(post, c, v, sources_ok=tiene_fuentes or
                                 (es_opinion and v.get('color') == 'GREY'))
        # 5.8: el fotograma que el claim involucra queda en la wiki.
        if hallazgo:
            try:
                vision.registrar(claim_obj, hallazgo)
            except Exception:
                pass


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
