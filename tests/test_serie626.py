"""Serie 6.26 (orden de David, 2026-11-09, 21:32, literal: «Quiero que TODAS
las frases de TODOS los interlocutores se analicen en el primer análisis
tanto por votos de los usuarios como por único voto del superusuario o
moderador»).

La cobertura total del primer analisis ya la vigila test_serie623 (un claim
por CADA frase con señal, de cualquier interlocutor). Lo que faltaba era la
PUERTA: el voto unico de moderador/superusuario solo valia en «modo
arranque» (<50 usuarios activos) y habria muerto en silencio al crecer.
Desde la 6.26 vale SIEMPRE, tambien para el rescate de Off-Topic. La puerta
de identificacion (65 %) no cambia.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post, ValidationVote
from apps.analysis.services import cast_vote, votes_needed

User = get_user_model()


class VotoUnicoDeModeradorSiempre(TestCase):
    def setUp(self):
        self.su = User.objects.create_superuser(username='su626',
                                                email='su626@example.org',
                                                password='x')
        self.normal = User.objects.create_user(username='u626',
                                               email='u626@example.org',
                                               password='x')
        self.post = Post.objects.create(author=self.normal,
                                        status='PENDING_VALIDATION',
                                        url='https://youtu.be/s626')

    @patch('apps.analysis.services.startup_mode_active', return_value=False)
    def test_el_voto_del_superusuario_vale_por_todos_fuera_del_arranque(self, _s):
        """Antes: fuera del modo arranque hacian falta 5. Ahora: 1 y SIEMPRE."""
        ValidationVote.objects.create(post=self.post, user=self.su,
                                      kind='VALIDATE')
        self.assertEqual(votes_needed(self.post), 1)

    def test_el_voto_de_un_usuario_normal_no_abre_solo(self):
        ValidationVote.objects.create(post=self.post, user=self.normal,
                                      kind='VALIDATE')
        self.assertGreaterEqual(votes_needed(self.post), 5)

    @patch('apps.analysis.services.identification_gate', return_value=(True, 'ok'))
    @patch('apps.analysis.tasks.launch_full_analysis')
    def test_su_voto_lanza_el_primer_analisis(self, lanzar, _gate):
        ok, msg = cast_vote(self.post, self.su, 'VALIDATE')
        self.assertTrue(ok)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'FULL_QUEUED')
        lanzar.assert_called_once()

    @patch('apps.analysis.services.identification_gate', return_value=(False, 'faltan voces'))
    @patch('apps.analysis.tasks.launch_full_analysis')
    def test_la_puerta_de_voces_sigue_mandando(self, lanzar, _gate):
        """David (21:11): la puerta queda «tal y como está» — el atajo del
        moderador cubre los VOTOS, no la identificacion."""
        cast_vote(self.post, self.su, 'VALIDATE')
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'PENDING_VALIDATION')
        lanzar.assert_not_called()
