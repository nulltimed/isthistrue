"""Serie 6.4 (ordenes de David, 2026-11-06): condiciones de compra de creditos
(desistimiento resuelto) y pagina publica de transparencia, con los huecos de
la SL en «pendiente de constitucion» hasta que David de los datos."""
from django.test import TestCase


class CondicionesDeCreditos(TestCase):
    def test_la_pagina_existe_con_el_desistimiento_y_el_hueco_de_la_sl(self):
        html = self.client.get('/legal/creditos/').content.decode()
        self.assertIn('desistimiento', html)
        self.assertIn('103.m', html)
        self.assertIn('pendiente de constitución', html)
        self.assertIn('compran inmediatez, nunca resultados', html)

    def test_con_la_sl_sembrada_aparece_su_nombre(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='sl_legal_name',
                                               defaults={'value': 'Veritas SL'})
        SystemSetting.objects.update_or_create(key='sl_cif', defaults={'value': 'B12345678'})
        html = self.client.get('/legal/creditos/').content.decode()
        self.assertIn('Veritas SL', html)
        self.assertIn('B12345678', html)
        self.assertNotIn('pendiente de constitución', html)

    def test_la_pagina_de_creditos_enlaza_las_condiciones(self):
        html = self.client.get('/creditos/').content.decode()
        self.assertIn('/legal/creditos/', html)


class Transparencia(TestCase):
    def test_quien_cobra_que_a_la_vista(self):
        html = self.client.get('/transparencia/').content.decode()
        self.assertIn('quién cobra qué', html)
        self.assertIn('Nada de los usuarios', html)
        self.assertIn('AL COSTE', html)
        self.assertIn('github.com/nulltimed/isthistrue', html)
        self.assertIn('pendiente de constitución', html)

    def test_el_pie_la_enlaza(self):
        html = self.client.get('/').content.decode()
        self.assertIn('/transparencia/', html)


class LegalesSinDonaciones(TestCase):
    def test_condiciones_y_privacidad_ya_no_venden_donaciones(self):
        self.assertNotIn('donacion', open('templates/legal/condiciones.html').read().lower())
        priv = open('templates/legal/privacidad.html').read().lower()
        self.assertNotIn('donaciones;', priv)
        # ENMIENDA 6.13 (David, 2026-11-09: «Paypal Bussiness»): la pasarela
        # nombrada en la privacidad es PayPal, no Stripe.
        self.assertIn('paypal', priv)
        self.assertNotIn('stripe', priv)
