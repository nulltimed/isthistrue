"""Serie 6.29 (respuestas de David, 2026-11-09, 21:46): email con MINI-GUIA al
nombrar moderador («sí») y AVISOS TOTALES de retenidos por voces — no solo en
el barrido: tambien cuando el video nace retenido tras la fase barata y cuando
los votos llegan pero la puerta de voces sigue cerrada.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase

from apps.analysis.models import Post
from apps.analysis.services import cast_vote, open_validation_window
from apps.panel.models import SystemSetting

User = get_user_model()


class EmailGuiaAlNombrar(TestCase):
    def test_el_nombrado_recibe_la_mini_guia(self):
        su = User.objects.create_superuser(username='su629', email='su629@example.org',
                                           password='x')
        User.objects.create_user(username='alvaro629', email='alvaro629@example.org',
                                 password='x')
        self.client.force_login(su)
        self.client.post('/panel/moderadores/', {'ident': 'alvaro629', 'action': 'add'})
        guia = [m for m in mail.outbox if 'mini-guía' in m.subject]
        self.assertEqual(len(guia), 1)
        cuerpo = guia[0].body
        for poder in ('VOTO ÚNICO', 'Verificar ya', 'QUIÉN HABLA', 'LLAVE INGLESA',
                      'FORO', 'los veredictos no se venden'):
            self.assertIn(poder, cuerpo)
        self.assertEqual(guia[0].to, ['alvaro629@example.org'])


class AvisosTotalesDeRetenidos(TestCase):
    def setUp(self):
        cache.clear()
        self.su = User.objects.create_superuser(username='su629b',
                                                email='su629b@example.org',
                                                password='x')
        self.autor = User.objects.create_user(username='u629', email='u629@example.org',
                                              password='x')

    def _retenidos_del_su(self):
        return self.su.notifications.filter(text__icontains='retenido por voces')

    @patch('apps.analysis.services.identification_gate', return_value=(False, 'faltan voces.'))
    def test_el_video_que_nace_retenido_avisa_al_momento(self, _g):
        post = Post.objects.create(author=self.autor, url='https://youtu.be/s629a',
                                   slug='video-629a')
        open_validation_window(post)
        self.assertEqual(self._retenidos_del_su().count(), 1)

    @patch('apps.analysis.services.identification_gate', return_value=(True, 'ok'))
    def test_con_la_puerta_abierta_no_hay_aviso(self, _g):
        post = Post.objects.create(author=self.autor, url='https://youtu.be/s629b')
        open_validation_window(post)
        self.assertEqual(self._retenidos_del_su().count(), 0)

    @patch('apps.analysis.services.identification_gate', return_value=(False, 'faltan voces.'))
    def test_votos_completos_con_voces_cerradas_avisan(self, _g):
        SystemSetting.objects.update_or_create(key='votes_to_validate',
                                               defaults={'value': '1'})
        post = Post.objects.create(author=self.autor, status='PENDING_VALIDATION',
                                   url='https://youtu.be/s629c', slug='video-629c')
        votante = User.objects.create_user(username='v629', email='v629@example.org',
                                           password='x', karma=100)
        ok, msg = cast_vote(post, votante, 'VALIDATE')
        self.assertTrue(ok)
        self.assertEqual(self._retenidos_del_su().count(), 1)
        self.assertIn('/post/video-629c', self._retenidos_del_su().first().url)
