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
