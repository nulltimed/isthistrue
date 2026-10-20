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
    """5.31 (orden de David, 2026-10-20): la WEB PRIVADA. Mientras el ajuste del
    panel `site_private` este encendido, la web entera sigue en su URL de
    siempre pero solo entra el SUPERUSUARIO: cualquier otro visitante va a la
    pagina de entrada. Pasan sin candado: la propia entrada (y recuperar la
    contrasena), los estaticos, y los avisos que llegan de fuera (IPN de PayPal
    y timbre de AssemblyAI), que si no romperian donaciones y analisis. Mientras
    este privada, toda respuesta lleva X-Robots-Tag: noindex. Abrir la web =
    apagar el interruptor en Panel → Ajustes, sin despliegue."""
    EXEMPT = ('/accounts/login', '/accounts/logout', '/accounts/password/',
              '/accounts/otp/', '/accounts/idioma/',
              '/static/', '/healthz', '/donaciones/ipn/', '/aai-hook/',
              '/metrics')

    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def activa():
        try:
            from apps.panel.models import SystemSetting
            return SystemSetting.get_str('site_private', '0') != '0'
        except Exception:
            return False

    def __call__(self, request):
        if not self.activa():
            return self.get_response(request)
        path = request.path
        u = getattr(request, 'user', None)
        es_super = bool(u and u.is_authenticated and u.is_superuser)
        if not es_super and not any(path.startswith(p) for p in self.EXEMPT):
            from django.shortcuts import redirect, render
            if u is not None and u.is_authenticated:
                resp = render(request, 'privada.html', status=403)
            else:
                resp = redirect('/accounts/login/?next=' + path)
            resp['X-Robots-Tag'] = 'noindex, nofollow'
            return resp
        resp = self.get_response(request)
        resp['X-Robots-Tag'] = 'noindex, nofollow'
        return resp

