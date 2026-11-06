"""Serie 6.1 (ordenes de David, 2026-11-06): el pivote a la SL en un solo parche.

Literales de David: «Yo tengo una incapacidad absoluta permanente, por lo que no
puedo ni aceptar donaciones» · Lectura A confirmada (donaciones/apadrinamiento
RETIRADOS, sustituidos por creditos cobrados por la SL) · packs 5/10/20 EUR con
«1 EUR tramo adicional» · rastreo de origen automatico en rojos/ambar y de pago
en el resto · «Aplica todos los cambios absolutamente en un solo parche».
La SL aun no esta constituida: la compra nace APAGADA (sl_checkout_enabled=0).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u61', email='u61@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Monedero(TestCase):
    def test_gastar_sin_saldo_no_deja_numeros_rojos(self):
        from apps.accounts import credits as cred
        from apps.accounts.credits import InsufficientCredits
        u = make_user()
        with self.assertRaises(InsufficientCredits):
            cred.spend(u, 3, 'ADVANCE')
        self.assertEqual(cred.wallet(u).balance, 0)
        self.assertEqual(u.credit_moves.count(), 0)

    def test_alta_y_gasto_dejan_libro_y_financiacion(self):
        from apps.accounts import credits as cred
        from apps.panel.models import Donation
        u = make_user(username='u61b', email='u61b@example.org')
        cred.grant(u, 5, note='pack de prueba')
        post = Post.objects.create(author=u, url='https://youtu.be/s61a', title='V')
        saldo = cred.spend(u, 2, 'ADVANCE', post=post)
        self.assertEqual(saldo, 3)
        self.assertEqual(u.credit_moves.count(), 2)
        # El gasto que autoriza analisis crea su apunte de financiacion CREDIT
        # verificado: es lo que sube live_monthly_cap (mecanica del 4.3-F).
        d = Donation.objects.get(method='CREDIT')
        self.assertTrue(d.verified)
        self.assertEqual(float(d.amount_eur), 2.0)
        self.assertEqual(d.post, post)

    def test_el_rastreo_suelto_no_infla_el_deposito(self):
        from apps.accounts import credits as cred
        from apps.panel.models import Donation
        u = make_user(username='u61c', email='u61c@example.org')
        cred.grant(u, 1)
        cred.spend(u, 1, 'ORIGIN', fund=False)
        self.assertFalse(Donation.objects.filter(method='CREDIT').exists())


class PaginaCreditos(TestCase):
    def test_donaciones_redirige_a_creditos(self):
        r = self.client.get('/donaciones/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/creditos/')

    def test_la_pagina_existe_y_la_compra_nace_apagada(self):
        html = self.client.get('/creditos/').content.decode()
        self.assertIn('Próximamente', html)       # sl_checkout_enabled=0 de fabrica
        self.assertNotIn('>Comprar<', html)
        for pack in ('5 €', '10 €', '20 €'):
            self.assertIn(pack, html)

    def test_el_banner_ya_no_pide_donaciones(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('Donar con PayPal', html)
        self.assertNotIn('Faltan', html)
        self.assertIn('/creditos/', html)


class AdelantarConCreditos(TestCase):
    def _post_en_cola(self, u):
        return Post.objects.create(author=u, url='https://youtu.be/s61q',
                                   title='Largo', status='AWAITING_BUDGET',
                                   duration_seconds=50 * 60)

    def test_adelantar_saca_de_la_cola_y_cobra_por_tramos(self):
        from unittest import mock
        from apps.accounts import credits as cred
        from apps.analysis.services import credits_for_post
        u = make_user(username='u61d', email='u61d@example.org')
        post = self._post_en_cola(u)
        self.assertEqual(credits_for_post(post), 3)   # 50 min / tramo de 20 = 3
        cred.grant(u, 3)
        self.client.force_login(u)
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanzar:
            self.client.post(f'/post/{post.pk}/adelantar-creditos/')
        post.refresh_from_db()
        self.assertEqual(post.status, 'NEW')
        lanzar.assert_called_once_with(post.pk)
        self.assertEqual(cred.wallet(u).balance, 0)

    def test_sin_saldo_no_pasa_nada_y_se_avisa(self):
        u = make_user(username='u61e', email='u61e@example.org')
        post = self._post_en_cola(u)
        self.client.force_login(u)
        r = self.client.post(f'/post/{post.pk}/adelantar-creditos/', follow=True)
        post.refresh_from_db()
        self.assertEqual(post.status, 'AWAITING_BUDGET')
        self.assertIn('créditos suficientes', r.content.decode())


class RastreoDeOrigen(TestCase):
    def _claim(self, u, color='GREEN'):
        from apps.wiki.models import Claim, ClaimAppearance
        post = Post.objects.create(author=u, url='https://youtu.be/s61o', title='O')
        seg = post.transcript_segments.create(start_seconds=10, end_seconds=12,
                                              text='el café cura el cáncer')
        claim = Claim.objects.create(text_original='el café cura el cáncer',
                                     slug='cafe-cura-61', color=color)
        ClaimAppearance.objects.create(claim=claim, segment=seg,
                                       quote='el café cura el cáncer')
        return claim

    def test_los_rojos_se_rastrean_solos_tras_los_veredictos(self):
        from apps.agents import origin
        u = make_user(username='u61f', email='u61f@example.org')
        claim = self._claim(u, color='RED')
        hechos = origin.run_pending(claim.appearances.first().segment.post)
        claim.refresh_from_db()
        self.assertEqual(hechos, 1)
        self.assertEqual(claim.origin_status, 'DONE')
        self.assertTrue(claim.origin_chain)           # la cadena del MOCK
        self.assertEqual(claim.origin_chain[0]['kind'], 'study')

    def test_el_verde_es_bajo_demanda_y_gasta_un_credito(self):
        from apps.accounts import credits as cred
        u = make_user(username='u61g', email='u61g@example.org')
        claim = self._claim(u, color='GREEN')
        # Sin pasar por la tarea automatica: el verde no se rastrea solo.
        from apps.agents import origin
        self.assertEqual(origin.run_pending(claim.appearances.first().segment.post), 0)
        cred.grant(u, 1)
        self.client.force_login(u)
        self.client.post(f'/wiki/claim/{claim.slug}/rastrear/')
        claim.refresh_from_db()
        self.assertEqual(claim.origin_status, 'DONE')
        self.assertEqual(cred.wallet(u).balance, 0)

    def test_la_cadena_se_pinta_en_la_ficha(self):
        u = make_user(username='u61h', email='u61h@example.org')
        claim = self._claim(u, color='RED')
        claim.origin_chain = [{'kind': 'press', 'date': '2020-01-01',
                               'title': 'El titular que lo torció',
                               'url': 'https://example.org/p', 'note': 'aquí se torció'}]
        claim.origin_status = 'DONE'
        claim.save()
        html = self.client.get(f'/wiki/claim/{claim.slug}/').content.decode()
        self.assertIn('cadena de difusión', html)
        self.assertIn('El titular que lo torció', html)
        self.assertIn('origen-cadena', html)


class AjustesNuevos(TestCase):
    def test_las_claves_61_existen_con_sus_defaults(self):
        import importlib
        d = importlib.import_module('config.settings').SETTING_DEFAULTS
        self.assertEqual(d['sl_checkout_enabled'], '0')   # la SL aun no existe
        self.assertEqual(d['credit_pack_eur'], '5,10,20')
        self.assertEqual(d['credit_tramo_minutes'], '20')
        self.assertEqual(d['origin_trace_auto'], '1')
