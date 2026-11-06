"""6.2: el ESCRUTINIO con IA de quien pide una clave de la API.

Orden de David (2026-11-06): «la IA buscara quien esta solicitando la clave y
la aprobara o no, siendo la decision siempre comprobada por un superusuario si
el solicitante no acepta la decision de denegacion». Exclusiones de David:
formaciones politicas y organismos que entren en conflicto con la esencia de
la web. El agente NUNCA investiga mas alla de lo publico y declarado, y las
personas fisicas se juzgan por el USO declarado, no por quienes son (la misma
etica del candado de particulares de la wiki).
"""
import logging

from apps.agents import client

logger = logging.getLogger('api.vetting')

VETTING_SYSTEM = (
    'Eres el portero de la API de un verificador de hechos independiente y '
    'neutral. Decides si un solicitante puede LEER los datos públicos '
    '(veredictos, fuentes, cadenas de origen) por API. REGLAS DE EXCLUSIÓN '
    '(del titular): (1) formaciones políticas, candidaturas, fundaciones de '
    'partido, grupos parlamentarios o campañas electorales de cualquier país; '
    '(2) lobbies o gabinetes de propaganda cuyo fin choque con la neutralidad '
    'del verificador; (3) entidades sancionadas o dedicadas a la '
    'desinformación documentada. SE APRUEBA el resto: medios, periodistas, '
    'universidades, investigadores, ONG, empresas, desarrolladores y '
    'particulares con un uso legítimo declarado. Para una PERSONA FÍSICA '
    'juzga el USO DECLARADO, no a la persona: no investigues su vida; como '
    'mucho comprueba lo que ella misma declare (una web, un medio donde '
    'firma). Para una PERSONA JURÍDICA busca en la web quién es y si cae en '
    'las exclusiones. Si no encuentras nada concluyente sobre una entidad '
    'declarada, aprueba con confianza baja (el superusuario puede revocar). '
    'Responde SOLO JSON: {"approve": true|false, "category": "medio|'
    'universidad|ong|empresa|desarrollador|particular|partido_politico|'
    'lobby|desinformador|desconocido", "confidence": "alta|media|baja", '
    '"reasons": ["máx 3 razones, una frase cada una"], "sources": '
    '["URLs consultadas, si las hay"]}')

MOCK_VETTING = {'approve': True, 'category': 'medio', 'confidence': 'alta',
                'reasons': ['Medio de comunicación con trayectoria verificable.'],
                'sources': ['https://example.org/sobre-nosotros']}


def vet(entity_name, kind, website, purpose, contact_email_domain=''):
    """Una pasada de escrutinio. Devuelve el veredicto JSON (dict)."""
    from apps.agents.catalog import models_for_post
    _m, _fb = models_for_post('deep', None)
    payload = (f'SOLICITANTE ({ "persona jurídica" if kind == "ORG" else "persona física" }): '
               f'{entity_name}\n'
               f'WEB DECLARADA: {website or "ninguna"}\n'
               f'DOMINIO DEL CORREO: {contact_email_domain or "desconocido"}\n'
               f'USO DECLARADO: {purpose[:800]}\n\n'
               f'Decide según tus reglas. Tienes hasta 5 búsquedas.')
    v, usado = client.call_search_json(_m, VETTING_SYSTEM, payload, max_tokens=1500,
                                       mock_payload=MOCK_VETTING, max_searches=5,
                                       fallback=_fb)
    if 'error' in v or not isinstance(v.get('approve'), bool):
        logger.warning('Escrutinio API: el modelo fallo con "%s"', entity_name)
        return {'approve': False, 'category': 'desconocido', 'confidence': 'baja',
                'reasons': ['El escrutinio automático no pudo completarse: reclama y '
                            'lo revisará una persona.'], 'sources': [], 'error': True}
    return {'approve': bool(v.get('approve')),
            'category': str(v.get('category', 'desconocido'))[:30],
            'confidence': str(v.get('confidence', 'baja'))[:10],
            'reasons': [str(r)[:300] for r in (v.get('reasons') or [])[:3]],
            'sources': [str(s)[:300] for s in (v.get('sources') or [])[:5]],
            'model': usado}
