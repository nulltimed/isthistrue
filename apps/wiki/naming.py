"""Nombrado participativo (diseño de David): votos ponderados; el moderador pesa
mas y desempata (SystemSetting mod_vote_weight=5). Al confirmar: se crea/asigna
el Interlocutor (SOLO figura publica tiene pagina), con 301 si cambia el slug."""
from django.utils.text import slugify
from apps.panel.models import SystemSetting
from .models import (Interlocutor, InterlocutorSlugHistory,
                     SpeakerNameProposal, SpeakerNameVote)

CONFIRM_POINTS = 'name_confirm_points'  # por defecto 5 puntos ponderados


def vote_proposal(proposal, user):
    if not (user.is_contrib_plus() or user.is_superuser):
        return False, 'Necesitas nivel Contribuidor o superior.'
    SpeakerNameVote.objects.get_or_create(proposal=proposal, user=user)
    points = sum(v.weight() for v in proposal.votes.select_related('user'))
    needed = SystemSetting.get_int(CONFIRM_POINTS, 5)
    if points >= needed and not proposal.confirmed:
        _confirm(proposal)
        return True, f'Confirmado: {proposal.candidate_name}.'
    return True, f'Voto registrado ({points}/{needed} puntos).'


def _person_for(proposal):
    """Devuelve el Interlocutor de la propuesta. La identidad la manda el QID de
    Wikidata cuando existe (2026-08-17): asi 'Pedro Sánchez (político)' y
    'Pedro Sánchez (futbolista)' son DOS fichas, no una revuelta. Sin QID se cae
    al comportamiento clasico por slug del nombre."""
    name, qid = proposal.candidate_name, (proposal.wikidata_id or '')
    if qid:
        person = Interlocutor.objects.filter(wikidata_id=qid).first()
        if person:
            return person
    base = slugify(name)[:150] or 'persona'
    slug, n = base, 2
    while Interlocutor.objects.filter(slug=slug).exists():
        # Homonimo con otra ficha (otro QID o sin el): slug propio, jamas mezclar.
        slug, n = f'{base}-{n}', n + 1
    return Interlocutor.objects.create(
        name=name, slug=slug, is_public_figure=None, wikidata_id=qid,
        photo_url=proposal.photo_url or '', description=proposal.description or '')


def _confirm(proposal):
    from apps.panel.models import AuditLog
    name = proposal.candidate_name
    person = _person_for(proposal)
    # Un solo nombre confirmado por hablante y post:
    SpeakerNameProposal.objects.filter(post=proposal.post,
        speaker_label=proposal.speaker_label).update(confirmed=False, interlocutor=None)
    proposal.confirmed = True
    proposal.interlocutor = person
    proposal.save(update_fields=['confirmed', 'interlocutor'])
    AuditLog.objects.create(action='speaker_confirmed',
                            detail=f'post {proposal.post_id} {proposal.speaker_label} -> {name}')


def rename_interlocutor(person, new_name):
    """Renombrado con redireccion 301 permanente (candado congelado)."""
    old = person.slug
    person.name = new_name
    person.slug = slugify(new_name)[:160]
    person.save()
    InterlocutorSlugHistory.objects.get_or_create(old_slug=old, interlocutor=person)


def claims_for_person(person):
    """Claims atribuidos: apariciones cuyo segmento pertenece a un hablante
    confirmado como esta persona en su post."""
    from .models import ClaimAppearance
    pairs = SpeakerNameProposal.objects.filter(confirmed=True, interlocutor=person) \
                                       .values_list('post_id', 'speaker_label')
    out = ClaimAppearance.objects.none()
    for post_id, label in pairs:
        out = out | ClaimAppearance.objects.filter(
            segment__post_id=post_id, segment__speaker_label=label)
    return out.select_related('claim', 'segment__post').distinct()
