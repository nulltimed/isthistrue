"""Serie 5.31 (orden de David, 2026-10-20): la WEB PRIVADA — cualquier direccion
carga VACIA con un modal de entrada que espera las credenciales del superusuario;
abrir la web = apagar el interruptor del panel."""
import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u531', email='u531@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Parche531_WebPrivada(TestCase):
    def _privada(self, on=True):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='site_private', defaults={'value': '1' if on else '0'})

    def _super(self):
        return make_user(username='root531', email='root531@example.org', password='clave-531',
                         is_staff=True, is_superuser=True)

    def test_nace_privada_de_fabrica(self):
        from django.conf import settings
        self.assertEqual(importlib.import_module('config.settings').SETTING_DEFAULTS['site_private'], '1')
        self.assertIn('config.middleware.PrivateSiteMiddleware', settings.MIDDLEWARE)

    def test_cualquier_direccion_carga_vacia_con_el_modal(self):
        self._privada()
        for url in ('/', '/foro/', '/wiki/', '/post/1/', '/accounts/login/', '/api/v1/claims/'):
            r = self.client.get(url)
            html = r.content.decode()
            self.assertEqual(r.status_code, 403, url)
            self.assertEqual(r['X-Robots-Tag'], 'noindex, nofollow')
            self.assertIn('name="privada_login"', html, url)
            self.assertIn('name="password"', html, url)
            for nada in ('masthead', '<nav', '<footer', 'quota-banner', 'Analizar un vídeo'):
                self.assertNotIn(nada, html, f'{url}: la web no debe verse ({nada})')

    def test_las_credenciales_del_superusuario_abren_la_web_en_la_misma_url(self):
        self._privada()
        self._super()
        r = self.client.post('/foro/', {'privada_login': '1', 'username': 'root531', 'password': 'clave-531'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], '/foro/')
        r = self.client.get('/foro/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('masthead', r.content.decode())

    def test_credenciales_malas_o_de_usuario_normal_no_entran(self):
        self._privada()
        self._super()
        make_user(username='normal531', email='n531@example.org', password='clave-n')
        r = self.client.post('/', {'privada_login': '1', 'username': 'root531', 'password': 'mal'})
        self.assertEqual(r.status_code, 403)
        self.assertIn('incorrectos', r.content.decode())
        r = self.client.post('/', {'privada_login': '1', 'username': 'normal531', 'password': 'clave-n'})
        self.assertEqual(r.status_code, 403)
        self.assertIn('Solo el administrador', r.content.decode())
        self.assertEqual(self.client.get('/').status_code, 403)

    def test_un_usuario_normal_con_sesion_tambien_ve_el_modal(self):
        self._privada()
        self.client.force_login(make_user())
        r = self.client.get('/')
        self.assertEqual(r.status_code, 403)
        self.assertIn('name="privada_login"', r.content.decode())

    def test_con_dos_pasos_pide_el_codigo_antes_de_abrir(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice
        self._privada()
        u = self._super()
        dev = TOTPDevice.objects.create(user=u, name='t', confirmed=True)
        r = self.client.post('/', {'privada_login': '1', 'username': 'root531', 'password': 'clave-531'})
        self.assertEqual(r.status_code, 403)
        self.assertIn('name="code"', r.content.decode())
        self.assertEqual(self.client.get('/').status_code, 403)       # sin codigo no hay sesion
        import time
        from django_otp.oath import totp
        from binascii import unhexlify
        code = totp(unhexlify(dev.key.encode()), dev.step, dev.t0, dev.digits, dev.drift)
        r = self.client.post('/', {'privada_login': '1', 'paso': 'codigo', 'code': f'{code:06d}'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_los_avisos_de_fuera_y_los_estaticos_pasan(self):
        self._privada()
        for url in ('/donaciones/ipn/', '/aai-hook/'):
            r = self.client.post(url, {})
            # llegan a su vista (que puede rechazarlos por su propia firma), no al modal
            self.assertNotIn('privada_login', r.content.decode(), url)
        self.assertEqual(self.client.get('/accounts/password/olvidada/').status_code, 200)

    def test_el_superusuario_ve_el_interruptor_en_el_panel(self):
        self._privada()
        self.client.force_login(self._super())
        html = self.client.get('/panel/settings/').content.decode()
        self.assertIn('name="site_private"', html)
        self.assertIn('la web está PRIVADA', html)

    def test_apagar_el_candado_abre_la_web_sin_desplegar(self):
        self._privada(False)
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.has_header('X-Robots-Tag'))
