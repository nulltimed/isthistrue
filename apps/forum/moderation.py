"""
Moderacion en cascada (decision congelada tras la factura):
- TODO comentario pasa por Haiku (~0,0005 EUR). Si Haiku duda/marca -> Sonnet.
- 3 primeros comentarios de la cuenta: Sonnet DECIDE (bloquea/elimina); mod puede revertir.
- Del 4 en adelante: Sonnet solo ADVIERTE a moderadores; 48 h sin respuesta = aprobado.
"""
import json
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from apps.agents import client

HAIKU_SYSTEM = ('Eres un filtro de moderacion. Responde SOLO JSON: '
                '{"flag": true|false, "reason": str}. flag=true ante insultos graves, '
                'acoso, amenazas, spam, doxxing o incitacion al odio. Se tolerante '
                'con el desacuerdo vehemente: criticar ideas no es acosar personas.')
SONNET_SYSTEM = ('Eres el moderador de segundo nivel. Responde SOLO JSON: '
                 '{"action": "APPROVE"|"BLOCK", "reason": str}. BLOCK solo ante '
                 'violaciones claras (acoso, amenazas, odio, spam). Tono forense.')


@shared_task
def moderate_machina_post(machina_post_id):
    from machina.core.db.models import get_model
    from apps.forum.models import ModerationCase
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
        if novato:  # limpio, pero novato: se aprueba y cuenta como revisado
            post.approved = True
            post.save(update_fields=['approved'])
        return 'clean'

    sonnet = client.call_json(settings.MODEL_VERDICT, SONNET_SYSTEM,
                              f'MOTIVO HAIKU: {haiku.get("reason","")}\n\nCOMENTARIO:\n{text}',
                              max_tokens=200,
                              mock_payload={'action': 'APPROVE', 'reason': '[SIMULADO]'})
    if novato:
        blocked = sonnet.get('action') == 'BLOCK'
        post.approved = not blocked
        post.save(update_fields=['approved'])
        ModerationCase.objects.create(machina_post_id=post.pk, user=post.poster,
            kind='NOVICE_DECIDED', agent_action=sonnet.get('action', ''),
            agent_reason=sonnet.get('reason', ''), resolved=True)
        return f'novice_{sonnet.get("action")}'
    # Veterano: solo advertencia con reloj de 48 h
    ModerationCase.objects.create(machina_post_id=post.pk, user=post.poster,
        kind='WARNING', agent_action=sonnet.get('action', ''),
        agent_reason=sonnet.get('reason', ''),
        deadline=timezone.now() + timezone.timedelta(hours=48))
    _alert_mods(post)
    return 'warned'


def _alert_mods(post):
    from apps.accounts.models import User
    from apps.accounts.services import notify
    for mod in User.objects.filter(level='MOD', is_active=True):
        notify(mod, 'Comentario con advertencia de moderación (48 h para revisar)',
               url=f'/foro/')


@shared_task
def resolve_expired_warnings():
    """Beat horario: advertencias sin respuesta de mod en 48 h -> se dan por positivas."""
    from apps.forum.models import ModerationCase
    expired = ModerationCase.objects.filter(kind='WARNING', resolved=False,
                                            deadline__lt=timezone.now())
    n = expired.update(resolved=True, outcome='AUTO_APPROVED')
    return n
