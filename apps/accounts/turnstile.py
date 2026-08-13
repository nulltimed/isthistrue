"""Validacion en servidor de Cloudflare Turnstile. Saltable en DEBUG sin claves."""
import requests
from django.conf import settings

def verify(token, ip=None):
    if not settings.TURNSTILE_SECRET_KEY:
        # Sin claves: Turnstile desactivado (antes devolvia settings.DEBUG y en
        # produccion bloqueaba TODO registro en silencio — Fase 3.7 §2).
        import logging
        logging.getLogger('accounts').warning('Turnstile DESACTIVADO (sin claves en .env)')
        return True
    try:
        r = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify',
                          data={'secret': settings.TURNSTILE_SECRET_KEY,
                                'response': token, 'remoteip': ip}, timeout=10)
        return r.json().get('success', False)
    except requests.RequestException:
        return False
