"""Serie 6.6 (orden de David, 2026-11-09): crecimiento — «aplica todo salvo lo
que tenga que esperar a la SL, pero aun asi, preparalo» + regla permanente de
revenue en cada cambio (con su guardarrail: votos gratis, veredictos
invendibles).

Cubre: credito de bienvenida (apagado de fabrica, tope diario, y el candado
contable: un credito REGALADO jamas crea el apunte que sube el tope mensual),
resumen semanal con los bulos de la semana, paginas de confianza
(quienes-somos, correcciones) y escaparate B2B (servicios, datos CSV).
"""
from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

User = get_user_model()

DATOS = {'username': 'nuevo66', 'email': 'nuevo66@example.org',
         'password1': 'Entrelazado#2026', 'password2': 'Entrelazado#2026',
         'birth_date': '1990-05-05', 'kind': 'PERSON'}


def make_user(**kw):
    defaults = dict(username='u66', email='u66@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def _set(key, value):
    from apps.panel.models import SystemSetting
    SystemSetting.objects.update_or_create(key=key, defaults={'value': str(value)})


class CreditoDeBienvenida(TestCase):
    def test_con_cero_no_se_regala_nada(self):
        _set('welcome_credits', 0)
        self.client.post('/accounts/register/', DATOS, follow=True)
        from apps.accounts import credits as cred
        u = User.objects.get(username='nuevo66')
        self.assertEqual(cred.wallet(u).balance, 0)

    def test_de_fabrica_regala_uno_y_apunta_bienvenida(self):
        # 6.6-b (orden de David, 2026-11-09): «regalo desde el principio».
        self.client.post('/accounts/register/', DATOS, follow=True)
        from apps.accounts import credits as cred
        from apps.accounts.models import CreditLedger
        u = User.objects.get(username='nuevo66')
        self.assertEqual(cred.wallet(u).balance, 1)
        self.assertTrue(CreditLedger.objects.filter(user=u, reason='WELCOME').exists())

    def test_el_tope_diario_frena_la_granja(self):
        _set('welcome_credits', 1)
        _set('welcome_daily_max', 1)
        from apps.accounts import credits as cred
        a = make_user(username='a66', email='a66@example.org')
        b = make_user(username='b66', email='b66@example.org')
        self.assertEqual(cred.welcome_grant(a), 1)
        self.assertEqual(cred.welcome_grant(b), 0)   # tope del dia alcanzado
        self.assertEqual(cred.wallet(b).balance, 0)


class CandadoContableDelRegalo(TestCase):
    """El puente CREDIT→live_monthly_cap (4.3-F) sigue intacto para el gasto
    RESPALDADO por una compra; el regalo nunca infla el libro."""

    def test_un_credito_regalado_no_crea_apunte_de_financiacion(self):
        from apps.accounts import credits as cred
        from apps.panel.models import Donation
        u = make_user()
        cred.grant(u, 2, reason='WELCOME')
        cred.spend(u, 1, reason='ORIGIN', fund=True)
        self.assertFalse(Donation.objects.filter(method='CREDIT').exists())

    def test_el_credito_comprado_si_lo_crea(self):
        from apps.accounts import credits as cred
        from apps.panel.models import Donation
        u = make_user(username='u66pack', email='u66pack@example.org')
        cred.grant(u, 2, reason='PACK')
        cred.spend(u, 1, reason='ORIGIN', fund=True)
        apunte = Donation.objects.filter(method='CREDIT', verified=True)
        self.assertEqual(apunte.count(), 1)
        self.assertEqual(float(apunte.first().amount_eur), 1.0)


class ResumenSemanal(TestCase):
    LUNES_8 = datetime(2026, 11, 9, 8, 0)   # el 9-11-2026 es lunes

    def _claim_rojo(self):
        from apps.wiki.models import Claim
        return Claim.objects.create(text_original='el bulo semanal 66',
                                    slug='bulo-66', color='RED',
                                    consolidated=True)

    def test_el_lunes_sale_con_bulos_y_pie_de_servicios(self):
        self._claim_rojo()
        make_user(notify_mode='WEEKLY')
        from apps.accounts.tasks import send_daily_digests
        with mock.patch('django.utils.timezone.localtime',
                        return_value=self.LUNES_8):
            send_daily_digests()
        self.assertEqual(len(mail.outbox), 1)
        cuerpo = mail.outbox[0].body
        self.assertIn('resumen semanal', mail.outbox[0].subject)
        self.assertIn('bulo-66', cuerpo)
        self.assertIn('/servicios/', cuerpo)       # el pie de revenue
        self.assertIn('/creditos/', cuerpo)

    def test_un_martes_no_sale_nada_semanal(self):
        self._claim_rojo()
        make_user(notify_mode='WEEKLY')
        from apps.accounts.tasks import send_daily_digests
        with mock.patch('django.utils.timezone.localtime',
                        return_value=datetime(2026, 11, 10, 8, 0)):
            send_daily_digests()
        self.assertEqual(len(mail.outbox), 0)

    def test_semana_vacia_y_sin_avisos_no_molesta(self):
        make_user(notify_mode='WEEKLY')
        from apps.accounts.tasks import send_daily_digests
        with mock.patch('django.utils.timezone.localtime',
                        return_value=self.LUNES_8):
            send_daily_digests()
        self.assertEqual(len(mail.outbox), 0)


class PaginasDeConfianzaYServicios(TestCase):
    def test_quienes_somos_correcciones_y_servicios_cargan(self):
        for ruta, marca in [('/quienes-somos/', 'Quiénes somos'),
                            ('/correcciones/', 'Política de correcciones'),
                            ('/servicios/', 'Dossieres a medida')]:
            html = self.client.get(ruta).content.decode()
            self.assertIn(marca, html, ruta)

    def test_el_pie_enlaza_las_paginas_nuevas(self):
        html = self.client.get('/').content.decode()
        for ruta in ('/quienes-somos/', '/correcciones/', '/servicios/'):
            self.assertIn(ruta, html)

    def test_servicios_sin_correo_b2b_remite_al_formulario_api(self):
        html = self.client.get('/servicios/').content.decode()
        self.assertIn('formulario de la API', html)

    def test_servicios_con_correo_b2b_lo_ensena(self):
        _set('b2b_contact_email', 'b2b@example.org')
        html = self.client.get('/servicios/').content.decode()
        self.assertIn('mailto:b2b@example.org', html)


class DatasetCsv(TestCase):
    def test_sin_cuenta_al_login(self):
        r = self.client.get('/datos/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])

    def test_con_cuenta_baja_el_csv_solo_con_consolidados(self):
        from apps.wiki.models import Claim
        Claim.objects.create(text_original='consolidado 66', slug='cons-66',
                             color='RED', consolidated=True)
        Claim.objects.create(text_original='sin consolidar 66', slug='nocons-66',
                             color='RED', consolidated=False)
        u = make_user(username='u66csv', email='u66csv@example.org')
        self.client.force_login(u)
        r = self.client.get('/datos/')
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        cuerpo = r.content.decode()
        self.assertIn('CC-BY-SA', cuerpo)
        self.assertIn('cons-66', cuerpo)
        self.assertNotIn('nocons-66', cuerpo)
