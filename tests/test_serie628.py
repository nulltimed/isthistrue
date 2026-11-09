"""Serie 6.28 (ordenes de David, 2026-11-09, 21:42):
1) «todo ese proceso debe ser avisado por mensaje privado al moderador de
   turno y a el/los superusuarios» — un video retenido por la puerta de voces
   manda campana (y email segun preferencias) a toda la moderacion, con el
   enlace; UNA vez por post y dia.
2) El nombramiento de moderador por username/email YA existia (4.2 H6,
   /panel/moderadores/): se añade que el nombrado (y el retirado) se enteren
   por mensaje privado — y este candado lo deja por escrito.
"""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


class AvisoDeRetenidosPorVoces(TestCase):
    def setUp(self):
        cache.clear()
        self.su = User.objects.create_superuser(username='su628',
                                                email='su628@example.org',
                                                password='x')
        self.mod = User.objects.create_user(username='mod628',
                                            email='mod628@example.org',
                                            password='x', level='MOD')
        self.normal = User.objects.create_user(username='u628',
                                               email='u628@example.org',
                                               password='x')
        self.post = Post.objects.create(author=self.normal,
                                        status='PENDING_VALIDATION',
                                        url='https://youtu.be/s628',
                                        slug='video-628', title='Retenido')

    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(False, 'faltan voces.'))
    def test_el_retenido_avisa_a_moderacion_y_superusuario(self, _g, _l):
        call_command('verificar_atrasados', stdout=StringIO())
        for quien in (self.su, self.mod):
            aviso = quien.notifications.filter(text__icontains='retenido por voces')
            self.assertEqual(aviso.count(), 1, quien.username)
            self.assertIn('/post/video-628', aviso.first().url)
        self.assertFalse(self.normal.notifications.filter(
            text__icontains='retenido').exists())

    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(False, 'faltan voces.'))
    def test_dos_barridos_el_mismo_dia_no_martillean(self, _g, _l):
        call_command('verificar_atrasados', stdout=StringIO())
        call_command('verificar_atrasados', stdout=StringIO())
        self.assertEqual(self.su.notifications.filter(
            text__icontains='retenido por voces').count(), 1)


class NombramientoAvisado(TestCase):
    def setUp(self):
        self.su = User.objects.create_superuser(username='su628b',
                                                email='su628b@example.org',
                                                password='x')
        self.user = User.objects.create_user(username='futuro-mod',
                                             email='fm628@example.org',
                                             password='x')
        self.client.force_login(self.su)

    def test_nombrar_por_email_funciona_y_avisa(self):
        self.client.post('/panel/moderadores/', {'ident': 'fm628@example.org',
                                                 'action': 'add'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.level, 'MOD')
        self.assertTrue(self.user.notifications.filter(
            text__icontains='nombrado MODERADOR').exists())

    def test_retirar_conserva_contribuidor_y_avisa(self):
        self.user.level = 'MOD'
        self.user.save(update_fields=['level'])
        self.client.post('/panel/moderadores/', {'ident': 'futuro-mod',
                                                 'action': 'remove'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.level, 'CONTRIB')
        self.assertTrue(self.user.notifications.filter(
            text__icontains='etapa como moderador termina').exists())
