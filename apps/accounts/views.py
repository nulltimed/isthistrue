from django.contrib import messages
from django.contrib.auth import login
from django.db import models
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import RegisterForm
from .models import RedeemCode
from . import turnstile


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        token = request.POST.get('cf-turnstile-response', '')
        if not turnstile.verify(token, request.META.get('REMOTE_ADDR')):
            messages.error(request, 'Verificación anti-bots fallida.')
        elif form.is_valid():
            user = form.save()
            from .verification import send_verification_email
            send_verification_email(user)
            messages.success(request, 'Cuenta creada. Revisa tu email y pulsa el '
                                      'enlace de verificación para poder entrar.')
            return redirect('login')
    else:
        form = RegisterForm()
    from django.conf import settings as dj_settings
    return render(request, 'accounts/register.html', {'form': form, 'debug': dj_settings.DEBUG, 'turnstile_site_key': dj_settings.TURNSTILE_SITE_KEY})


@login_required
def settings_view(request):
    """Panel de cuenta unico (foro+wiki): sliders +18 y opiniones."""
    u = request.user
    if request.method == 'POST':
        if u.is_adult:  # 14-17: el slider +18 ni aparece ni se procesa
            u.hide_adult = request.POST.get('hide_adult') == 'on'
        u.hide_opinions = request.POST.get('hide_opinions') == 'on'
        u.notify_mode = request.POST.get('notify_mode', u.notify_mode)
        u.allow_friend_requests = request.POST.get('allow_friend_requests') == 'on'
        u.accept_private_messages = request.POST.get('accept_private_messages') == 'on'
        if request.FILES.get('avatar'):
            u.avatar = request.FILES['avatar']
            u.avatar_approved = True
        u.save()
        if request.FILES.get('avatar'):
            from .tasks import check_avatar
            check_avatar.delay(u.pk)
        messages.success(request, 'Preferencias guardadas.')
        return redirect('account_settings')
    return render(request, 'accounts/settings.html', {'u': u})


@login_required
def claim_code(request):
    """/claim/ — canje de codigos ISTT-XXXX-XXXX."""
    if request.method == 'POST':
        raw = request.POST.get('code', '').strip().upper()
        code = RedeemCode.objects.filter(code=raw).first()
        if code and code.redeem(request.user):
            messages.success(request, f'Código canjeado: ahora eres {code.get_grants_level_display()}.')
            return redirect('/')
        messages.error(request, 'Código no válido o ya utilizado.')
    return render(request, 'accounts/claim.html')


@login_required
def delete_account(request):
    """Autoborrado RGPD con confirmacion de contraseña."""
    from django.contrib.auth import logout
    from .services import anonymize_user
    if request.method == 'POST':
        if request.user.check_password(request.POST.get('password', '')):
            anonymize_user(request.user)
            logout(request)
            messages.success(request, 'Tu cuenta ha sido eliminada.')
            return redirect('/')
        messages.error(request, 'Contraseña incorrecta.')
    return render(request, 'accounts/delete_account.html')


@login_required
def notifications(request):
    notes = request.user.notifications.all()[:50]
    request.user.notifications.filter(read=False).update(read=True)
    return render(request, 'accounts/notifications.html', {'notes': notes})


@login_required
def pm_inbox(request):
    """4.2 H8: buzon de mensajes privados (los mios, enviados y recibidos)."""
    from .models import PrivateMessage
    received = PrivateMessage.objects.filter(recipient=request.user)[:50]
    sent = PrivateMessage.objects.filter(sender=request.user)[:20]
    PrivateMessage.objects.filter(recipient=request.user, read=False).update(read=True)
    return render(request, 'accounts/pm_inbox.html', {'received': received, 'sent': sent})


@login_required
def pm_send(request, user_id):
    """4.2 H8: enviar MP. Reglas: buzon del destinatario abierto O remitente mod/root;
    los bloqueos mandan; el texto es Markdown con HTML escapado al mostrarse."""
    from .models import User, UserBlock, PrivateMessage
    from .services import notify
    target = User.objects.filter(pk=user_id, is_active=True).first()
    if not target or target == request.user:
        return redirect('pm_inbox')
    is_mod = request.user.is_staff or request.user.level == 'MOD'
    if not (target.accept_private_messages or is_mod):
        messages.error(request, 'Este usuario no acepta mensajes privados.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    if UserBlock.objects.filter(blocker=target, blocked=request.user).exists() and not is_mod:
        messages.error(request, 'No puedes enviar mensajes a este usuario.')
        return redirect(request.META.get('HTTP_REFERER', '/'))
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()[:8000]
        if body:
            PrivateMessage.objects.create(sender=request.user, recipient=target, body=body)
            notify(target, f'Mensaje privado de {request.user.username}', '/accounts/mensajes/')
            messages.success(request, 'Mensaje enviado.')
            return redirect('pm_inbox')
    return render(request, 'accounts/pm_send.html', {'target': target})


@login_required
def pm_report(request, pm_id):
    """4.2 H8 (salvaguarda de la factura): el destinatario eleva un MP a los mods."""
    from .models import PrivateMessage, User
    from .services import notify
    pm = PrivateMessage.objects.filter(pk=pm_id, recipient=request.user).first()
    if pm and request.method == 'POST' and not pm.reported:
        pm.reported = True
        pm.save(update_fields=['reported'])
        for mod in User.objects.filter(level='MOD', is_active=True) |                    User.objects.filter(is_superuser=True, is_active=True):
            notify(mod, f'MP reportado de {pm.sender.username} a {pm.recipient.username}: '
                        f'«{pm.body[:120]}»', '/accounts/mensajes/')
        messages.success(request, 'Mensaje reportado a moderación.')
    return redirect('pm_inbox')


@login_required
def notifications_poll(request):
    """4.2 D2: sondeo ligero de static/js/notify.js — no leidas mas nuevas que
    ?after=<id>, para el numerito de la campana y las notificaciones del NAVEGADOR
    (permiso opcional del usuario). No marca nada como leido."""
    from django.http import JsonResponse
    try:
        after = int(request.GET.get('after', 0))
    except ValueError:
        after = 0
    unread = request.user.notifications.filter(read=False)
    items = [{'id': n.pk, 'text': n.text, 'url': n.url}
             for n in unread.filter(pk__gt=after).order_by('pk')[:10]]
    return JsonResponse({'unread': unread.count(), 'items': items})


@login_required
def friends(request):
    from .models import Friendship, User, UserBlock
    from .services import notify
    me = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request':
            target = User.objects.filter(username=request.POST.get('username', '').strip(),
                                         is_active=True).first()
            blocked = target and (UserBlock.objects.filter(blocker=target, blocked=me).exists()
                                  or UserBlock.objects.filter(blocker=me, blocked=target).exists())
            if target and target != me and target.allow_friend_requests and not blocked:
                _, created = Friendship.objects.get_or_create(requester=me, addressee=target)
                if created:
                    notify(target, f'{me.username} te ha enviado una solicitud de amistad',
                           url='/accounts/amigos/')
                messages.success(request, 'Solicitud enviada.')
            else:
                messages.error(request, 'No se pudo enviar la solicitud.')
        elif action in ('accept', 'decline'):
            fr = Friendship.objects.filter(pk=request.POST.get('id'), addressee=me,
                                           status='PENDING').first()
            if fr:
                fr.status = 'ACCEPTED' if action == 'accept' else 'DECLINED'
                fr.save(update_fields=['status'])
        elif action == 'block':
            target = User.objects.filter(pk=request.POST.get('id')).first()
            if target and target != me:
                UserBlock.objects.get_or_create(blocker=me, blocked=target)
                Friendship.objects.filter(requester=target, addressee=me).delete()
                messages.success(request, 'Usuario bloqueado.')
        return redirect('friends')
    pending = Friendship.objects.filter(addressee=me, status='PENDING')
    accepted = Friendship.objects.filter(status='ACCEPTED').filter(
        models.Q(requester=me) | models.Q(addressee=me))
    return render(request, 'accounts/friends.html', {'pending': pending, 'accepted': accepted})


def verify_email(request, token):
    from .verification import verify_token
    user = verify_token(token)
    if user:
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        from .verification import send_welcome_email
        send_welcome_email(user)
        messages.success(request, 'Email verificado: ya puedes iniciar sesión.')
    else:
        messages.error(request, 'Enlace de verificación no válido o caducado.')
    return redirect('login')


def resend_verification(request):
    if request.method == 'POST':
        from .models import User
        from .verification import send_verification_email
        u = User.objects.filter(email__iexact=request.POST.get('email', '').strip(),
                                email_verified=False).first()
        if u:
            send_verification_email(u)
        messages.success(request, 'Si la cuenta existe y está sin verificar, '
                                  'hemos reenviado el enlace.')
    return redirect('login')
