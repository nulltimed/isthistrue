"""5.32 (orden de David, 2026-10-20): EL VIDEO COMO FUENTE.

Caso que lo motivo (post 4, Abascal en el 2:56): «Usted trae aqui una foto y la
manipula...». La foto la habia enseñado Diaz en el 2:37; la vista miro los
fotogramas del 2:56 (cuando habla Abascal), no vio la foto, y el verificador
busco en internet una foto de la que no sabia nada: 🔍 sin resolver.

Aqui se hace lo que haria una persona:
 1. DETECTAR que la frase se refiere a algo del propio video («esta foto»,
    «usted trae aqui», «lo que acaba de decir», «en esta pantalla»). Regla
    determinista (regex), sin coste.
 2. BUSCAR EL MOMENTO al que se refiere: hacia atras en la transcripcion, la
    frase mas cercana que nombra el objeto, y el ARRANQUE del turno anterior
    del otro hablante (quien enseño la cosa suele ser el interlocutor).
 3. MANDAR LA VISTA a esos momentos con la pregunta «¿que se muestra y que
    contiene?», ademas de al instante de la frase.
 4. El VIDEO cuenta como fuente (enlace al segundo exacto + fotograma) SOLO si
    la vista vio algo que sostiene o contradice; si no vio nada, no hay fuente
    y el candado «sin fuentes no hay color» sigue intacto. Con lo visto, el
    verificador busca fuera el hecho de fondo.
Interruptor del panel: `video_as_source` (1 de fabrica).
"""
import logging
import re

logger = logging.getLogger('agents.selfref')

OBJETOS = {
    'foto': r'foto(?:graf[ií]a)?s?',
    'imagen': r'im[aá]gen(?:es)?',
    'gráfico': r'gr[aá]fic[ao]s?',
    'tabla': r'tablas?',
    'documento': r'documentos?|papel(?:es)?|informes?|cartas?',
    'cartel': r'cartel(?:es)?|pancartas?',
    'vídeo': r'v[ií]deos?|clips?|fragmentos?',
    'pantalla': r'pantalla',
    'dato': r'datos?|cifras?|n[uú]meros?',
}
_DEICTICO = r'(?:est[aeo]s?|es[aeo]s?|aquel(?:la|los|las)?|la|el|los|las|una?|unos?|unas?)'
_P_OBJETO = re.compile(r'\b' + _DEICTICO + r'\s+(?:misma?s?\s+)?(' + '|'.join(OBJETOS.values()) + r')\b', re.I)
_P_CLAVE = re.compile(r'\b(?:usted(?:es)?\s+(?:me\s+|nos\s+)?trae[ns]?\s+aqu[ií]|aqu[ií]\s+(?:les?\s+)?(?:tengo|traigo)'
                      r'|lo\s+que\s+acaba[ns]?\s+de\s+(?:decir|mostrar|ense[ñn]ar|ver|leer)'
                      r'|como\s+(?:ha|has|han|he)\s+dicho\s+(?:antes|hace\s+un\s+momento|al\s+principio)'
                      r'|(?:lo\s+que|como)\s+(?:ven|vemos|se\s+ve|est[aá]n\s+viendo)\s+(?:aqu[ií]|en\s+(?:la\s+|esta\s+)?pantalla)'
                      r'|en\s+(?:esta|la)\s+pantalla'
                      r'|(?:este|el)\s+v[ií]deo\s+que\s+(?:acaba[ns]?\s+de|hemos)\s+(?:ver|visto|emitir|poner))\b', re.I)
_P_SENAL = re.compile(r'\b(?:trae[ns]?|tra[ií]do|muestra[ns]?|mostrado|ense[ñn]a[ns]?|ense[ñn]ado|saca[ns]?|sacado|'
                      r'exhibe[ns]?|levanta[ns]?|he\s+tra[ií]do|ha\s+tra[ií]do|manipula[ns]?|'
                      r've[ns]?|vemos|viendo|ver|lea[ns]?|leer|leemos)\b', re.I)


def activo():
    try:
        from apps.panel.models import SystemSetting
        return SystemSetting.get_int('video_as_source', 1) > 0
    except Exception:
        return True


def detect(text):
    """¿La frase alude a algo del propio video? Devuelve {'objeto', 'motivo'} o None.
    Dispara: una frase clave («usted trae aqui», «lo que acaba de decir»...) o un
    deictico + objeto («esta foto», «ese grafico») acompañado de un verbo de
    mostrar (para no disparar con «la foto de mi abuela»)."""
    t = text or ''
    clave = _P_CLAVE.search(t)
    obj = _P_OBJETO.search(t)
    if not clave and not (obj and _P_SENAL.search(t)):
        return None
    objeto = ''
    if obj:
        for k, rx in OBJETOS.items():
            if re.fullmatch(rx, obj.group(1), re.I):
                objeto = k
                break
    return {'objeto': objeto, 'motivo': (clave or obj).group(0)}


def momentos(segments, i, objeto='', atras=20, adelante=4, maximo=4):
    """Segundos a los que mandar la vista, ademas del de la frase:
      1. la mencion mas cercana del objeto (hacia atras y un poco hacia delante);
      2. el turno anterior de OTRO hablante, muestreado en tres puntos (arranque,
         mitad y final): la cosa se enseña en algun momento de ese turno y la
         transcripcion rara vez lo nombra («¿Ve como se rien?» — post 4, 2:31).
    Sin repetir el instante de la frase ni momentos a menos de 8 s entre si."""
    rx = re.compile(r'\b(?:' + (OBJETOS.get(objeto) or '|'.join(OBJETOS.values())) + r')\b', re.I)
    out = []
    propio = int(segments[i].start_seconds or 0)
    for j in list(range(i - 1, max(-1, i - atras - 1), -1)) + list(range(i + 1, min(len(segments), i + adelante + 1))):
        if rx.search(segments[j].text or ''):
            out.append(int(segments[j].start_seconds or 0))
            break
    spk = segments[i].speaker_label
    j = i - 1
    while j >= 0 and segments[j].speaker_label == spk:
        j -= 1
    if j >= 0:
        otro = segments[j].speaker_label
        k = j
        while k - 1 >= 0 and segments[k - 1].speaker_label == otro and (i - (k - 1)) <= atras:
            k -= 1
        turno = segments[k:j + 1]
        for idx in sorted({0, len(turno) // 2, len(turno) - 1}):
            out.append(int(turno[idx].start_seconds or 0))
    res = []
    for s in out:
        if abs(s - propio) >= 8 and all(abs(s - r) >= 8 for r in res):
            res.append(s)
    return res[:maximo]


def _mmss(s):
    s = int(s or 0)
    return f'{s // 60:02d}:{s % 60:02d}'


def evidencia(post, texto, segments, i, ref):
    """Manda la vista a los momentos referidos. Devuelve el expediente de la
    referencia: {'ref', 'momentos': [{'segundo','detalle','veredicto'}],
    'mejor': hallazgo|None, 'transcripcion': str}."""
    from apps.agents import vision
    objeto = ref.get('objeto') or 'objeto (foto, gráfico, documento, vídeo)'
    pregunta = (f'{texto[:220]} — ¿Qué {objeto} se muestra en pantalla y qué contiene '
                f'exactamente (personas, rótulos, cifras, gesto)?')
    hallazgos, lineas = [], []
    for seg in momentos(segments, i, ref.get('objeto', '')):
        try:
            h = vision.mirar(post, pregunta, seg)
        except Exception as exc:
            logger.warning('5.32: la vista fallo en el post %s s%s (%r)', post.pk, seg, exc)
            h = None
        if h:
            h = dict(h)            # copia: la vista puede devolver el mismo objeto dos veces
            h['segundo'] = seg
            hallazgos.append(h)
        for s in segments:
            if abs(int(s.start_seconds or 0) - seg) <= 12:
                lineas.append(f'[{_mmss(s.start_seconds)}] {s.speaker_label or "¿?"}: {s.text}')
    mejor = next((h for h in hallazgos if h.get('veredicto_visual') in ('sostiene', 'contradice')),
                 hallazgos[0] if hallazgos else None)
    return {'ref': ref, 'momentos': [{'segundo': h['segundo'], 'detalle': h.get('detalle', ''),
                                      'veredicto': h.get('veredicto_visual', '')} for h in hallazgos],
            'mejor': mejor, 'transcripcion': '\n'.join(dict.fromkeys(lineas))}


def url_video(post, segundo):
    from django.conf import settings
    base = getattr(settings, 'AAI_WEBHOOK_BASE', '').rstrip('/')
    return f'{base}{post.get_absolute_url()}?t={int(segundo or 0)}'


def bloque(post, ev):
    """El texto que entra en el expediente del verificador."""
    if not ev:
        return ''
    partes = [f"REFERENCIA AL PROPIO VÍDEO: la frase alude a algo que ocurre en este mismo vídeo "
              f"(«{ev['ref'].get('motivo', '')}»)."]
    if ev.get('transcripcion'):
        partes.append('LO QUE DICE LA TRANSCRIPCIÓN EN ESOS MOMENTOS:\n' + ev['transcripcion'])
    if ev.get('momentos'):
        partes.append('LO QUE SE VE EN PANTALLA (la vista):\n' + '\n'.join(
            f"- minuto {_mmss(m['segundo'])}: {m['detalle'][:400]} [{m['veredicto']}]" for m in ev['momentos']))
    else:
        partes.append('LO QUE SE VE EN PANTALLA: la vista no pudo mirar esos momentos.')
    aporta = bool(ev.get('mejor')) and ev['mejor'].get('veredicto_visual') in ('sostiene', 'contradice')
    if aporta:
        partes.append(f"REGLA: para lo que ocurre DENTRO del vídeo (que se enseña una foto, que alguien dijo "
                      f"algo), el propio vídeo ES fuente válida: inclúyelo en \"sources\" como "
                      f"{{\"url\": \"{url_video(post, ev['mejor']['segundo'])}\", \"title\": "
                      f"\"El propio vídeo, minuto {_mmss(ev['mejor']['segundo'])}\"}}. Para el hecho de fondo "
                      f"(quiénes aparecen, cuándo ocurrió, contexto real) BUSCA fuentes externas partiendo de la "
                      f"descripción de la pantalla, y decide el color con ambas.")
    else:
        partes.append('La vista NO vio nada concluyente: el vídeo no puede citarse como fuente; '
                      'busca fuera con lo que dice la transcripción.')
    return '\n\n'.join(partes)


def ajustar_fuentes(v, post, ev):
    """Candado: el video solo es fuente si la vista APORTO. Si aporto y el modelo
    olvido citarlo, se añade; si no aporto, cualquier cita al video se retira
    (asi «sin fuentes no hay color» sigue mandando). Devuelve si aporto."""
    if not ev:
        return False
    mejor = ev.get('mejor')
    aporta = bool(mejor) and mejor.get('veredicto_visual') in ('sostiene', 'contradice')
    fuentes = [s for s in (v.get('sources') or []) if isinstance(s, dict)]
    ruta = post.get_absolute_url()
    es_video = lambda s: ruta in str(s.get('url', '')) or (post.url and post.url in str(s.get('url', '')))
    if aporta:
        if not any(es_video(s) for s in fuentes):
            fuentes.append({'url': url_video(post, mejor['segundo']),
                            'title': f"El propio vídeo, minuto {_mmss(mejor['segundo'])}"})
    else:
        fuentes = [s for s in fuentes if not es_video(s)]
    v['sources'] = fuentes
    return aporta
