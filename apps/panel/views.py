from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import redirect, render
from apps.accounts.models import RedeemCode
from .models import AuditLog, CodeBatch, SystemSetting
from .tasks import BATCH_BG_THRESHOLD, generate_code_batch


@staff_member_required
def codes(request):
    """Pestaña Codigos: generar lotes (1 a 1.000.000), listar, revocar (silencioso)."""
    if request.method == 'POST':
        if 'revoke' in request.POST:
            code = RedeemCode.objects.filter(pk=request.POST['revoke']).first()
            if code:
                code.revoke()  # silencioso: sin email
                AuditLog.objects.create(user=request.user, action='revoke_code',
                                        detail=code.code)
                messages.success(request, 'Código revocado (sin notificación).')
        else:
            level = request.POST.get('level', 'CONTRIB')
            count = max(1, min(1_000_000, int(request.POST.get('count', '1'))))
            batch = CodeBatch.objects.create(level=level, count=count,
                                             created_by=request.user)
            AuditLog.objects.create(user=request.user, action='generate_codes',
                                    detail=f'{count} x {level}')
            if count > BATCH_BG_THRESHOLD:
                generate_code_batch.delay(batch.pk)
                messages.info(request, 'Lote grande: se genera en segundo plano; '
                                       'el enlace de descarga aparecerá aquí al terminar.')
            else:
                generate_code_batch(batch.pk)  # sincrono: instantaneo
                messages.success(request, 'Lote generado.')
        return redirect('panel_codes')
    batches = CodeBatch.objects.order_by('-created_at')[:50]
    redeemed = RedeemCode.objects.filter(redeemed_by__isnull=False,
                                         revoked=False).order_by('-redeemed_at')[:100]
    return render(request, 'panel/codes.html', {'batches': batches, 'redeemed': redeemed})


@staff_member_required
def settings_panel(request):
    """Umbrales vivos: algoritmo, votaciones, modo arranque."""
    keys = ['opinion_ratio_percent', 'minutes_per_factual_claim', 'votes_to_validate',
            'votes_to_rescue', 'validation_window_days', 'startup_mode_min_users',
            'donation_goal_eur']
    if request.method == 'POST':
        for k in keys:
            if k in request.POST:
                SystemSetting.objects.update_or_create(key=k,
                    defaults={'value': request.POST[k].strip()})
        AuditLog.objects.create(user=request.user, action='update_settings')
        messages.success(request, 'Ajustes guardados.')
        return redirect('panel_settings')
    current = {k: SystemSetting.objects.filter(key=k).first() for k in keys}
    return render(request, 'panel/settings.html', {'current': current})


@staff_member_required
def staging_invites(request):
    """Invitados del espejo (decision de David): email + permisos, gestionado aqui."""
    import secrets
    from django.conf import settings as dj
    from django.core.mail import send_mail
    from apps.accounts.models import StagingInvite, User
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        can_admin = request.POST.get('can_admin') == 'on'
        if email:
            inv = StagingInvite.objects.create(email=email, can_admin=can_admin,
                                               token=secrets.token_urlsafe(24))
            existing = User.objects.filter(email=email).first()
            if existing:
                existing.staging_invited = True
                existing.save(update_fields=['staging_invited'])
            send_mail('Invitación al espejo de pruebas de isthistrue',
                      'Has sido invitado al entorno de pruebas: '
                      'https://stagings.xyztserver.com\n'
                      'Entra con tu cuenta (o créala) usando este mismo email.',
                      dj.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
            AuditLog.objects.create(user=request.user, action='staging_invite', detail=email)
            messages.success(request, 'Invitación enviada.')
        return redirect('panel_staging')
    invites = StagingInvite.objects.order_by('-created_at')[:50]
    return render(request, 'panel/staging.html', {'invites': invites})


@staff_member_required
def complaints(request):
    from .models import ContentComplaint
    if request.method == 'POST':
        c = ContentComplaint.objects.filter(pk=request.POST.get('id')).first()
        if c:
            c.status = request.POST.get('status', c.status)
            c.save(update_fields=['status'])
            AuditLog.objects.create(user=request.user, action='complaint_update',
                                    detail=f'#{c.pk} -> {c.status}')
        return redirect('panel_complaints')
    items = ContentComplaint.objects.order_by('-created_at')[:100]
    return render(request, 'panel/complaints.html', {'items': items})
