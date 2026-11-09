"""Serie 6.27 (orden de David, 2026-11-09, 21:39: «Sí» al boton): «⚡ Verificar
ya» — el voto unico de moderacion (6.26) en un clic, solo para mod/superusuario
y solo por POST (lanza gasto real). Y la salida de verificar_atrasados imprime
el ENLACE de cada retenido (respuesta a su «¿de qué comando? dónde?»).
"""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


class BotonVerificarYa(TestCase):
    def setUp(self):
        self.su = User.objects.create_superuser(username='su627',
                                                email='su627@example.org',
                                                password='x')
        self.normal = User.objects.create_user(username='u627',
                                               email='u627@example.org',
                                               password='x')
        self.post = Post.objects.create(author=self.normal,
                                        status='PENDING_VALIDATION',
                                        url='https://youtu.be/s627')

    def test_el_boton_solo_lo_ve_moderacion(self):
        self.client.force_login(self.su)
        html = self.client.get(f'/post/{self.post.pk}/', follow=True).content.decode()
        self.assertIn('verificar-ya', html)
        self.assertIn('Verificar ya', html)
        self.client.force_login(self.normal)
        html = self.client.get(f'/post/{self.post.pk}/', follow=True).content.decode()
        self.assertNotIn('verificar-ya', html)

    def test_en_un_post_terminado_no_hay_boton(self):
        self.post.status = 'DONE'
        self.post.save(update_fields=['status'])
        self.client.force_login(self.su)
        html = self.client.get(f'/post/{self.post.pk}/', follow=True).content.decode()
        self.assertNotIn('verificar-ya', html)

    @patch('apps.analysis.services.identification_gate', return_value=(True, 'ok'))
    @patch('apps.analysis.tasks.launch_full_analysis')
    def test_el_clic_del_superusuario_lanza(self, lanzar, _g):
        self.client.force_login(self.su)
        r = self.client.post(f'/post/{self.post.pk}/verificar-ya/')
        self.assertEqual(r.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'FULL_QUEUED')
        lanzar.assert_called_once()

    @patch('apps.analysis.tasks.launch_full_analysis')
    def test_un_usuario_normal_no_puede(self, lanzar):
        self.client.force_login(self.normal)
        self.client.post(f'/post/{self.post.pk}/verificar-ya/')
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'PENDING_VALIDATION')
        lanzar.assert_not_called()

    @patch('apps.analysis.tasks.launch_full_analysis')
    def test_un_get_no_lanza_nada(self, lanzar):
        """Gasto real jamas por GET (prefetch de navegadores)."""
        self.client.force_login(self.su)
        self.client.get(f'/post/{self.post.pk}/verificar-ya/')
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'PENDING_VALIDATION')
        lanzar.assert_not_called()


class SalidaConEnlace(TestCase):
    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(False, 'faltan voces'))
    def test_el_retenido_sale_con_su_enlace(self, _g, _l):
        u = User.objects.create_user(username='u627b', email='u627b@example.org',
                                     password='x')
        Post.objects.create(author=u, status='PENDING_VALIDATION',
                            url='https://youtu.be/s627b', slug='video-627b')
        out = StringIO()
        call_command('verificar_atrasados', stdout=out)
        salida = out.getvalue()
        self.assertIn('Retenido', salida)
        self.assertIn('https://esestocierto.com/post/video-627b', salida)
