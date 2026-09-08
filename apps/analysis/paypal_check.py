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


# ---------------- 5.24-A (orden de David): el pago sin ventana emergente ----------------
# El boton del SDK abria una ventana en blanco sobre el login de PayPal (5.17-C
# no lo curo). Ahora el SERVIDOR crea el pedido, el usuario paga en paypal.com a
# pantalla completa y vuelve a /donaciones/retorno/, donde el servidor CAPTURA y
# anota la donacion ya verificada (la captura la hacemos nosotros).

def credenciales_ok():
    return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)


def create_order(amount_eur, return_url, cancel_url, custom_id='', locale='es-ES',
                 brand='esestocierto?'):
    """Crea el pedido (intent CAPTURE) y devuelve (order_id, approve_url) o
    (None, None). Nunca lanza."""
    if not credenciales_ok():
        return None, None
    try:
        cuerpo = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {'currency_code': 'EUR', 'value': f'{float(amount_eur):.2f}'},
                'custom_id': (custom_id or 'donacion')[:127],
                'description': ('Donación a esestocierto? (fact-checking comunitario)')[:127],
            }],
            'application_context': {
                'brand_name': brand[:127], 'locale': locale,
                'landing_page': 'LOGIN', 'shipping_preference': 'NO_SHIPPING',
                'user_action': 'PAY_NOW',
                'return_url': return_url, 'cancel_url': cancel_url,
            },
        }
        r = requests.post(f'{API}/v2/checkout/orders', json=cuerpo,
                          headers={'Authorization': f'Bearer {_token()}',
                                   'Content-Type': 'application/json'}, timeout=20)
        if r.status_code not in (200, 201):
            logger.warning('PayPal: crear pedido fallo (%s) %s', r.status_code, r.text[:200])
            return None, None
        datos = r.json()
        approve = next((l.get('href') for l in datos.get('links') or []
                        if l.get('rel') == 'approve'), None)
        return datos.get('id'), approve
    except Exception as exc:
        logger.warning('PayPal: crear pedido fallo (%r)', exc)
        return None, None


def capture_order(order_id):
    """Captura el pedido aprobado. Devuelve {'status', 'amount', 'custom_id',
    'payer'} o None. Un pedido ya capturado (ORDER_ALREADY_CAPTURED) se relee
    con GET para que el retorno sea idempotente."""
    if not credenciales_ok():
        return None
    try:
        h = {'Authorization': f'Bearer {_token()}', 'Content-Type': 'application/json'}
        r = requests.post(f'{API}/v2/checkout/orders/{order_id}/capture',
                          headers=h, json={}, timeout=25)
        if r.status_code == 422 and 'ALREADY_CAPTURED' in r.text:
            r = requests.get(f'{API}/v2/checkout/orders/{order_id}', headers=h, timeout=15)
        if r.status_code not in (200, 201):
            logger.warning('PayPal: captura de %s fallo (%s) %s', order_id,
                           r.status_code, r.text[:200])
            return None
        datos = r.json()
        total, custom = 0.0, ''
        for u in datos.get('purchase_units') or []:
            custom = custom or u.get('custom_id', '')
            caps = ((u.get('payments') or {}).get('captures') or [])
            for c in caps:
                imp = c.get('amount') or {}
                if imp.get('currency_code') == 'EUR' and c.get('status') in ('COMPLETED', 'PENDING'):
                    total += float(imp.get('value') or 0)
            if not caps:   # pedido releido con GET
                imp = u.get('amount') or {}
                if imp.get('currency_code') == 'EUR':
                    total += float(imp.get('value') or 0)
        return {'status': datos.get('status'), 'amount': round(total, 2),
                'custom_id': custom,
                'payer': ((datos.get('payer') or {}).get('email_address') or '')[:120]}
    except Exception as exc:
        logger.warning('PayPal: captura de %s fallo (%r)', order_id, exc)
        return None
