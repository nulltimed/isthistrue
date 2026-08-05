"""
Moderacion (rediseño congelado): SOLO Haiku (~0,0005 EUR/comentario).
- Limpio -> publicado.
- Marcado + cuenta novata (<3 comentarios) -> BLOQUEADO automaticamente.
- Marcado + cuenta veterana -> publicado con expediente (WARNING).
- SIEMPRE se notifica a los moderadores si existen; el mod puede revertir en el foro.
- Sin moderadores activos: la decision automatica de Haiku es DEFINITIVA.
- Expedientes WARNING sin respuesta en 48 h -> se dan por positivos (regla congelada).
"""
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.agents import client

HAIKU_SYSTEM = ('Eres un filtro de moderacion. Responde SOLO JSON: '
                '{"flag": true|false, "reason": str}. flag=true ante insultos graves, '
                'acoso, amenazas, spam, doxxing o incitacion al odio. Se tolerante '
                'con el desacuerdo vehemente: criticar ideas no es acosar personas.')


def _active_mods():
    from apps.accounts.models import User
    return list(User.objects.filter(level='MOD', is_active=True))


@shared_task
def moderate_machina_post(machina_post_id):
    from machina.core.db.models import get_model
    from apps.forum.models import ModerationCase
    from apps.accounts.services import notify
    MPost = get_model('forum_conversation', 'Post')
    post = MPost.objects.filter(pk=machina_post_id).first()
    if not post or not post.poster:
        return 'skip'
    text = str(post.content)[:4000]
    haiku = client.call_json(settings.MODEL_CHEAP, HAIKU_SYSTEM, text,
                             max_tokens=100, mock_payload={'flag': False, 'reason': ''})
    prior = MPost.objects.filter(poster=post.poster, approved=True).exclude(pk=post.pk).count()
    novato = prior < 3

    if not haiku.get('flag'):
        if novato:
            post.approved = True
            post.save(update_fields=['approved'])
        return 'clean'

    mods = _active_mods()
    if novato:
        post.approved = False  # decision automatica (provisional si hay mods; definitiva si no)
        post.save(update_fields=['approved'])
        kind, outcome = 'NOVICE_DECIDED', ('' if mods else 'AUTO_FINAL')
    else:
        kind, outcome = 'WARNING', ''
    ModerationCase.objects.create(machina_post_id=post.pk, user=post.poster, kind=kind,
        agent_action='BLOCK' if novato else 'WARN',
        agent_reason=haiku.get('reason', '')[:300],
        deadline=None if novato else timezone.now() + timezone.timedelta(hours=48),
        resolved=not mods, outcome=outcome)
    for mod in mods:
        notify(mod, f'Moderación: comentario {"bloqueado" if novato else "con advertencia"} '
                    f'por el agente — puedes revertirlo', url='/foro/')
    return 'flagged'


@shared_task
def resolve_expired_warnings():
    """Beat horario: advertencias sin respuesta de mod en 48 h -> positivas."""
    from apps.forum.models import ModerationCase
    expired = ModerationCase.objects.filter(kind='WARNING', resolved=False,
                                            deadline__lt=timezone.now())
    return expired.update(resolved=True, outcome='AUTO_APPROVED')
