"""4.4-I · La pasada de sentido: quien dijo cada frase, leyendo la conversacion.

Contexto (docs/06 §45): con las dos voces del post 5, pyannote 3.1 agrupaba
«habla limpia» contra «habla solapada», no Neil contra Chuck, se le dijera lo
que se le dijera. Los post-procesos acusticos (suelo, fantasma, backchannels)
se quedan; esta pasada corrige lo que el audio no da: por TEXTO, con el modelo
de la tarea «attribution» del panel (Haiku de fabrica). Solo texto: centimos.

Decision de David (2026-08-26): los cambios seguros se aplican; las dudas se
MARCAN como «atribucion incierta» y la comunidad las resuelve en «¿Quien
habla?». Mientras tanto no cuentan para la puerta del 65 % ni se cuelgan de
ninguna persona en la wiki.
"""
import logging

from apps.agents import client, prompts
from apps.agents.catalog import model_for

logger = logging.getLogger('agents.attribution')

CHUNK = 120          # frases por llamada (con 10 de contexto previo)
OVERLAP = 10
MOCK_ATTRIBUTION = {'changes': []}


def _lista(segments, inicio, fin):
    lineas = []
    for i in range(inicio, fin):
        s = segments[i]
        lineas.append(f"{i} [{s.speaker_label or '?'}] ({s.start_seconds:.0f}s) {s.text}")
    return '\n'.join(lineas)


def run(post):
    """Devuelve {'relabeled': n, 'split': n, 'uncertain': n}. No falla nunca hacia
    arriba: cualquier error deja la transcripcion como estaba, con WARNING."""
    from apps.panel.models import SystemSetting
    vacio = {'relabeled': 0, 'split': 0, 'uncertain': 0}
    if SystemSetting.get_int('attribution_sense_pass', 1) <= 0:
        return vacio
    segments = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
    etiquetas = sorted({s.speaker_label for s in segments if s.speaker_label})
    if len(etiquetas) < 2:
        return vacio                    # un monologo no se discute
    cambios = []
    inicio = 0
    while inicio < len(segments):
        fin = min(len(segments), inicio + CHUNK)
        desde = max(0, inicio - OVERLAP)
        payload = (f"VOCES: {', '.join(etiquetas)}\n"
                   f"FRASES (las {inicio - desde} primeras son contexto; corrige solo de la {inicio} a la {fin - 1}):\n"
                   + _lista(segments, desde, fin))
        try:
            datos = client.call_json(model_for('attribution'), prompts.ATTRIBUTION_SYSTEM,
                                     payload, max_tokens=1500, mock_payload=MOCK_ATTRIBUTION)
        except Exception as exc:
            logger.warning('Pasada de sentido fallida en el post %s: %r', post.pk, exc)
            return vacio
        if 'error' in datos:
            # 4.8-A: un JSON invalido puntual no puede tumbar la pasada — se
            # reintenta UNA vez (el modelo muestrea distinto).
            datos = client.call_json(model_for('attribution'),
                                     prompts.ATTRIBUTION_SYSTEM, payload,
                                     max_tokens=1500,
                                     mock_payload=MOCK_ATTRIBUTION)
        if 'error' in datos:
            logger.warning('Pasada de sentido fallida en el post %s: %s', post.pk, datos.get('error'))
            return vacio
        for c in datos.get('changes') or []:
            try:
                i = int(c.get('i'))
            except (TypeError, ValueError):
                continue
            if inicio <= i < fin:
                cambios.append(c)
        inicio = fin
    return apply_changes(segments, etiquetas, cambios, post)


def intro_rewrite(post):
    """4.6-B: el ARRANQUE FUNDIDO se reescribe entero. Medido contra el oro de
    David: el oido funde los primeros ~45 s (los hablantes se pisan) y ni el
    cruce ni las correcciones sueltas pueden partir lo que el oido no marco.
    Lo que SI funciona es lo que hizo David a mano: LEER el dialogo y
    reescribirlo. Se le pide a Sonnet exactamente eso, con un candado duro:
    si las palabras reconstruidas no son EXACTAMENTE las originales en el
    mismo orden, se descarta entero (fail-closed, leccion 4.4-E)."""
    import re
    from django.db import transaction
    from apps.panel.models import SystemSetting
    tope = SystemSetting.get_int('intro_rewrite_seconds', 120)
    if tope <= 0:
        return {'rewritten': 0}
    segments = list(post.transcript_segments.filter(start_seconds__lt=tope)
                    .order_by('start_seconds', 'pk'))
    etiquetas = sorted({s.speaker_label for s in post.transcript_segments.all()
                        if s.speaker_label})
    # Con MENOS de dos voces en el post no hay nada que repartir; pero UNA sola
    # frase en la ventana si cuenta: el arranque fundido en un unico bloque es
    # exactamente el sintoma clasico (lo cazo el test del 4.6-B).
    if len(etiquetas) < 2 or not segments:
        return {'rewritten': 0}
    # 4.6-D: el guion entra SIN etiquetas — las del oido estan fundidas en el
    # arranque y anclaban al modelo a conservarlas. David separo este dialogo
    # sin mas herramienta que leerlo; que el modelo haga lo mismo.
    guion = '\n'.join(s.text for s in segments)
    # 4.6-C: el ancla de paridad — la cuota GLOBAL de cada voz en el video
    from collections import defaultdict
    cuota = defaultdict(float)
    for s2 in post.transcript_segments.all():
        if s2.speaker_label:
            cuota[s2.speaker_label] += s2.end_seconds - s2.start_seconds
    total = sum(cuota.values()) or 1
    reparto = ' · '.join(f'{k}: {v / total * 100:.0f}% del video'
                         for k, v in sorted(cuota.items(), key=lambda x: -x[1]))
    # 4.6-F: el ANCLA ACUSTICA — el oido falla en las interjecciones cortas,
    # pero un turno LARGO y continuo es justo donde es de fiar. Se cita al
    # modelo la frase mas larga del arranque con su voz medida: con un punto
    # fijo, el razonamiento relativo (nombres, ecos, turnos) encadena la
    # paridad correcta hacia atras. Sin esto, los primeros segundos son
    # textualmente INDECIDIBLES y la votacion los cruzaba en firme.
    ancla = max(segments, key=lambda x: x.end_seconds - x.start_seconds)
    cita = ' '.join(ancla.text.split()[:12])
    payload = (f"VOCES: {', '.join(etiquetas)}\n"
               f"CUOTA GLOBAL (quien explica es el dominante): {reparto}\n"
               f"ANCLA ACUSTICA FIABLE (medida en un turno largo y continuo): "
               f"las palabras «{cita}...» son de {ancla.speaker_label}. "
               f"Encadena el resto de la conversacion a partir de este hecho.\n\n"
               f"ARRANQUE:\n{guion}")
    def toks(t):
        return re.findall(r"[\w']+", t.lower())
    orig = [w for s in segments for w in toks(s.text)]

    # 4.6-E: TRES reescrituras y voto por mayoria palabra a palabra. Las
    # iteraciones 4.6-B/C/D oscilaban 55-61%: cada muestra unica tiraba los
    # dados y volteaba lineas distintas. Como el candado garantiza palabras
    # identicas, cada palabra puede recibir un voto de voz por muestra.
    muestras = []
    for _ in range(3):
        try:
            datos = client.call_json(model_for('attribution'),
                                     prompts.INTRO_REWRITE_SYSTEM, payload,
                                     max_tokens=4000,
                                     mock_payload={'utterances': []})
        except Exception as exc:
            logger.warning('Reescritura de arranque: muestra fallida en el '
                           'post %s: %r', post.pk, exc)
            continue
        utt = [u for u in (datos.get('utterances') or [])
               if str(u.get('text', '')).strip()]
        if not utt:
            continue
        nuevo_txt = [w for u in utt for w in toks(str(u['text']))]
        if nuevo_txt != orig:
            logger.warning('Reescritura de arranque: muestra descartada en el '
                           'post %s (texto no coincide: %d vs %d palabras)',
                           post.pk, len(orig), len(nuevo_txt))
            continue
        if any(u.get('speaker') not in etiquetas
               and u.get('tipo') != 'reaccion' for u in utt):
            logger.warning('Reescritura de arranque: muestra descartada en el '
                           'post %s (etiqueta desconocida)', post.pk)
            continue
        muestras.append(utt)
    if not muestras:
        return {'rewritten': 0}

    from collections import Counter
    def voz_por_palabra(utt):
        # 4.7-A: una reaccion vota 'R' — si la mayoria dice R, la palabra se
        # OMITE del transcript (regla de David: la web analiza afirmaciones;
        # las reacciones que cortan al orador se quitan de en medio).
        out = []
        for u in utt:
            voto = 'R' if u.get('tipo') == 'reaccion' else u['speaker']
            out.extend([voto] * len(toks(str(u['text']))))
        return out
    votos_muestra = [voz_por_palabra(m) for m in muestras]
    final = []
    for i in range(len(orig)):
        c = Counter(v[i] for v in votos_muestra)
        final.append(c.most_common(1)[0][0])

    # reconstruir las intervenciones sobre el TEXTO CRUDO (puntuacion intacta):
    # cada palabra cruda hereda el voto de su primer token normalizado; una
    # "palabra" sin tokens (solo signos) se pega a la anterior.
    crudo = ' '.join(s.text for s in segments).split()
    utt = []
    idx = 0
    for w in crudo:
        k = len(toks(w))
        voz = final[idx] if k else (utt[-1]['speaker'] if utt else final[0])
        if utt and utt[-1]['speaker'] == voz:
            utt[-1]['text'] += ' ' + w
            utt[-1]['_fin'] = idx + max(k, 1) - 1 if k else utt[-1]['_fin']
        else:
            utt.append({'speaker': voz, 'text': w, '_ini': idx,
                        '_fin': idx + max(k, 1) - 1})
        idx += k

    # reloj: cada palabra original hereda un tramo proporcional de su frase
    tiempos = []
    for s in segments:
        ws = toks(s.text)
        n = len(ws) or 1
        dur = s.end_seconds - s.start_seconds
        for k in range(len(ws)):
            tiempos.append((s.start_seconds + dur * k / n,
                            s.start_seconds + dur * (k + 1) / n))
    omitidas = sum(1 for u in utt if u['speaker'] == 'R')
    utt = [u for u in utt if u['speaker'] != 'R']
    from apps.analysis.models import TranscriptSegment
    nuevos = []
    for u in utt:
        ini = tiempos[min(u['_ini'], len(tiempos) - 1)][0]
        fin = tiempos[min(u['_fin'], len(tiempos) - 1)][1]
        nuevos.append(TranscriptSegment(
            post=post, start_seconds=round(ini, 3), end_seconds=round(fin, 3),
            text=str(u['text']).strip(), speaker_label=u['speaker'],
            attribution_note=_nota('arranque reescrito por la pasada de sentido')))
    with transaction.atomic():
        post.transcript_segments.filter(
            pk__in=[s.pk for s in segments]).delete()
        TranscriptSegment.objects.bulk_create(nuevos)
    logger.info('Post %s: arranque reescrito por mayoria de %d — %d frases → '
                '%d intervenciones (+%d reacciones omitidas)',
                post.pk, len(muestras), len(segments), len(nuevos), omitidas)
    return {'rewritten': len(nuevos), 'omitted': omitidas}


def adjudicate_minor_voices(post):
    """4.8-B (politica de David, 2026-08-30): con las frases de voces FANTASMA
    no se adivina el hablante — o es cientifico o no se afirma. Sonnet decide
    SOLO si la frase contiene informacion factual: si NO, se elimina y se
    aprende para siempre (InnocuousPhrase); si SI, se marca atribucion
    INCIERTA y la comunidad la resuelve — excluida de la verificacion y de la
    wiki hasta entonces. Fail-soft integral."""
    import re
    from collections import defaultdict
    from apps.analysis.models import InnocuousPhrase

    def norm(t):
        return ' '.join(re.findall(r"[\w']+", t.lower()))[:200]

    segs = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
    dur = defaultdict(float)
    for s2 in segs:
        if s2.speaker_label:
            dur[s2.speaker_label] += s2.end_seconds - s2.start_seconds
    if len(dur) <= 2:
        return {'adjudicated': 0}
    orden = sorted(dur, key=lambda k: -dur[k])
    menores = orden[2:]
    total = sum(dur.values()) or 1
    if sum(dur[m] for m in menores) / total > 0.15:
        return {'adjudicated': 0}   # demasiada voz "menor": quiza es real
    fantasmas = [s2 for s2 in segs if s2.speaker_label in menores]
    if not fantasmas:
        return {'adjudicated': 0}

    # 1º: la base de frases inocuas YA aprendidas — gratis y sin adivinanza
    borradas = 0
    pendientes = []
    for s2 in fantasmas:
        n = norm(s2.text)
        fila = InnocuousPhrase.objects.filter(text_norm=n).first()
        if fila:
            fila.times_seen += 1
            fila.save(update_fields=['times_seen'])
            s2.delete()
            borradas += 1
        else:
            pendientes.append(s2)

    # 2º: las nuevas, a Sonnet — SOLO la pregunta factual
    if pendientes:
        bloques = [f'FRASE {n}: «{s2.text[:150]}»'
                   for n, s2 in enumerate(pendientes)]
        try:
            datos = client.call_json(model_for('attribution'),
                                     prompts.ADJUDICATE_SYSTEM,
                                     '\n'.join(bloques), max_tokens=1500,
                                     mock_payload={'decisiones': []})
        except Exception as exc:
            logger.warning('Criba de fantasmas fallida en el post %s: %r',
                           post.pk, exc)
            datos = {'decisiones': []}
        for d in (datos.get('decisiones') or []):
            try:
                s2 = pendientes[int(d.get('n'))]
            except (TypeError, ValueError, IndexError):
                continue
            if d.get('factual') is False:
                InnocuousPhrase.objects.get_or_create(
                    text_norm=norm(s2.text),
                    defaults={'first_post': post})
                s2.delete()
                borradas += 1
            else:
                s2.attribution_uncertain = True
                s2.attribution_note = _nota(
                    'voz dudosa del separador; contiene información: '
                    'la comunidad decide de quién es')
                s2.save(update_fields=['attribution_uncertain',
                                       'attribution_note'])
    inciertas = len(fantasmas) - borradas
    logger.info('Post %s: criba de fantasmas — %d inocuas eliminadas '
                '(la base aprende), %d con información → INCIERTAS para la '
                'comunidad', post.pk, borradas, inciertas)
    return {'adjudicated': len(fantasmas), 'deleted': borradas,
            'uncertain': inciertas}


REACTION_LEXICON = {
    'okay', 'ok', 'yeah', 'yes', 'right', 'wow', 'whoa', 'nice', 'great',
    'sure', 'exactly', 'totally', 'absolutely', 'damn', 'oh', 'oh my',
    'oh my gosh', 'oh my god', 'get out', 'no way', 'oh wow', 'mm-hmm',
    'uh-huh', 'oh look at that', 'i love it', 'look at that', 'there you go',
    'come on', 'oh boy', 'gotcha', 'huh',
}


def drop_reactions(post):
    """4.7-A (regla de David, 2026-08-30): la web analiza AFIRMACIONES; una
    reaccion suelta del oyente no contiene ninguna y solo mete ruido. Se
    OMITEN las frases-reaccion independientes: lexico, o eco literal de la
    frase vecina (hasta 8 palabras). Configurable: reaction_filter=0 apaga."""
    import re
    from apps.panel.models import SystemSetting
    if SystemSetting.get_int('reaction_filter', 1) <= 0:
        return 0
    def norm(t):
        return ' '.join(re.findall(r"[\w']+", t.lower()))
    segs = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
    fuera = []
    for i, s2 in enumerate(segs):
        n = norm(s2.text)
        palabras = n.split()
        if not palabras or len(palabras) > 8:
            continue
        es_lexico = n in REACTION_LEXICON or all(
            w in REACTION_LEXICON for w in palabras)
        if not es_lexico:
            # 4.8-B: la base APRENDIDA de frases inocuas tambien cuenta
            from apps.analysis.models import InnocuousPhrase
            es_lexico = InnocuousPhrase.objects.filter(text_norm=n).exists()
        # Un ECO es una REPETICION: solo puede serlo respecto del segmento
        # ANTERIOR. Comparar tambien con el siguiente hacia que dos copias
        # identicas se aniquilaran mutuamente — el original sustancial moria
        # junto al eco (lo cazo el oro de David: 24 omisiones, sustancia
        # perdida). Fix 4.7-B.1.
        prev = segs[i - 1] if i > 0 else None
        es_eco = bool(prev) and n and n in norm(prev.text)
        if es_lexico or es_eco:
            fuera.append(s2.pk)
    if fuera:
        post.transcript_segments.filter(pk__in=fuera).delete()
        logger.info('Post %s: %d reacciones sueltas omitidas del transcript',
                    post.pk, len(fuera))
    return len(fuera)


def _nota(texto):
    """Fix del operador (2026-08-26): attribution_note es varchar(160) y la razon
    de la pasada de sentido viene del modelo SIN acotar — con large-v3 crecio y
    un DataError tumbo la pasada ENTERA en el post 5. Se trunca al limite REAL
    del campo (leido del modelo, no cableado)."""
    from apps.analysis.models import TranscriptSegment
    tope = TranscriptSegment._meta.get_field('attribution_note').max_length
    return (texto or '')[:tope]


def apply_changes(segments, etiquetas, cambios, post):
    """Aplica en la BD. relabel/split solo con confianza alta; todo lo demas
    marca la frase como incierta. Los indices son los de la lista ordenada."""
    out = {'relabeled': 0, 'split': 0, 'uncertain': 0}
    tocados = set()
    for c in cambios:
        i = int(c.get('i'))
        if i in tocados or not (0 <= i < len(segments)):
            continue
        s = segments[i]
        accion = str(c.get('action') or '').lower()
        voz = str(c.get('speaker') or '')
        seguro = str(c.get('confidence') or '').lower() == 'high'
        razon = str(c.get('reason') or '')[:150]
        if accion == 'relabel' and seguro and voz in etiquetas and voz != s.speaker_label:
            s.speaker_label = voz
            s.attribution_uncertain = False
            s.attribution_note = _nota(f'corregida por la pasada de sentido: {razon}')
            s.save(update_fields=['speaker_label', 'attribution_uncertain', 'attribution_note'])
            out['relabeled'] += 1
        elif accion == 'split' and seguro and voz in etiquetas:
            palabras = s.text.split()
            try:
                k = int(c.get('split_word'))
            except (TypeError, ValueError):
                continue
            if not (2 <= k <= len(palabras)):
                continue
            primera, segunda = ' '.join(palabras[:k - 1]), ' '.join(palabras[k - 1:])
            dur = max(0.0, s.end_seconds - s.start_seconds)
            corte = s.start_seconds + dur * (len(primera) / max(1, len(s.text)))
            nuevo = type(s).objects.create(
                post=post, start_seconds=round(corte, 2), end_seconds=s.end_seconds,
                text=segunda, speaker_label=voz, signal=s.signal,
                attribution_note=_nota(f'partida por la pasada de sentido: {razon}'))
            s.text, s.end_seconds = primera, round(corte, 2)
            s.save(update_fields=['text', 'end_seconds'])
            out['split'] += 1
        else:
            s.attribution_uncertain = True
            s.attribution_note = _nota(razon or 'la pasada de sentido no está segura')
            s.save(update_fields=['attribution_uncertain', 'attribution_note'])
            out['uncertain'] += 1
        tocados.add(i)
    logger.info('Post %s: pasada de sentido → %d reetiquetadas, %d partidas, %d inciertas',
                post.pk, out['relabeled'], out['split'], out['uncertain'])
    return out
