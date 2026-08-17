"""Nombrado participativo (diseño de David): votos ponderados; el moderador pesa
mas y desempata (SystemSetting mod_vote_weight=5). Al confirmar: se crea/asigna
el Interlocutor (SOLO figura publica tiene pagina), con 301 si cambia el slug."""
from django.utils.text import slugify
from apps.panel.models import SystemSetting
from .models import (Interlocutor, InterlocutorSlugHistory,
                     SpeakerNameProposal, SpeakerNameVote)

CONFIRM_POINTS = 'name_confirm_points'  # por defecto 5 puntos ponderados


def points_of(proposal):
    """Puntos ponderados de una propuesta. El voto de un MODERADOR o del
    SUPERUSUARIO vale por 5 (SystemSetting mod_vote_weight): confirma en
    solitario. Lo calcula SpeakerNameVote.weight()."""
    return sum(v.weight() for v in proposal.votes.select_related('user'))


def times_proposed(proposal):
    """Cuantas veces se ha propuesto ESE MISMO nombre en toda la plataforma.
    David: "por votación, wikidata sobre todo y repetición del nombre"."""
    return SpeakerNameProposal.objects.filter(
        candidate_name__iexact=proposal.candidate_name).count()


def rank_key(proposal):
    """Orden de mando para elegir el nombre de un hablante (4.3-C, decision de
    David), de mayor a menor peso:
      1. Tener QID de Wikidata. Una propuesta identificada gana SIEMPRE a una
         escrita a mano, aunque empaten a puntos.
      2. Los puntos ponderados (el moderador pesa 5).
      3. La repeticion del nombre en la plataforma.
    """
    return (1 if proposal.wikidata_id else 0, points_of(proposal),
            times_proposed(proposal))


def vote_proposal(proposal, user):
    if not (user.is_contrib_plus() or user.is_superuser):
        return False, 'Necesitas nivel Contribuidor o superior.'
    SpeakerNameVote.objects.get_or_create(proposal=proposal, user=user)
    needed = SystemSetting.get_int(CONFIRM_POINTS, 5)
    # Gana la MEJOR propuesta de ese hablante, no necesariamente la votada: si
    # una con QID iguala en puntos a una escrita a mano, se confirma la del QID.
    hermanas = list(SpeakerNameProposal.objects.filter(
        post=proposal.post, speaker_label=proposal.speaker_label))
    mejor = max(hermanas, key=rank_key)
    puntos_mejor = points_of(mejor)
    if puntos_mejor >= needed and not mejor.confirmed:
        _confirm(mejor)
        return True, f'Confirmado: {mejor.candidate_name}.'
    points = points_of(proposal)
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
    # 4.3-C — quien tiene pagina y quien no:
    # Con QID, Wikidata ya certifico que es una PERSONA (filtro P31=Q5) y publica
    # lo bastante para tener ficha: figura publica, pagina abierta.
    # Sin QID es un nombre escrito a mano, que podria ser un particular: queda en
    # revision (None) y NO genera pagina. El candado congelado manda: los
    # particulares jamas tienen pagina ni nombre en la URL.
    return Interlocutor.objects.create(
        name=name, slug=slug, base_slug=base, wikidata_id=qid,
        is_public_figure=True if qid else None,
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
    # 4.3-C (David): "hasta que esa persona/hablante se identifica: entonces se
    # crea/actualiza la página de la persona". La ficha se arma en vivo desde
    # claims_for_person(), asi que confirmar YA la actualiza; lo que falta es
    # refrescar los datos de Wikidata si la propuesta traia foto o descripcion
    # mejores, y avisar a quien sigue el post.
    cambios = []
    if proposal.photo_url and not person.photo_url:
        person.photo_url = proposal.photo_url
        cambios.append('photo_url')
    if proposal.description and not person.description:
        person.description = proposal.description
        cambios.append('description')
    if not person.base_slug:
        person.base_slug = slugify(person.name)[:150]
        cambios.append('base_slug')
    if cambios:
        person.save(update_fields=cambios)
    _notify_person_page(proposal, person)
    return person


def _notify_person_page(proposal, person):
    """Aviso a quien voto o sigue el post: ese hablante ya tiene ficha."""
    from apps.accounts.services import notify
    from apps.analysis.models import ValidationVote
    post = proposal.post
    if person.is_public_figure is not True:
        return
    destinatarios = {v.user for v in ValidationVote.objects.filter(post=post)
                     .select_related('user')}
    destinatarios |= {s.user for s in post.subscriptions.select_related('user')}
    for u in destinatarios:
        notify(u, f'{person.name} ya tiene ficha en la wiki: sus afirmaciones de '
                  f'«{post.title or post.url}» ya están atribuidas.',
               url=f'/persona/{person.slug}/', kind='speakers_unnamed')


def rename_interlocutor(person, new_name):
    """Renombrado con redireccion 301 permanente (candado congelado)."""
    old = person.slug
    person.name = new_name
    person.slug = slugify(new_name)[:160]
    person.base_slug = slugify(new_name)[:150]   # 4.3-C: la raiz sigue al nombre
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
