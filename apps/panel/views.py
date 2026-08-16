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


SETTINGS_DEF = [
    # 4.3-A.3 M3 (decision de David): los ajustes del panel con nombre y apellidos.
    # kind: 'bool' = toggle (guarda 1/0); 'num' = campo numerico.
    ('registration_open', 'Permitir registro de nuevos usuarios',
     'Apagado: nadie nuevo puede crear cuenta; la página de registro avisa y vuelve a portada.', 'bool'),
    ('opinion_ratio_percent', 'Umbral de opinión (%)',
     'Porcentaje de frases de opinión a partir del cual el clasificador sugiere Off-Topic.', 'num'),
    ('minutes_per_factual_claim', 'Minutos por claim factual',
     'Densidad mínima: un claim verificable por cada X minutos de vídeo.', 'num'),
    ('votes_to_validate', 'Votos para validar',
     'Votos de la comunidad que sacan un post de la cuarentena.', 'num'),
    ('votes_to_rescue', 'Votos para rescatar',
     'Votos que devuelven un post de Off-Topic a Principal.', 'num'),
    ('validation_window_days', 'Ventana de validación (días)',
     'Días de plazo antes de que la validación caduque.', 'num'),
    ('startup_mode_min_users', 'Modo arranque hasta N usuarios',
     'Con menos usuarios que esto, un solo voto de moderador valida.', 'num'),
    ('donation_goal_eur', 'Meta de donaciones (€)',
     'El objetivo que muestra el termómetro del banner.', 'num'),
]


@staff_member_required
def settings_panel(request):
    """Umbrales vivos: algoritmo, votaciones, modo arranque, puerta del registro."""
    if request.method == 'POST':
        for key, _label, _hint, kind in SETTINGS_DEF:
            if kind == 'bool':
                value = '1' if request.POST.get(key) == 'on' else '0'
            elif key in request.POST and request.POST[key].strip():
                value = request.POST[key].strip()
            else:
                continue
            SystemSetting.objects.update_or_create(key=key, defaults={'value': value})
        AuditLog.objects.create(user=request.user, action='update_settings')
        messages.success(request, 'Ajustes guardados.')
        return redirect('panel_settings')
    rows = []
    for key, label, hint, kind in SETTINGS_DEF:
        obj = SystemSetting.objects.filter(key=key).first()
        rows.append({'key': key, 'label': label, 'hint': hint, 'kind': kind,
                     'value': obj.value if obj else ''})
    # 4.3-A.5 O4 (petición imperativa de David): el toggle de registro se saca a una
    # sección DESTACADA arriba del panel, aparte de los umbrales técnicos.
    reg = next((r for r in rows if r['key'] == 'registration_open'), None)
    others = [r for r in rows if r['key'] != 'registration_open']
    return render(request, 'panel/settings.html', {'rows': others, 'reg': reg})


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


@staff_member_required
def donations_panel(request):
    from .models import Donation, SystemSetting
    if request.method == 'POST':
        amt = request.POST.get('amount', '').replace(',', '.')
        try:
            if float(amt) <= 0:
                raise ValueError('importe no positivo')  # 4.1 B3: cantidad valida obligatoria
            Donation.objects.create(amount_eur=float(amt),
                method=request.POST.get('method', 'PAYPAL'),
                note=request.POST.get('note', '')[:200])
            AuditLog.objects.create(user=request.user, action='donation_add', detail=amt)
            messages.success(request, 'Donación registrada: el depósito ha crecido.')
        except ValueError:
            messages.error(request, 'Importe no válido.')
        return redirect('panel_donations')
    items = Donation.objects.order_by('-created_at')[:100]
    return render(request, 'panel/donations.html', {'items': items})


@staff_member_required
def moderators_panel(request):
    """4.2 H6: nombrar y retirar moderadores por nickname O email (solo superusuario)."""
    from apps.accounts.models import User
    if not request.user.is_superuser:
        return redirect('panel_codes')
    if request.method == 'POST':
        ident = request.POST.get('ident', '').strip()
        action = request.POST.get('action', 'add')
        target = (User.objects.filter(username__iexact=ident).first()
                  or User.objects.filter(email__iexact=ident).first())
        if not target:
            messages.error(request, f'No existe ningún usuario con «{ident}».')
        elif target.is_superuser:
            messages.error(request, 'El superusuario ya es moderador supremo por definición.')
        elif action == 'add':
            target.level = 'MOD'
            target.save(update_fields=['level'])
            messages.success(request, f'{target.username} nombrado moderador.')
        else:
            target.level = 'CONTRIB'  # al retirar conserva confianza, no el mando
            target.save(update_fields=['level'])
            messages.success(request, f'{target.username} ya no es moderador.')
        return redirect('panel_moderators')
    from apps.accounts.models import User as U
    mods = U.objects.filter(level='MOD', is_active=True).order_by('username')
    return render(request, 'panel/moderators.html', {'mods': mods})


@staff_member_required
def moderator_settings_panel(request):
    """4.2 H7: subseccion «Moderador» del panel — el superusuario tambien es
    moderador supremo. Aloja los ajustes de moderacion independientes del resto;
    los mods la veran cuando llegue su panel (4.4). Hoy: los umbrales vivos."""
    from apps.panel.models import SystemSetting
    KEYS = [('segment_opus_downvotes', 'Votos ▼ por oración para re-análisis Opus'),
            ('message_sensitive_reports', 'Reportes para difuminar un mensaje'),
            ('trending_votes_threshold', 'Votos para Trending'),
            ('trending_window_days', 'Ventana de Trending (días)')]
    if request.method == 'POST':
        for key, _label in KEYS:
            raw = request.POST.get(key, '').strip()
            if raw.isdigit() and int(raw) > 0:
                SystemSetting.objects.update_or_create(key=key, defaults={'value': raw})
        messages.success(request, 'Ajustes de moderación guardados.')
        return redirect('panel_moderator_settings')
    values = [(key, label, SystemSetting.get_int(key, 5)) for key, label in KEYS]
    return render(request, 'panel/moderator_settings.html', {'values': values})
