"""6.2: autenticacion y cupo diario de la API (cabecera X-API-Key)."""
import functools
from datetime import date

from django.db.models import F
from django.http import JsonResponse

ATTRIBUTION = {'text': 'Datos de esestocierto? (CC-BY-SA)',
               'url': 'https://esestocierto.com'}


def require_api_key(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        from .models import ApiKey, ApiUsage
        raw = request.headers.get('X-API-Key', '').strip()
        if not raw:
            return JsonResponse({'error': 'Falta la cabecera X-API-Key. '
                                 'Solicita una clave en /api/.'}, status=401)
        key = ApiKey.objects.filter(key=raw, status='APPROVED').first()
        if not key:
            return JsonResponse({'error': 'Clave no válida o revocada.'}, status=403)
        uso, _ = ApiUsage.objects.get_or_create(api_key=key, date=date.today())
        if uso.count >= key.daily_limit():
            return JsonResponse({'error': 'Cupo diario agotado.',
                                 'daily_limit': key.daily_limit()}, status=429)
        ApiUsage.objects.filter(pk=uso.pk).update(count=F('count') + 1)
        request.api_key = key
        return view(request, *args, **kwargs)
    return wrapper


def envelope(data, **extra):
    """Toda respuesta lleva la atribucion (CC-BY-SA, nivel gratuito la exige)."""
    out = {'data': data, 'attribution': ATTRIBUTION}
    out.update(extra)
    return JsonResponse(out, json_dumps_params={'ensure_ascii': False})
