"""Serie 6.7 (ordenes de David, 2026-11-09, 01:59): «ahora es una empresa» —
el libro de gastos publico pasa a categorias y totales (el detalle por marcas,
solo staff; enmienda en test_pase42), el email de verificacion anuncia el
credito de regalo, y el RECORRIDO GUIADO interactivo para el invitado
(literal: «Prepara un guion dirigido interactivo en la web para el usuario
a@a.com para la proxima vez que se loguee»).
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

User = get_user_model()

DATOS = {'username': 'nuevo67', 'email': 'nuevo67@example.org',
         'password1': 'Entrelazado#2026', 'password2': 'Entrelazado#2026',
         'birth_date': '1990-05-05', 'kind': 'PERSON'}


def _set(key, value):
    from apps.panel.models import SystemSetting
    SystemSetting.objects.update_or_create(key=key, defaults={'value': str(value)})


class EmailConRegalo(TestCase):
    def test_el_correo_de_verificacion_anuncia_el_credito(self):
        self.client.post('/accounts/register/', DATOS, follow=True)
        verificacion = [m for m in mail.outbox if 'Verifica' in m.subject]
        self.assertTrue(verificacion)
        self.assertIn('crédito(s) de regalo', verificacion[0].body)

    def test_sin_regalo_no_se_promete_nada(self):
        _set('welcome_credits', 0)
        self.client.post('/accounts/register/', DATOS, follow=True)
        verificacion = [m for m in mail.outbox if 'Verifica' in m.subject]
        self.assertTrue(verificacion)
        self.assertNotIn('regalo', verificacion[0].body)


class RecorridoGuiado(TestCase):
    def _socio(self):
        # a@a.com es el email de fabrica de `tour_email` (orden de David).
        return User.objects.create_user(username='socio67', email='a@a.com',
                                        password='x')

    def test_el_invitado_ve_el_recorrido_y_los_demas_no(self):
        socio = self._socio()
        otro = User.objects.create_user(username='otro67',
                                        email='otro67@example.org', password='x')
        self.client.force_login(socio)
        html = self.client.get('/').content.decode()
        self.assertIn('tour-pasos', html)
        self.assertIn('js/tour.js', html)
        self.assertIn('/servicios/', html)             # pasos del guion
        self.assertIn('/quienes-somos/', html)         # cierre sin panel (no staff)
        self.assertNotIn('/panel/settings/', html)     # el panel, solo staff
        # El socio real sera superusuario: entonces el cierre ES el panel.
        socio.is_staff = True
        socio.save(update_fields=['is_staff'])
        html2 = self.client.get('/').content.decode()
        self.assertIn('/panel/settings/', html2)
        self.client.force_login(otro)
        self.assertNotIn('tour-pasos', self.client.get('/').content.decode())

    def test_terminarlo_o_saltarlo_lo_apaga_para_siempre(self):
        socio = self._socio()
        self.client.force_login(socio)
        self.assertIn('tour-pasos', self.client.get('/').content.decode())
        r = self.client.post('/accounts/tour/visto/')
        self.assertEqual(r.status_code, 200)
        socio.refresh_from_db()
        self.assertTrue(socio.notify_prefs.get('tour_done'))
        self.assertNotIn('tour-pasos', self.client.get('/').content.decode())

    def test_el_email_del_invitado_se_cambia_en_el_panel(self):
        _set('tour_email', 'invitada67@example.org')
        invitada = User.objects.create_user(username='inv67',
                                            email='invitada67@example.org',
                                            password='x')
        self.client.force_login(invitada)
        self.assertIn('tour-pasos', self.client.get('/').content.decode())
        # Y a@a.com deja de verlo: la llave es el ajuste, no el nombre.
        socio = self._socio()
        self.client.force_login(socio)
        self.assertNotIn('tour-pasos', self.client.get('/').content.decode())
