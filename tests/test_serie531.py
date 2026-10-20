"""Serie 5.31 (orden de David, 2026-10-20): la WEB PRIVADA — en su URL de siempre,
pero solo entra el superusuario hasta que el apague el candado en el panel."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u531', email='u531@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Parche531_WebPrivada(TestCase):
    def _privada(self, on=True):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='site_private', defaults={'value': '1' if on else '0'})

    def test_nace_privada_de_fabrica(self):
        import importlib
        from django.conf import settings
        # el de produccion (config.settings) dice '1'; la suite lo apaga en settings_test
        self.assertEqual(importlib.import_module('config.settings').SETTING_DEFAULTS['site_private'], '1')
        self.assertIn('config.middleware.PrivateSiteMiddleware', settings.MIDDLEWARE)

    def test_el_anonimo_va_a_la_entrada_y_no_se_indexa(self):
        self._privada()
        for url in ('/', '/foro/', '/wiki/', '/post/1/', '/api/v1/claims/', '/rss/veredictos/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertTrue(r['Location'].startswith('/accounts/login/?next='), url)
            self.assertEqual(r['X-Robots-Tag'], 'noindex, nofollow')
        r = self.client.get('/accounts/login/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('no está abierta al público', r.content.decode())

    def test_un_usuario_normal_con_sesion_ve_en_construccion(self):
        self._privada()
        self.client.force_login(make_user())
        r = self.client.get('/')
        self.assertEqual(r.status_code, 403)
        self.assertIn('En construcción', r.content.decode())

    def test_el_superusuario_entra_y_el_panel_enseña_el_candado(self):
        self._privada()
        self.client.force_login(make_user(username='root531', email='root531@example.org',
                                          is_staff=True, is_superuser=True))
        self.assertEqual(self.client.get('/').status_code, 200)
        html = self.client.get('/panel/settings/').content.decode()
        self.assertIn('name="site_private"', html)
        self.assertIn('la web está PRIVADA', html)

    def test_los_avisos_de_fuera_y_los_estaticos_pasan(self):
        self._privada()
        # el IPN de PayPal y el timbre de AssemblyAI NO se redirigen a la entrada
        for url in ('/donaciones/ipn/', '/aai-hook/'):
            r = self.client.post(url, {})
            self.assertNotEqual(r.status_code, 302, url)
        r = self.client.get('/accounts/password/olvidada/')
        self.assertEqual(r.status_code, 200)

    def test_apagar_el_candado_abre_la_web_sin_desplegar(self):
        self._privada(False)
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.has_header('X-Robots-Tag'))
