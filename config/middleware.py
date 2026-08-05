"""Decide idioma y seccion por subdominio (el 'portero' de la app)."""
from django.utils import translation

HOST_LANG = {'isthistrue': 'en', 'escierto': 'es', 'wikitrue': None}

class HostLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].split('.')[0]
        request.site_section = 'wiki' if host == 'wikitrue' else 'forum'
        lang = HOST_LANG.get(host)
        if lang is None:  # wikitrue o entrada neutra: Accept-Language
            lang = translation.get_language_from_request(request)
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        response = self.get_response(request)
        response.headers.setdefault('Content-Language', lang)
        return response


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
