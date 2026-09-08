"""Serie 5.24 (ordenes de David, 2026-09-09): PayPal por el servidor (sin
ventana emergente), RSS para los podcasts de Spotify, y el panel Gastos."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u524', email='u524@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class _R:
    def __init__(self, status_code, data, text=''):
        self.status_code, self._data, self.text = status_code, data, text or str(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class Parche524A_PayPalPorElServidor(TestCase):
    """A: el formulario crea el pedido en el servidor y manda a paypal.com; el
    retorno captura, anota VERIFICADA (idempotente) y lanza el apadrinamiento."""

    CRED = dict(PAYPAL_CLIENT_ID='cid', PAYPAL_CLIENT_SECRET='sec')

    def _paypal(self, capture_status='COMPLETED', amount='5.00', custom='donacion'):
        def post(url, **kw):
            if url.endswith('/v1/oauth2/token'):
                return _R(200, {'access_token': 't'})
            if url.endswith('/v2/checkout/orders'):
                self.pedido = kw.get('json')
                return _R(201, {'id': 'ORD524', 'links': [
                    {'rel': 'self', 'href': 'x'},
                    {'rel': 'approve', 'href': 'https://www.paypal.com/checkoutnow?token=ORD524'}]})
            if url.endswith('/capture'):
                return _R(201, {'status': capture_status, 'payer': {'email_address': 'p@x'},
                                'purchase_units': [{'custom_id': custom, 'payments': {'captures': [
                                    {'status': 'COMPLETED', 'amount': {'currency_code': 'EUR', 'value': amount}}]}}]})
            return _R(404, {})
        return mock.patch('apps.analysis.paypal_check.requests.post', side_effect=post)

    def test_el_banner_es_un_formulario_sin_sdk(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('paypal.com/sdk/js', html)
        self.assertIn('action="/donaciones/iniciar/"', html)
        self.assertIn('Donar con PayPal', html)
        self.assertNotIn('istt-pp-cerrar', html)

    def test_iniciar_crea_el_pedido_y_redirige_a_paypal(self):
        from apps.panel.models import AuditLog
        with override_settings(**self.CRED), self._paypal():
            r = self.client.post('/donaciones/iniciar/', {'amount': '7,50'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('https://www.paypal.com/checkoutnow'))
        self.assertEqual(self.pedido['purchase_units'][0]['amount']['value'], '7.50')
        self.assertEqual(self.pedido['application_context']['locale'], 'es-ES')
        self.assertIn('/donaciones/retorno/', self.pedido['application_context']['return_url'])
        self.assertTrue(AuditLog.objects.filter(action='donation_started').exists())

    def test_cantidad_invalida_no_llega_a_paypal(self):
        with override_settings(**self.CRED), self._paypal() as pp:
            r = self.client.post('/donaciones/iniciar/', {'amount': '0.5'})
        self.assertEqual(r['Location'], '/donaciones/')
        pp.assert_not_called()

    def test_sin_credenciales_va_al_enlace_clasico(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='paypal_url', defaults={'value': 'https://paypal.me/x'})
        with override_settings(PAYPAL_CLIENT_ID='', PAYPAL_CLIENT_SECRET=''):
            r = self.client.post('/donaciones/iniciar/', {'amount': '5'})
        self.assertEqual(r['Location'], 'https://paypal.me/x')

    def test_el_retorno_captura_anota_verificada_y_es_idempotente(self):
        from apps.panel.models import Donation
        from apps.panel.services import live_monthly_cap
        cap_antes, _, _ = live_monthly_cap()
        with override_settings(**self.CRED), self._paypal(amount='5.00'):
            r1 = self.client.get('/donaciones/retorno/?token=ORD524&PayerID=P')
            r2 = self.client.get('/donaciones/retorno/?token=ORD524&PayerID=P')
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(Donation.objects.filter(note='paypal-web:ORD524').count(), 1)
        d = Donation.objects.get(note='paypal-web:ORD524')
        self.assertTrue(d.verified, 'la captura la hizo el servidor: nace verificada')
        self.assertEqual(d.amount_eur, Decimal('5.00'))
        cap_despues, _, _ = live_monthly_cap()
        self.assertGreater(cap_despues, cap_antes, 'una donacion verificada sube el tope')
        self.assertEqual(r2.status_code, 302)

    def test_el_apadrinamiento_atado_lanza_el_analisis_al_volver(self):
        from apps.panel.models import Donation
        u = make_user()
        post = Post.objects.create(author=u, url='https://youtu.be/ap524', title='En cola',
                                   status='AWAITING_BUDGET', duration_seconds=600)
        with override_settings(**self.CRED), self._paypal(amount='99.00', custom=f'post:{post.pk}'), \
             mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanza:
            r = self.client.get('/donaciones/retorno/?token=ORD524')
        post.refresh_from_db()
        self.assertEqual(post.status, 'PENDING')
        lanza.assert_called_once_with(post.pk)
        self.assertEqual(Donation.objects.get(note='paypal-web:ORD524').post_id, post.pk)
        self.assertEqual(r['Location'], post.get_absolute_url())
        # y el boton de apadrinar es un formulario al servidor con la cantidad exacta
        post.status = 'AWAITING_BUDGET'
        post.save(update_fields=['status'])
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('action="/donaciones/iniciar/"', html)
        self.assertIn(f'name="post" value="{post.pk}"', html)
        self.assertNotIn('paypal.Buttons', html)

    def test_una_captura_fallida_no_anota_nada(self):
        from apps.panel.models import AuditLog, Donation
        with override_settings(**self.CRED), self._paypal(capture_status='DECLINED', amount='0'):
            r = self.client.get('/donaciones/retorno/?token=ORD524')
        self.assertEqual(r['Location'], '/donaciones/')
        self.assertFalse(Donation.objects.exists())
        self.assertTrue(AuditLog.objects.filter(action='donation_reject').exists())
