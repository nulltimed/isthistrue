"""5.15 (orden de David): el servidor deja de creerse al navegador.

Con PAYPAL_CLIENT_SECRET en el .env, cada aviso de captura se contrasta
contra la API REST de PayPal (v2/checkout/orders): el pedido debe EXISTIR,
estar COMPLETED y su importe cubrir lo declarado. Sin credenciales, se
mantiene el circuito anterior (documentado en docs/85 con su riesgo).
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('analysis.paypal')

API = 'https://api-m.paypal.com'


def _token():
    r = requests.post(f'{API}/v1/oauth2/token',
                      auth=(settings.PAYPAL_CLIENT_ID,
                            settings.PAYPAL_CLIENT_SECRET),
                      data={'grant_type': 'client_credentials'}, timeout=15)
    r.raise_for_status()
    return r.json()['access_token']


def verify_order(order_id, amount_eur):
    """True = pedido real, COMPLETED y con importe suficiente en EUR.
    False = no cuadra o no existe. None = sin credenciales (no se verifica)."""
    if not (settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET):
        return None
    try:
        r = requests.get(f'{API}/v2/checkout/orders/{order_id}',
                         headers={'Authorization': f'Bearer {_token()}'},
                         timeout=15)
        if r.status_code != 200:
            logger.warning('PayPal: pedido %s no consultable (%s)',
                           order_id, r.status_code)
            return False
        datos = r.json()
        if datos.get('status') != 'COMPLETED':
            logger.warning('PayPal: pedido %s en estado %s',
                           order_id, datos.get('status'))
            return False
        total = 0.0
        for u in datos.get('purchase_units') or []:
            imp = (u.get('amount') or {})
            if imp.get('currency_code') == 'EUR':
                total += float(imp.get('value') or 0)
        if total + 0.001 < float(amount_eur):
            logger.warning('PayPal: pedido %s importe %.2f < declarado %.2f',
                           order_id, total, float(amount_eur))
            return False
        return True
    except Exception as exc:
        logger.warning('PayPal: verificacion del pedido %s fallo (%r)',
                       order_id, exc)
        return False
