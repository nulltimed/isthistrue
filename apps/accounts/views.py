from django.contrib import messages
from django.contrib.auth import login
from django.db import models
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import RegisterForm
from .models import RedeemCode, UI_LANGUAGES
from . import turnstile


def register(request):
    # 4.3-A.1 K6 (decision de David): el superusuario puede cerrar el registro
    # desde el panel (registration_open=0). Cerrado: ni formulario ni altas.
    from apps.panel.models import SystemSetting
    if not SystemSetting.get_int('registration_open', 1):
        messages.info(request, 'El registro está cerrado temporalmente. Vuelve pronto.')
        return redirect('index')
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


def set_language_pref(request):
    """4.4-A: el selector ES·EN de la cabecera.

    Hace lo de siempre (cookie de idioma, via la vista de Django) y ADEMAS, si
    hay cuenta, guarda la eleccion en el perfil. Asi el idioma le sigue al
    usuario aunque entre desde otro ordenador, y Ajustes y la cabecera no se
    contradicen nunca: son la misma decision escrita en el mismo sitio.
    """
    from django.conf import settings as dj_settings
    from django.views.i18n import set_language
    lang = request.POST.get('language', '')
    if request.method == 'POST' and request.user.is_authenticated \
            and lang in dict(dj_settings.LANGUAGES):
        request.user.language = lang
        request.user.save(update_fields=['language'])
    return set_language(request)


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
        # 4.3-A J5: avisos por tipo, firma, silencio nocturno y hora del resumen
        PREF_KEYS = ['post_phase', 'thread_replies', 'mentions', 'claim_color',
                     'trending', 'post_votes', 'project_news']
        u.notify_prefs = {k: request.POST.get('pref_' + k) == 'on' for k in PREF_KEYS}
        # 4.3-A.2 L6 (quiz 78): sonido de los bocadillos — OFF por defecto
        u.notify_prefs['toast_sound'] = request.POST.get('toast_sound') == 'on'
        u.quiet_night = request.POST.get('quiet_night') == 'on'
        u.signature = request.POST.get('signature', '').strip()[:200]
        # 4.4-A: idioma de la interfaz ('' = automatico segun el navegador)
        lang = request.POST.get('language', '')
        if lang in dict(UI_LANGUAGES):
            u.language = lang
        dh = request.POST.get('digest_hour', '')
        if dh.isdigit() and 0 <= int(dh) <= 23:
            u.digest_hour = int(dh)
        if request.FILES.get('avatar'):
            u.avatar = request.FILES['avatar']
            u.avatar_approved = True
        u.save()
        if request.FILES.get('avatar'):
            from .tasks import check_avatar
            check_avatar.delay(u.pk)
        messages.success(request, 'Preferencias guardadas.')
        return redirect('account_settings')
    PREF_ROWS = [
        ('post_phase', 'Mi post cambia de fase', 'Transcripción lista, veredictos publicados…'),
        ('thread_replies', 'Nuevos mensajes en posts suscritos', 'La conversación sigue sin ti: te avisa.'),
        ('mentions', 'Menciones y citas (@tu-nombre)', 'Alguien te nombra o te cita en un hilo.'),
        ('claim_color', 'Un claim que sigo cambia de semáforo', 'El color de la wiki se mueve.'),
        ('trending', 'Un post suscrito entra en Trending', 'El fuego te llega a la campana.'),
        ('post_votes', 'Votos a mis posts', 'Cada ▲ que recibes, si quieres saberlo.'),
        ('project_news', 'Novedades del proyecto', 'Cuando la plataforma estrene algo.'),
        # 4.3-C: sin nombre no hay ficha en la wiki; este aviso pide ayuda para
        # identificar a los hablantes justo cuando el análisis va a dar veredictos.
        ('speakers_unnamed', 'Hablantes sin identificar',
         'Un análisis que sigues va a dar veredictos y aún no se sabe quién habla.'),
        # 4.3-D: aviso de coste en vídeos que pasan del tramo gratuito.
        ('long_video_cost', 'Coste de los vídeos largos',
         'Un análisis que sigues supera los minutos gratuitos y te decimos lo que cuesta.'),
    ]
    pref_rows = [(k, lbl, hint, u.wants(k)) for k, lbl, hint in PREF_ROWS]
    # 5.0-E: estado de la verificacion en dos pasos para la seccion Cuenta.
    from django_otp.plugins.otp_totp.models import TOTPDevice
    otp_activo = TOTPDevice.objects.filter(user=u, confirmed=True).exists()
    return render(request, 'accounts/settings.html',
                  {'u': u, 'pref_rows': pref_rows, 'hours': range(24),
                   'otp_activo': otp_activo})


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
    """4.3-A J5: avisos AGRUPADOS (mismo texto+destino = una linea con contador),
    con botones de vaciar todo y de pausar 24 horas."""
    from django.utils import timezone
    if request.method == 'POST':
        if 'clear' in request.POST:
            request.user.notifications.all().delete()
            messages.success(request, 'Avisos vaciados.')
        elif 'pause' in request.POST:
            request.user.notifications_paused_until = timezone.now() + timezone.timedelta(hours=24)
            request.user.save(update_fields=['notifications_paused_until'])
            messages.success(request, 'Emails de aviso en pausa 24 horas (la campana sigue).')
        elif 'resume' in request.POST:
            request.user.notifications_paused_until = None
            request.user.save(update_fields=['notifications_paused_until'])
            messages.success(request, 'Pausa retirada.')
        return redirect('notifications')
    grouped, seen = [], {}
    for n in request.user.notifications.all()[:200]:
        key = (n.text, n.url)
        if key in seen:
            seen[key]['count'] += 1
        else:
            seen[key] = {'n': n, 'count': 1}
            grouped.append(seen[key])
    request.user.notifications.filter(read=False).update(read=True)
    paused = (request.user.notifications_paused_until
              and request.user.notifications_paused_until > timezone.now())
    return render(request, 'accounts/notifications.html',
                  {'grouped': grouped[:60], 'paused': paused})


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
        elif action == 'unblock':   # 5.0-E: el candado ya existia; faltaba la llave
            UserBlock.objects.filter(blocker=me,
                                     blocked_id=request.POST.get('id')).delete()
            messages.success(request, 'Usuario desbloqueado.')
        return redirect('friends')
    pending = Friendship.objects.filter(addressee=me, status='PENDING')
    accepted = Friendship.objects.filter(status='ACCEPTED').filter(
        models.Q(requester=me) | models.Q(addressee=me))
    blocks = UserBlock.objects.filter(blocker=me).select_related('blocked')
    return render(request, 'accounts/friends.html',
                  {'pending': pending, 'accepted': accepted, 'blocks': blocks})


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


# ------------------------- 5.0-E: la cuenta completa -------------------------
# Los seis huecos que faltaban (orden de David, 2026-09-03): recuperar la
# contrasena olvidada, cambiarla desde dentro, cambiar el email con
# verificacion, exportar los datos (portabilidad RGPD), interfaz de bloqueos
# y 2FA opcional por TOTP.

from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy


class PasswordResetViewES(auth_views.PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'emails/password_reset.txt'
    subject_template_name = 'emails/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')


class PasswordResetConfirmViewES(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')


class PasswordChangeViewES(auth_views.PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('account_settings')

    def form_valid(self, form):
        messages.success(self.request, 'Contraseña cambiada.')
        return super().form_valid(form)


EMAIL_CHANGE_SALT = 'email-change'
EMAIL_CHANGE_MAX_AGE = 72 * 3600


@login_required
def email_change(request):
    """El enlace de confirmacion viaja al email NUEVO: quien no controla ese
    buzon no puede quedarselo. El token firmado lleva el email dentro, asi que
    no hace falta campo pendiente en el modelo."""
    from django.core import signing
    from django.core.mail import send_mail
    from django.core.validators import validate_email
    from django.core.exceptions import ValidationError
    from django.conf import settings as dj_settings
    from .models import User
    from .verification import _site_host
    if request.method != 'POST':
        return redirect('account_settings')
    nuevo = request.POST.get('new_email', '').strip().lower()
    try:
        validate_email(nuevo)
    except ValidationError:
        messages.error(request, 'Ese email no parece válido.')
        return redirect('account_settings')
    if User.objects.filter(email__iexact=nuevo).exists():
        messages.error(request, 'Ese email ya está en uso.')
        return redirect('account_settings')
    token = signing.dumps({'uid': request.user.pk, 'email': nuevo},
                          salt=EMAIL_CHANGE_SALT)
    url = f'https://{_site_host()}/accounts/email/confirmar/{token}/'
    send_mail('Confirma tu email nuevo — esestocierto.com',
              f'Hola {request.user.username}:\n\nPulsa para confirmar que este '
              f'es tu email nuevo:\n{url}\n\nEl enlace caduca en 72 horas. Si '
              'no pediste este cambio, ignora este mensaje: tu email actual '
              'sigue siendo el de siempre.',
              dj_settings.DEFAULT_FROM_EMAIL, [nuevo],
              fail_silently=False)
    messages.success(request, f'Te hemos escrito a {nuevo} con el enlace de '
                              'confirmación. Tu email no cambia hasta que lo pulses.')
    return redirect('account_settings')


def email_change_confirm(request, token):
    from django.core import signing
    from .models import User
    try:
        data = signing.loads(token, salt=EMAIL_CHANGE_SALT,
                             max_age=EMAIL_CHANGE_MAX_AGE)
    except signing.BadSignature:
        messages.error(request, 'El enlace no es válido o ha caducado.')
        return redirect('login')
    user = User.objects.filter(pk=data.get('uid')).first()
    nuevo = data.get('email', '')
    if not user or User.objects.filter(email__iexact=nuevo).exclude(pk=user.pk).exists():
        messages.error(request, 'El enlace no es válido o el email ya está en uso.')
        return redirect('login')
    user.email = nuevo
    user.email_verified = True
    user.save(update_fields=['email', 'email_verified'])
    messages.success(request, 'Email actualizado.')
    return redirect('account_settings' if request.user.is_authenticated else 'login')


@login_required
def export_data(request):
    """Portabilidad (RGPD art. 20): lo que el usuario nos dio, en JSON legible.
    Solo SUS datos: los mensajes recibidos son de otros y no se exportan."""
    import json
    from django.http import HttpResponse
    from apps.analysis.models import Post
    u = request.user
    datos = {
        'perfil': {
            'usuario': u.username, 'email': u.email,
            'fecha_alta': u.date_joined.isoformat(),
            'fecha_nacimiento': u.birth_date.isoformat() if u.birth_date else None,
            'idioma': u.language, 'firma': u.signature,
            'karma': u.karma, 'nivel': u.effective_level(),
        },
        'ajustes': {
            'ocultar_adulto': u.hide_adult, 'difuminar_opiniones': u.hide_opinions,
            'modo_avisos': u.notify_mode, 'preferencias_avisos': u.notify_prefs,
            'silencio_nocturno': u.quiet_night, 'hora_resumen': u.digest_hour,
            'acepta_mensajes_privados': u.accept_private_messages,
            'permite_solicitudes_amistad': u.allow_friend_requests,
        },
        'posts_enviados': [
            {'url': p.url, 'titulo': p.title, 'fecha': p.created_at.isoformat(),
             'opinion_inicial': p.author_opinion}
            for p in Post.objects.filter(author=u).order_by('created_at')],
        'mensajes_privados_enviados': [
            {'para': pm.recipient.username, 'texto': pm.body,
             'fecha': pm.created_at.isoformat()}
            for pm in u.pm_sent.order_by('created_at')],
        'amistades': [
            {'con': (f.addressee if f.requester_id == u.pk else f.requester).username,
             'estado': f.status}
            for f in (u.friend_requests_sent.all() | u.friend_requests_received.all())],
        'bloqueos': [b.blocked.username for b in u.blocks.all()],
    }
    try:
        from machina.core.db.models import get_model
        MPost = get_model('forum_conversation', 'Post')
        datos['mensajes_del_foro'] = [
            {'asunto': mp.subject, 'texto': str(mp.content),
             'fecha': mp.created.isoformat()}
            for mp in MPost.objects.filter(poster=u).order_by('created')]
    except Exception:
        datos['mensajes_del_foro'] = []
    cuerpo = json.dumps(datos, ensure_ascii=False, indent=2)
    resp = HttpResponse(cuerpo, content_type='application/json; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="esestocierto-{u.username}.json"'
    return resp


def _dispositivo_confirmado(user):
    from django_otp.plugins.otp_totp.models import TOTPDevice
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


@login_required
def otp_setup(request):
    """Activar 2FA: se crea un dispositivo SIN confirmar, se muestra el QR y
    solo queda activo cuando el usuario demuestra un codigo valido."""
    import qrcode
    import qrcode.image.svg
    from io import BytesIO
    from django_otp.plugins.otp_totp.models import TOTPDevice
    if _dispositivo_confirmado(request.user):
        messages.info(request, 'La verificación en dos pasos ya está activa.')
        return redirect('account_settings')
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if not device:
        device = TOTPDevice.objects.create(user=request.user, name='app',
                                           confirmed=False)
    if request.method == 'POST':
        if device.verify_token(request.POST.get('code', '').strip()):
            device.confirmed = True
            device.save(update_fields=['confirmed'])
            messages.success(request, 'Verificación en dos pasos ACTIVADA. '
                                      'A partir de ahora, al entrar se te pedirá el código.')
            return redirect('account_settings')
        messages.error(request, 'Código incorrecto. Prueba con el siguiente que muestre la app.')
    buf = BytesIO()
    qrcode.make(device.config_url,
                image_factory=qrcode.image.svg.SvgPathImage).save(buf)
    svg = buf.getvalue().decode()
    if svg.startswith('<?xml'):       # la declaracion XML no va incrustada en HTML
        svg = svg.split('?>', 1)[1].lstrip()
    return render(request, 'accounts/otp_setup.html',
                  {'qr_svg': svg, 'secret_url': device.config_url})


@login_required
def otp_disable(request):
    from django_otp.plugins.otp_totp.models import TOTPDevice
    device = _dispositivo_confirmado(request.user)
    if request.method == 'POST' and device:
        if device.verify_token(request.POST.get('code', '').strip()):
            TOTPDevice.objects.filter(user=request.user).delete()
            messages.success(request, 'Verificación en dos pasos desactivada.')
        else:
            messages.error(request, 'Código incorrecto: la 2FA sigue activa.')
    return redirect('account_settings')


def otp_verify(request):
    """Segundo paso del login: la contraseña ya se comprobo, falta el codigo."""
    from django.conf import settings as dj_settings
    from .models import User
    uid = request.session.get('otp_user_pk')
    user = User.objects.filter(pk=uid).first() if uid else None
    if not user:
        return redirect('login')
    if request.method == 'POST':
        device = _dispositivo_confirmado(user)
        if device and device.verify_token(request.POST.get('code', '').strip()):
            from django_otp import login as otp_login
            backend = request.session.pop('otp_backend',
                                          dj_settings.AUTHENTICATION_BACKENDS[0])
            del request.session['otp_user_pk']
            destino = request.session.pop('otp_next', '') or '/'
            login(request, user, backend=backend)
            otp_login(request, device)
            return redirect(destino)
        messages.error(request, 'Código incorrecto.')
    return render(request, 'accounts/otp_verify.html', {'username': user.username})
