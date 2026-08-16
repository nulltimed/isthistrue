"""Wikidata / Wikipedia: fotos y BUSQUEDA de personas para el nombrado
participativo de hablantes (peticion de David, 2026-08-17).

Por que Wikidata y no una lista propia: identificador UNIVOCO y estable (QID),
licencia libre, API gratuita y sin clave. Dos personas con el mismo nombre son
dos QID distintos, asi que "Pedro Sanchez (politico)" y "Pedro Sanchez (futbolista)"
NUNCA se confunden en la wiki de claims.

LINEA ROJA (congelada §4.7): aqui no hay NADA de voz. Solo texto y fotos publicas;
la diarizacion sigue produciendo etiquetas genericas SPEAKER_XX por video y jamas
se persisten huellas ni embeddings de voz, ni se comparan hablantes entre videos.
"""
import hashlib
import logging

import httpx
from django.core.cache import cache

logger = logging.getLogger('agents.wikidata')

_UA = {'User-Agent': 'isthistrue/1.0 (contact@xyztserver.com)'}
_TIMEOUT = 6          # la caja de sugerencias no puede colgar la pagina
_CACHE_SECONDS = 86400  # 24 h: los famosos no cambian de nombre a diario


def photo_for(name, lang='es'):
    """Foto de Wikipedia por NOMBRE (compatibilidad: lo usaban las propuestas)."""
    try:
        r = httpx.get(f'https://{lang}.wikipedia.org/api/rest_v1/page/summary/'
                      + name.replace(' ', '_'), timeout=_TIMEOUT, headers=_UA)
        if r.status_code == 200:
            data = r.json()
            thumb = (data.get('thumbnail') or {}).get('source', '')
            is_person = data.get('description', '') != '' and data.get('type') == 'standard'
            return thumb if (thumb and is_person) else ''
    except Exception as exc:
        logger.warning('Foto de Wikipedia no disponible para %r: %r', name, exc)
    return ''


def _is_human(entity):
    """P31 (instancia de) == Q5 (ser humano). Sin esto, buscar 'Ferrari'
    devolveria la escuderia; queremos personas, no marcas ni peliculas."""
    claims = (entity.get('claims') or {}).get('P31') or []
    for c in claims:
        try:
            if c['mainsnak']['datavalue']['value']['id'] == 'Q5':
                return True
        except (KeyError, TypeError):
            continue
    return False


def _commons_thumb(filename, width=80):
    """URL de miniatura de Wikimedia Commons (licencia libre) desde P18."""
    from urllib.parse import quote
    return ('https://commons.wikimedia.org/wiki/Special:FilePath/'
            f'{quote(filename.replace(" ", "_"))}?width={width}')


def search_people(query, lang='es', limit=6):
    """Busca PERSONAS en Wikidata y devuelve candidatos listos para la caja.

    Cada resultado: {'qid', 'name', 'description', 'photo'}. El QID es la
    identificacion univoca; el nombre y la descripcion son para que el usuario
    distinga entre homonimos ("politico" vs "futbolista").

    Degradacion RUIDOSA (regla 5.7): si Wikidata no responde, WARNING en logs y
    lista vacia — la caja sigue aceptando texto libre, nunca se bloquea.
    """
    query = ' '.join((query or '').split())
    if len(query) < 3:
        return []
    # Clave hasheada: los nombres traen espacios y tildes, y eso rompe con
    # memcached (CacheKeyWarning). Con LocMem funciona, pero no dejamos trampas.
    key = 'wd:people:%s:%s' % (lang, hashlib.sha1(query.lower().encode()).hexdigest())
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        r = httpx.get('https://www.wikidata.org/w/api.php', timeout=_TIMEOUT, headers=_UA,
                      params={'action': 'wbsearchentities', 'search': query,
                              'language': lang, 'uselang': lang, 'type': 'item',
                              'limit': 20, 'format': 'json'})
        r.raise_for_status()
        hits = r.json().get('search') or []
        ids = [h['id'] for h in hits][:20]
        if not ids:
            cache.set(key, [], _CACHE_SECONDS)
            return []
        # Segunda llamada: los datos completos dicen QUIEN es persona y su foto.
        r2 = httpx.get('https://www.wikidata.org/w/api.php', timeout=_TIMEOUT, headers=_UA,
                       params={'action': 'wbgetentities', 'ids': '|'.join(ids),
                               'props': 'labels|descriptions|claims',
                               'languages': f'{lang}|en', 'format': 'json'})
        r2.raise_for_status()
        entities = r2.json().get('entities') or {}
    except Exception as exc:
        logger.warning('Búsqueda de personas en Wikidata no disponible (%r): %r', query, exc)
        return []

    results = []
    for qid in ids:  # se respeta el orden de relevancia de Wikidata
        ent = entities.get(qid) or {}
        if not _is_human(ent):
            continue
        labels, descs = ent.get('labels') or {}, ent.get('descriptions') or {}
        name = (labels.get(lang) or labels.get('en') or {}).get('value', '')
        desc = (descs.get(lang) or descs.get('en') or {}).get('value', '')
        if not name:
            continue
        photo = ''
        try:
            photo = _commons_thumb(ent['claims']['P18'][0]['mainsnak']['datavalue']['value'])
        except (KeyError, IndexError, TypeError):
            pass
        results.append({'qid': qid, 'name': name[:160],
                        'description': desc[:120], 'photo': photo})
        if len(results) >= limit:
            break
    cache.set(key, results, _CACHE_SECONDS)
    return results


def entity_photo(qid, width=80):
    """Foto (P18) de un QID concreto: se usa al guardar la propuesta elegida."""
    if not qid:
        return ''
    key = f'wd:photo:{qid}:{width}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        r = httpx.get('https://www.wikidata.org/w/api.php', timeout=_TIMEOUT, headers=_UA,
                      params={'action': 'wbgetentities', 'ids': qid,
                              'props': 'claims', 'format': 'json'})
        r.raise_for_status()
        ent = (r.json().get('entities') or {}).get(qid) or {}
        photo = _commons_thumb(ent['claims']['P18'][0]['mainsnak']['datavalue']['value'], width)
    except Exception as exc:
        logger.warning('Foto de Wikidata no disponible para %s: %r', qid, exc)
        photo = ''
    cache.set(key, photo, _CACHE_SECONDS)
    return photo
