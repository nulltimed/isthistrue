"""Chequeo de avatar con Haiku (vision) y resumen diario de notificaciones."""
from celery import shared_task
from django.conf import settings


@shared_task
def check_avatar(user_id):
    from .models import User
    from apps.panel.models import AuditLog
    user = User.objects.get(pk=user_id)
    if not user.avatar:
        return 'no_avatar'
    if settings.MOCK_AGENTS:
        return 'ok_mock'
    import base64, anthropic
    with user.avatar.open('rb') as f:
        data = base64.standard_b64encode(f.read()).decode()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(model=settings.MODEL_CHEAP, max_tokens=10,  # avatares: Haiku (decision de David, Fase 3.4)
        messages=[{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': data}},
            {'type': 'text', 'text': 'Responde SOLO "OK" o "REVISAR". REVISAR si hay desnudos, violencia, simbologia de odio o contenido inadecuado para un avatar publico.'}]}])
    verdict = ''.join(b.text for b in msg.content if getattr(b, 'type', '') == 'text').strip()
    if 'REVISAR' in verdict.upper():
        user.avatar_approved = False
        user.save(update_fields=['avatar_approved'])
        AuditLog.objects.create(action='avatar_flagged', detail=f'user {user.pk}')
    return verdict


def _lo_mejor_de_la_semana():
    """6.6: los bulos desmontados en los ultimos 7 dias, para el resumen
    semanal. Texto plano con enlaces a las fichas."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.wiki.models import Claim
    desde = timezone.now() - timedelta(days=7)
    rojos = list(Claim.objects.filter(color='RED', consolidated=True,
                                      created_at__gte=desde)
                 .exclude(slug__isnull=True).order_by('-pk')[:3])
    if not rojos:
        return ''
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    lineas = [f'- «{(c.title or c.text_original)[:90]}» → '
              f'{base}/wiki/claim/{c.slug}/' for c in rojos]
    return 'Los bulos desmontados esta semana:\n' + '\n'.join(lineas)


@shared_task
def send_daily_digests():
    from django.core.mail import send_mail
    from .models import User
    from django.utils import timezone
    hour = timezone.localtime().hour
    for user in User.objects.filter(notify_mode='DAILY', is_active=True,
                                    digest_hour=hour).exclude(email=''):
        pending = user.notifications.filter(read=False)[:20]
        if pending:
            body = '\n'.join(f'- {n.text}' for n in pending)
            send_mail('esestocierto: resumen diario', body,
                      settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    # 6.6: resumen SEMANAL — los VIERNES a la hora elegida (6.6-c, David:
    # «mejor el viernes, más punch»). Lleva los avisos pendientes Y lo mejor
    # de la semana, con el pie de servicios (regla de David 2026-11-09:
    # revenue en cada cambio — aqui, embudo, no venta).
    if timezone.localtime().weekday() != 4:
        return
    extra = _lo_mejor_de_la_semana()
    base = getattr(settings, 'SITE_URL', '').rstrip('/')
    pie = ('—\n¿Prisa por verificar un vídeo? Los créditos lo adelantan: '
           f'{base}/creditos/\nServicios para medios y empresas: {base}/servicios/')
    for user in User.objects.filter(notify_mode='WEEKLY', is_active=True,
                                    digest_hour=hour).exclude(email=''):
        pending = user.notifications.filter(read=False)[:30]
        partes = []
        if pending:
            partes.append('Tus avisos de la semana:\n'
                          + '\n'.join(f'- {n.text}' for n in pending))
        if extra:
            partes.append(extra)
        if partes:   # sin nada que contar, no se molesta a nadie
            send_mail('esestocierto: resumen semanal', '\n\n'.join(partes + [pie]),
                      settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)


@shared_task
def refund_failed_credit_advances():
    """6.1-f (orden de David, 2026-11-06): si un analisis adelantado o lanzado
    con creditos acaba FAILED, los creditos vuelven solos. Idempotente: corre a
    diario y no reembolsa dos veces (busca el apunte de devolucion por nota)."""
    from apps.accounts.models import CreditLedger
    from apps.accounts import credits as cred
    from apps.accounts.services import notify
    hechos = 0
    gastos = (CreditLedger.objects.filter(reason='ADVANCE', delta__lt=0,
                                          post__status='FAILED')
              .select_related('post', 'user'))
    for g in gastos:
        marca = f'reembolso-adv-{g.pk}'
        if CreditLedger.objects.filter(note=marca).exists():
            continue
        cred.grant(g.user, -g.delta, reason='ADMIN', note=marca)
        notify(g.user, f'El análisis que adelantaste («{(g.post.title or g.post.url)[:80]}») '
               f'falló: tus {-g.delta} crédito(s) se han devuelto.',
               url='/creditos/', kind='credit_refund')
        hechos += 1
    return hechos


@shared_task
def vet_org_signup(vet_pk):
    """6.3: escrutinio por IA del registro de una persona juridica."""
    from .signup_vetting import resolve_org_vetting
    return resolve_org_vetting(vet_pk)
