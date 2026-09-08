"""5.24-B (orden de David): el AUDIO ORIGINAL de un podcast de Spotify.

Spotify protege su reproductor con DRM, pero casi todos los podcasts publican
ademas un canal RSS con el MP3 original sin proteccion. Dado un enlace de
episodio de Spotify:
  1. se lee su pagina publica (titulo del episodio y nombre del programa);
  2. se busca el programa en el indice publico de podcasts de Apple
     (itunes.apple.com/search — gratis, sin clave) para obtener la URL del RSS;
  3. se lee el RSS y se casa el episodio por parecido de titulo;
  4. se devuelve el MP3 como ALTERNATIVA «audio original (RSS)» junto a las
     versiones con video que encuentre la busqueda web (5.19).
Todo fail-soft: cualquier fallo devuelve [] y el usuario ve lo que haya.
Nada se almacena: el enlace al MP3 es del editor del podcast, como el de YouTube.
"""
import difflib
import html as _html
import logging
import re
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger('embeds.rss')
UA = {'User-Agent': 'Mozilla/5.0 (compatible; esestocierto/1.0; +https://esestocierto.com)'}
ITUNES = 'https://itunes.apple.com/search'
MAX_FEED_BYTES = 6_000_000


def _limpio(t):
    t = _html.unescape(t or '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def ficha_spotify(url):
    """(titulo_episodio, nombre_programa) leidos de la pagina publica."""
    try:
        r = requests.get(url, headers=UA, timeout=8)
        if r.status_code != 200:
            return '', ''
        h = r.text
    except Exception as exc:
        logger.warning('RSS: pagina de Spotify ilegible (%r)', exc)
        return '', ''
    og = re.search(r'<meta property="og:title" content="([^"]+)"', h)
    titulo = _limpio(og.group(1)) if og else ''
    programa = ''
    # el <title> de un episodio: «Episodio - Programa | Podcast on Spotify»
    t = re.search(r'<title>([^<]+)</title>', h)
    if t:
        crudo = _limpio(t.group(1)).split('|')[0]
        if ' - ' in crudo:
            partes = crudo.rsplit(' - ', 1)
            programa = partes[1].strip()
            if not titulo:
                titulo = partes[0].strip()
    if not programa:
        m = re.search(r'"name":"([^"]{2,120})","@type":"PodcastSeries"', h) or \
            re.search(r'PodcastSeries"[^}]{0,200}"name":"([^"]{2,120})"', h)
        if m:
            programa = _limpio(m.group(1))
    return titulo, programa


def feeds_de(programa):
    """URLs de RSS candidatas para un nombre de programa (indice de Apple)."""
    if not programa:
        return []
    try:
        r = requests.get(ITUNES, params={'media': 'podcast', 'entity': 'podcast',
                                         'term': programa, 'limit': 5}, headers=UA, timeout=8)
        if r.status_code != 200:
            return []
        out = []
        for it in (r.json().get('results') or []):
            if it.get('feedUrl'):
                out.append({'feed': it['feedUrl'], 'nombre': it.get('collectionName', '')})
        return out
    except Exception as exc:
        logger.warning('RSS: indice de podcasts no responde (%r)', exc)
        return []


def _texto(el, *nombres):
    for n in nombres:
        x = el.find(n)
        if x is not None and (x.text or '').strip():
            return _limpio(x.text)
    return ''


def episodios(feed_url):
    """[{titulo, url, tipo, fecha, duracion}] del RSS (solo items con audio)."""
    try:
        r = requests.get(feed_url, headers=UA, timeout=12, stream=True)
        if r.status_code != 200:
            return []
        cuerpo = b''
        for trozo in r.iter_content(65536):
            cuerpo += trozo
            if len(cuerpo) > MAX_FEED_BYTES:
                break
        raiz = ET.fromstring(cuerpo)
    except Exception as exc:
        logger.warning('RSS: canal %s ilegible (%r)', feed_url[:80], exc)
        return []
    ns = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd'}
    out = []
    for item in raiz.iter('item'):
        enc = item.find('enclosure')
        if enc is None:
            continue
        u = enc.get('url') or ''
        tipo = enc.get('type') or ''
        if not u.startswith('http') or (tipo and not tipo.startswith('audio')):
            continue
        out.append({'titulo': _texto(item, 'title'), 'url': u, 'tipo': tipo,
                    'fecha': _texto(item, 'pubDate'),
                    'duracion': _texto(item, 'itunes:duration'.replace('itunes:', '{%s}' % ns['itunes']))})
    return out


def segundos(duracion):
    """'1:02:03' / '62:03' / '3723' -> 3723 (0 si no se entiende)."""
    d = (duracion or '').strip()
    if not d:
        return 0
    try:
        if ':' in d:
            partes = [int(float(x)) for x in d.split(':')]
            while len(partes) < 3:
                partes.insert(0, 0)
            h, m, s = partes[-3:]
            return h * 3600 + m * 60 + s
        return int(float(d))
    except ValueError:
        return 0


def _parecido(a, b):
    a, b = _limpio(a).lower(), _limpio(b).lower()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def alternativas_rss(url):
    """Para un enlace de episodio de Spotify: [{url, titulo, plataforma:'audio',
    origen, parecido}] con el MP3 original si se encuentra (0 o 1 elementos)."""
    titulo, programa = ficha_spotify(url)
    if not titulo and not programa:
        return []
    mejor = None
    for f in feeds_de(programa or titulo)[:3]:
        for ep in episodios(f['feed'])[:300]:
            p = _parecido(titulo, ep['titulo'])
            if p >= 0.6 and (mejor is None or p > mejor['parecido']):
                mejor = {'url': ep['url'], 'titulo': ep['titulo'] or titulo,
                         'plataforma': 'audio', 'origen': f['nombre'] or programa,
                         'parecido': round(p, 2), 'duracion': segundos(ep['duracion'])}
        if mejor and mejor['parecido'] >= 0.9:
            break
    return [mejor] if mejor else []
