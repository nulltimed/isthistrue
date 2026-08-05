"""Sirve /media/ en produccion con candado: los lotes de codigos, SOLO staff."""
import os
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseForbidden


def media_serve(request, path):
    if path.startswith('code_batches/') and not (
            request.user.is_authenticated and request.user.is_staff):
        return HttpResponseForbidden('Solo administración.')
    root = str(settings.MEDIA_ROOT)
    full = os.path.normpath(os.path.join(root, path))
    # sin el separador, '../media-staging' pasaria el filtro (prefijo comun 'media')
    if not full.startswith(root.rstrip(os.sep) + os.sep) or not os.path.isfile(full):
        raise Http404
    return FileResponse(open(full, 'rb'))
