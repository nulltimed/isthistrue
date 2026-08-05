"""Fotos de candidatos (peticion de David) via Wikidata/Wikipedia: licencia libre,
API gratuita. Sin ficha en Wikipedia -> sin foto (y pista de que quiza no es
figura publica, que es nuestro filtro congelado)."""
import httpx


def photo_for(name, lang='es'):
    try:
        r = httpx.get(f'https://{lang}.wikipedia.org/api/rest_v1/page/summary/'
                      + name.replace(' ', '_'), timeout=10,
                      headers={'User-Agent': 'isthistrue/1.0 (contact@xyztserver.com)'})
        if r.status_code == 200:
            data = r.json()
            thumb = (data.get('thumbnail') or {}).get('source', '')
            is_person = data.get('description', '') != '' and data.get('type') == 'standard'
            return thumb if (thumb and is_person) else ''
    except Exception:
        pass
    return ''
