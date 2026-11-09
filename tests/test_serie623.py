"""Serie 6.23 (orden de David, 2026-11-09, 21:18, literal: «SIEMPRE se deben
analizar TODAS las frases. Repito: siempre»): los claims en gris (UNDECIDED)
se reintentan solos cada noche con busquedas frescas, pasados grey_retry_days
dias de su ultima version. El reloj es la ultima ClaimVersion: cada intento
pospone el siguiente (insistencia sin martilleo). 0 lo apaga.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.analysis.models import Post, TranscriptSegment
from apps.analysis.tasks import reclarify_grey_claims
from apps.panel.models import SystemSetting
from apps.wiki.models import Claim, ClaimAppearance, ClaimVersion

User = get_user_model()


class ReintentoEternoDeGrises(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username='u623', email='u623@example.org',
                                          password='x')

    def _gris(self, dias, status='DONE', color='UNDECIDED'):
        post = Post.objects.create(author=self.u, status=status,
                                   url=f'https://youtu.be/s623{dias}{color}')
        seg = TranscriptSegment.objects.create(post=post, start_seconds=0,
                                               end_seconds=5, text='frase')
        claim = Claim.objects.create(title=f'c{dias}{color}',
                                     slug=f'c623-{dias}-{color.lower()}',
                                     text_original='frase', color=color)
        ClaimAppearance.objects.create(claim=claim, segment=seg)
        v = ClaimVersion.objects.create(claim=claim, color=color, body_snapshot={})
        ClaimVersion.objects.filter(pk=v.pk).update(
            created_at=timezone.now() - timedelta(days=dias))
        return post

    @patch('apps.agents.clarify.run_pending', return_value=1)
    def test_el_gris_viejo_se_reintenta(self, run):
        post = self._gris(5)
        reclarify_grey_claims()
        run.assert_called_once()
        self.assertEqual(run.call_args[0][0].pk, post.pk)

    @patch('apps.agents.clarify.run_pending', return_value=1)
    def test_el_gris_reciente_espera_su_turno(self, run):
        self._gris(1)   # ultimo intento hace 1 dia < 3 de fabrica
        reclarify_grey_claims()
        run.assert_not_called()

    @patch('apps.agents.clarify.run_pending', return_value=1)
    def test_a_cero_se_apaga(self, run):
        SystemSetting.objects.update_or_create(key='grey_retry_days',
                                               defaults={'value': '0'})
        self._gris(30)
        reclarify_grey_claims()
        run.assert_not_called()

    @patch('apps.agents.clarify.run_pending', return_value=1)
    def test_un_claim_con_color_no_se_toca(self, run):
        self._gris(30, color='GREEN')
        reclarify_grey_claims()
        run.assert_not_called()

    def test_la_tarea_esta_en_el_beat(self):
        from config.celery import app
        tareas = [e['task'] for e in app.conf.beat_schedule.values()]
        self.assertIn('apps.analysis.tasks.reclarify_grey_claims', tareas)
