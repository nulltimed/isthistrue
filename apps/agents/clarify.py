"""5.6-A (orden de David): el CLARIFICADOR de sin-resolver.

«Hay que intentar por todos los medios clarificar las afirmaciones/opiniones
sin resolver. [...] Exprime el modelo LLM».

Una afirmacion que quedo UNDECIDED (🔍) recibe una SEGUNDA pasada de ultima
instancia con el modelo del reanalisis profundo (rueda 'deep' del panel) y el
DOBLE de busquedas: el encargo le ordena descomponer la afirmacion en hechos
comprobables, reformular las busquedas (espanol e ingles, nombres + fechas),
mirar hemerotecas y diarios de sesiones, y — si la afirmacion relata un dicho
de otra persona — buscar la cita textual. El contrato JSON es EL MISMO del
veredicto normal (mismos sistemas), asi que el resultado se aplica con las
mismas garantias: sin fuentes no hay color (salvo GREY legitimo de opinion).

Corre sola tras los veredictos (ajuste `clarify_pass`, 1 de fabrica) y a mano
con `manage.py clarificar_claims`. Cada claim pasa por el fusible del
presupuesto diario.
"""
import logging

from apps.agents import client, prompts

logger = logging.getLogger('agents.clarify')


def _tope():
    from apps.agents.catalog import web_searches_per_claim
    return max(8, 2 * web_searches_per_claim())


def _payload(claim, ap, tope):
    post = ap.segment.post
    fecha = post.event_date.isoformat() if post.event_date else None
    confirmadas = dict(post.name_proposals.filter(confirmed=True)
                       .values_list('speaker_label', 'candidate_name'))
    quien = confirmadas.get(ap.segment.speaker_label) \
        or ap.segment.speaker_label or '¿?'
    return (
        f"AFIRMACIÓN SIN RESOLVER (la primera pasada no encontró fuentes): "
        f"«{claim.text_original}»\n\n"
        + (f"FECHA DEL SUCESO: {fecha}\n" if fecha else '')
        + f"QUIÉN LO DIJO: {quien}\n"
          f"DÓNDE: {post.title or post.url} "
          f"(segundo {int(ap.segment.start_seconds or 0)})\n\n"
          "MISIÓN DE ÚLTIMA INSTANCIA — exprime tus capacidades:\n"
          "1) DESCOMPÓN la afirmación en los hechos comprobables que contiene.\n"
          "2) REFORMULA las búsquedas varias veces: nombres propios, sinónimos "
          "y fechas, en español Y en inglés.\n"
          "3) DÓNDE MIRAR: transcripciones y diarios de sesiones oficiales "
          "(Congreso, parlamentos), hemerotecas de prensa, RTVE a la carta, "
          "verificadores (Newtral, Maldita.es, Verificat, EFE Verifica).\n"
          "4) Si la afirmación relata un DICHO de otra persona («X dijo/ofreció "
          "...»), lo comprobable es SI CONSTA que lo dijo: busca la cita "
          "textual y su fecha.\n"
          f"Tienes hasta {tope} búsquedas: úsalas. Lista en \"sources\" las "
          "URLs reales que uses. Solo si tras agotar todos los caminos no hay "
          "nada: UNDECIDED.\n\n"
          # Leccion de la primera tanda real: 11 de 13 fallaron con json_parse
          # — el modelo, exprimido, se explaya y el JSON llegaba TRUNCADO por
          # max_tokens. Mas aire (3000) y el recordatorio explicito.
          "IMPORTANTE: responde ÚNICAMENTE con el objeto JSON del contrato, "
          "sin ningún texto antes ni después.")


def _aplicar(claim, v, sources_ok):
    """El resultado se aplica con las mismas garantias que upsert_claim
    (color, evidencia, version en el historial, fuentes, avisos)."""
    from apps.wiki.models import Claim, ClaimVersion, Source
    old_color = claim.color
    claim.color = v.get('color') or claim.color
    claim.what_is_claimed = v.get('what_is_claimed') or claim.what_is_claimed
    claim.what_evidence_says = v.get('what_evidence_says') or claim.what_evidence_says
    claim.the_difference = v.get('the_difference', claim.the_difference)
    claim.model_used = (v.get('model_used') or '')[:60]
    _max_sens = Claim._meta.get_field('sensitive').max_length
    if v.get('sensitive'):
        claim.sensitive = v['sensitive'][:_max_sens]
    claim.sources_ok = sources_ok
    claim.save()
    ClaimVersion.objects.create(claim=claim, color=claim.color, body_snapshot=v)
    if v.get('sources'):
        claim.sources.all().delete()
        for s in v['sources']:
            Source.objects.create(claim=claim, url=s.get('url', ''),
                                  title=s.get('title', ''))
    if old_color != claim.color:
        from apps.accounts.services import notify
        for f in claim.followers.select_related('user'):
            notify(f.user, f'El semáforo de un claim que sigues ha cambiado: '
                           f'«{claim.text_original[:70]}»',
                   f'/wiki/claim/{claim.slug or claim.pk}/', kind='claim_color')


def clarify_claim(claim):
    """Una pasada de ultima instancia. Devuelve el color final o None."""
    from apps.agents import verdict as verdict_agent
    from apps.agents.catalog import models_for_post
    ap = claim.appearances.select_related('segment__post').first()
    if not ap:
        return None     # claim huerfano (sin aparicion): no hay contexto
    post = ap.segment.post
    es_op = claim.kind == 'OPINION'
    sistema = prompts.OPINION_VERDICT_SYSTEM if es_op else prompts.VERDICT_SYSTEM
    tope = _tope()
    _m, _fb = models_for_post('deep', post)
    v, usado = client.call_search_json(
        _m, sistema, _payload(claim, ap, tope), max_tokens=3000,
        mock_payload=verdict_agent.MOCK_VERDICT, max_searches=tope, fallback=_fb)
    if 'error' in v:
        logger.warning('Clarificador: el modelo fallo con el claim %s (%s)',
                       claim.pk, v.get('error'))
        return None
    v['model_used'] = usado
    tiene = bool(v.get('sources'))
    # La misma garantia del 4.4-B: sin fuentes no hay color (GREY de opinion
    # pura es la unica excepcion legitima, 5.3-C).
    if not tiene and not (es_op and v.get('color') == 'GREY'):
        v['color'] = 'UNDECIDED'
    _aplicar(claim, v, tiene or (es_op and v.get('color') == 'GREY'))
    return claim.color


# Estimacion por claim para el fusible del presupuesto: ~doble de busquedas
# que un veredicto normal + el modelo grande. Se apunta el gasto REAL igual
# (libro 5.3-D); esto solo evita que una tanda vacie el dia.
COST_PER_CLAIM_EUR = 0.06


def run_pending(post, limit=25):
    """Tras los veredictos: clarificar los UNDECIDED del post. Fail-soft."""
    from apps.panel.models import SystemSetting
    from apps.wiki.models import Claim
    if SystemSetting.get_int('clarify_pass', 1) <= 0:
        return 0
    qs = Claim.objects.filter(color='UNDECIDED',
                              appearances__segment__post=post).distinct()
    resueltos = 0
    for c in qs[:limit]:
        from apps.analysis.models import DailyBudget
        if not DailyBudget.try_spend(COST_PER_CLAIM_EUR):
            logger.warning('Clarificador: presupuesto agotado (post %s)', post.pk)
            break
        try:
            if clarify_claim(c) not in (None, 'UNDECIDED'):
                resueltos += 1
        except Exception as exc:
            logger.warning('Clarificador fallo con el claim %s (%r)', c.pk, exc)
    return resueltos
