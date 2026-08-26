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
            s.attribution_note = f'corregida por la pasada de sentido: {razon}'
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
                attribution_note=f'partida por la pasada de sentido: {razon}')
            s.text, s.end_seconds = primera, round(corte, 2)
            s.save(update_fields=['text', 'end_seconds'])
            out['split'] += 1
        else:
            s.attribution_uncertain = True
            s.attribution_note = razon or 'la pasada de sentido no está segura'
            s.save(update_fields=['attribution_uncertain', 'attribution_note'])
            out['uncertain'] += 1
        tocados.add(i)
    logger.info('Post %s: pasada de sentido → %d reetiquetadas, %d partidas, %d inciertas',
                post.pk, out['relabeled'], out['split'], out['uncertain'])
    return out
