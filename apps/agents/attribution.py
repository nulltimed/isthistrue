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
    guion = '\n'.join(f'[{s.speaker_label}] {s.text}' for s in segments)
    payload = f"VOCES: {', '.join(etiquetas)}\n\nARRANQUE:\n{guion}"
    try:
        datos = client.call_json(model_for('attribution'),
                                 prompts.INTRO_REWRITE_SYSTEM, payload,
                                 max_tokens=4000,
                                 mock_payload={'utterances': []})
    except Exception as exc:
        logger.warning('Reescritura de arranque fallida en el post %s: %r',
                       post.pk, exc)
        return {'rewritten': 0}
    utt = [u for u in (datos.get('utterances') or [])
           if str(u.get('text', '')).strip()]
    if not utt:
        return {'rewritten': 0}

    def toks(t):
        return re.findall(r"[\w']+", t.lower())
    orig = [w for s in segments for w in toks(s.text)]
    nuevo_txt = [w for u in utt for w in toks(str(u['text']))]
    if orig != nuevo_txt:
        logger.warning('Reescritura de arranque DESCARTADA en el post %s: el '
                       'texto no coincide (%d vs %d palabras)',
                       post.pk, len(orig), len(nuevo_txt))
        return {'rewritten': 0}
    if any(u.get('speaker') not in etiquetas for u in utt):
        logger.warning('Reescritura de arranque DESCARTADA en el post %s: '
                       'etiqueta desconocida', post.pk)
        return {'rewritten': 0}

    # reloj: cada palabra original hereda un tramo proporcional de su frase
    tiempos = []
    for s in segments:
        ws = toks(s.text)
        n = len(ws) or 1
        dur = s.end_seconds - s.start_seconds
        for k in range(len(ws)):
            tiempos.append((s.start_seconds + dur * k / n,
                            s.start_seconds + dur * (k + 1) / n))
    from apps.analysis.models import TranscriptSegment
    nuevos, idx = [], 0
    for u in utt:
        n = len(toks(str(u['text'])))
        ini, fin = tiempos[idx][0], tiempos[idx + n - 1][1]
        idx += n
        nuevos.append(TranscriptSegment(
            post=post, start_seconds=round(ini, 3), end_seconds=round(fin, 3),
            text=str(u['text']).strip(), speaker_label=u['speaker'],
            attribution_note=_nota('arranque reescrito por la pasada de sentido')))
    with transaction.atomic():
        post.transcript_segments.filter(
            pk__in=[s.pk for s in segments]).delete()
        TranscriptSegment.objects.bulk_create(nuevos)
    logger.info('Post %s: arranque reescrito — %d frases → %d intervenciones',
                post.pk, len(segments), len(nuevos))
    return {'rewritten': len(nuevos)}


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
