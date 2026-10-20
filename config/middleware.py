"""Middlewares propios. (HostLanguageMiddleware eliminado en Fase 3.9: el idioma
lo decide LocaleMiddleware — cookie del selector → Accept-Language → 'es'.
Nada usaba request.site_section fuera de aquel middleware: verificado con grep.)"""


class UserLanguageMiddleware:
    """4.4-A: si el usuario eligio idioma en Ajustes, ESE manda.

    LocaleMiddleware ya resolvio antes cookie -> Accept-Language -> 'es', pero
    corre por encima de la autenticacion y no sabe quien es el visitante. Este
    va DESPUES de AuthenticationMiddleware y solo pisa la decision cuando hay
    una eleccion explicita guardada en el perfil. Sin cuenta, no hace nada.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.utils import translation
        lang = getattr(getattr(request, 'user', None), 'language', '') or ''
        if lang:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
        return self.get_response(request)


class StagingAccessMiddleware:
    """Espejo de pruebas: solo entran invitados logueados (gestion desde el panel).
    En produccion (STAGING_MODE=false) no hace nada."""
    EXEMPT = ('/accounts/login', '/accounts/logout', '/static/', '/healthz')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if settings.STAGING_MODE:
            path = request.path
            if not any(path.startswith(p) for p in self.EXEMPT):
                u = getattr(request, 'user', None)
                allowed = u and u.is_authenticated and (
                    u.is_superuser or getattr(u, 'staging_invited', False))
                if not allowed:
                    from django.shortcuts import redirect
                    return redirect('/accounts/login/?next=' + path)
        return self.get_response(request)


class PrivateSiteMiddleware:
    """5.31 (orden de David, 2026-10-20, 2ª version): la WEB PRIVADA. Mientras el
    ajuste `site_private` este encendido, cualquier direccion de la web carga
    VACIA y enseña un MODAL de entrada que espera las credenciales del
    SUPERUSUARIO; nada de la web (cabecera, banner, pie) se ve. El modal se
    sirve y se valida AQUI, en la misma URL: contraseña (usuario o correo) y,
    si la cuenta tiene verificacion en dos pasos, el codigo como segundo paso.
    Pasan sin candado: los estaticos, el cierre de sesion, recuperar la
    contraseña, y los avisos de fuera (IPN de PayPal, timbre de AssemblyAI).
    Toda respuesta lleva X-Robots-Tag: noindex. Abrir la web = apagar el
    interruptor en Panel → Ajustes."""
    EXEMPT = ('/accounts/logout', '/accounts/password/', '/accounts/idioma/',
              '/static/', '/healthz', '/donaciones/ipn/', '/aai-hook/', '/metrics')
    CAMPO = 'privada_login'

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def activa():
        try:
            from apps.panel.models import SystemSetting
            return SystemSetting.get_str('site_private', '0') != '0'
        except Exception:
            return False

    def _modal(self, request, estado='', error='', paso='clave', status=403):
        from django.shortcuts import render
        resp = render(request, 'privada.html',
                      {'error': error, 'paso': paso, 'estado': estado}, status=status)
        resp['X-Robots-Tag'] = 'noindex, nofollow'
        resp['Cache-Control'] = 'no-store'
        return resp

    def _entrar(self, request):
        """POST del modal: contraseña o codigo. Devuelve una respuesta."""
        from django.conf import settings
        from django.contrib.auth import authenticate, login
        from django.middleware.csrf import CsrfViewMiddleware
        from django.shortcuts import redirect
        rechazo = CsrfViewMiddleware(lambda r: None).process_view(request, lambda r: None, (), {})
        if rechazo is not None:
            return rechazo
        if request.POST.get('paso') == 'codigo':
            from apps.accounts.models import User
            from django_otp import login as otp_login
            from django_otp.plugins.otp_totp.models import TOTPDevice
            user = User.objects.filter(pk=request.session.get('otp_user_pk')).first()
            device = TOTPDevice.objects.filter(user=user, confirmed=True).first() if user else None
            if user and device and device.verify_token(request.POST.get('code', '').strip()):
                backend = request.session.pop('otp_backend', settings.AUTHENTICATION_BACKENDS[0])
                request.session.pop('otp_user_pk', None)
                login(request, user, backend=backend)
                otp_login(request, device)
                return redirect(request.path)
            return self._modal(request, paso='codigo', error='Código incorrecto.')
        user = authenticate(request, username=request.POST.get('username', '').strip(),
                            password=request.POST.get('password', ''))
        if user is None:
            return self._modal(request, error='Usuario o contraseña incorrectos.')
        if not user.is_superuser:
            return self._modal(request, error='Solo el administrador puede entrar de momento.')
        from django_otp.plugins.otp_totp.models import TOTPDevice
        if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
            request.session['otp_user_pk'] = user.pk
            request.session['otp_backend'] = user.backend
            return self._modal(request, paso='codigo')
        login(request, user)
        return redirect(request.path)

    def __call__(self, request):
        if not self.activa():
            return self.get_response(request)
        path = request.path
        u = getattr(request, 'user', None)
        es_super = bool(u and u.is_authenticated and u.is_superuser)
        if es_super or any(path.startswith(p) for p in self.EXEMPT):
            resp = self.get_response(request)
            resp['X-Robots-Tag'] = 'noindex, nofollow'
            return resp
        if request.method == 'POST' and request.POST.get(self.CAMPO):
            return self._entrar(request)
        return self._modal(request)
