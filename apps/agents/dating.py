"""4.4-B: ¿CUANDO ocurrio lo que se ve en el video? (no cuando se subio)

David lo pidio asi, literal: «el agente de verificacion debe averiguar eso
buscando pistas. Por ejemplo, mirando el titulo del video y comparandolo con si
hubo eventos de algun tipo en la fecha concreta, o mirando en la transcripcion si
se repite una fecha que pueda dar contexto (imaginate que Rosa Diez, 20
comentarios antes de hablar de la cifra de empleados, hubiese dicho algun dato
temporal que ayude a determinar de que fechas esta hablando)».

Ojo a la diferencia con el CONTEXTO del veredicto, que son las frases contiguas
del mismo hablante: para datar hay que barrer la transcripcion ENTERA. Son dos
mecanismos distintos y no deben confundirse.

Modelo: Haiku (el barato). Se ejecuta UNA vez por post.
"""
import logging

from django.conf import settings

from apps.agents import client, prompts

logger = logging.getLogger('agents.dating')

MOCK_DATING = {'event_date': '2023-07-10', 'confidence': 'high',
               'note': '[SIMULADO] El título menciona un debate electoral datable.'}

# Cuanta transcripcion se le enseña: las marcas temporales suelen estar al
# principio (presentacion) y repartidas. 12.000 caracteres cubren de sobra un
# debate y cuestan centesimas de centimo con Haiku.
MAX_CHARS = 12000


def date_event(post):
    """Devuelve (fecha ISO o None, nota). No escribe en la BD: eso es de quien llama."""
    textos = list(post.transcript_segments.order_by('start_seconds', 'pk')
                  .values_list('text', flat=True))
    cuerpo = ' '.join(textos)[:MAX_CHARS]
    subida = getattr(post, 'created_at', None)
    payload = (f"TITULO DEL VIDEO: {post.title or '(sin titulo)'}\n"
               f"URL: {post.url}\n"
               f"FECHA DE SUBIDA (tope superior): "
               f"{subida.date().isoformat() if subida else '(desconocida)'}\n\n"
               f"TRANSCRIPCION (fragmento):\n{cuerpo}")
    from apps.agents.catalog import model_for
    datos = client.call_json(model_for('dating'), prompts.DATING_SYSTEM, payload,
                             max_tokens=400, mock_payload=MOCK_DATING)
    if 'error' in datos:
        logger.warning('Datación fallida en el post %s: %s', post.pk, datos.get('error'))
        return (None, '')
    return (normalize(datos.get('event_date')), (datos.get('note') or '')[:250])


def normalize(valor):
    """'2023' -> 2023-01-01 · '2023-07' -> 2023-07-01 · '2023-07-10' -> tal cual.

    El modelo puede devolver una fecha con menos precision de la que pide un
    DateField. Un año suelto ya sirve para elegir la tabla correcta: perderlo por
    no encajar en el formato seria tirar la unica pista que hay.
    """
    import datetime
    if not valor or not isinstance(valor, str):
        return None
    trozos = valor.strip().split('-')
    try:
        anio = int(trozos[0])
        mes = int(trozos[1]) if len(trozos) > 1 else 1
        dia = int(trozos[2]) if len(trozos) > 2 else 1
        if not (1900 <= anio <= 2100):
            return None
        return datetime.date(anio, mes, dia)
    except (ValueError, IndexError):
        return None
