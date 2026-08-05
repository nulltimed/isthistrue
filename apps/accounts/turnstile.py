"""Validacion en servidor de Cloudflare Turnstile. Saltable en DEBUG sin claves."""
import requests
from django.conf import settings

def verify(token, ip=None):
    if not settings.TURNSTILE_SECRET_KEY:
        return settings.DEBUG  # sin claves: solo pasa en desarrollo
    try:
        r = requests.post('https://challenges.cloudflare.com/turnstile/v0/siteverify',
                          data={'secret': settings.TURNSTILE_SECRET_KEY,
                                'response': token, 'remoteip': ip}, timeout=10)
        return r.json().get('success', False)
    except requests.RequestException:
        return False
