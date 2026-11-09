"""Serie 6.19 (2026-11-09): los NEW huerfanos ya no se quedan colgados.

Caza del post de Abascal: con el deposito diario vacio, run_cheap_phase
rebota el post a NEW prometiendo «se reintentara cuando haya deposito» —
pero ninguna tarea barria los NEW (launch_queued_analyses solo recogia
AWAITING_BUDGET y relaunch_stuck_analyses solo mira RUNNING). El post
quedaba «Nuevo» y «Sin transcripcion todavia» PARA SIEMPRE, en silencio.

Candado: la tarea horaria recoge tambien los NEW huerfanos (mas de 30 min,
sin transcripcion, sin trabajo AAI en vuelo) cuando el presupuesto da, y
respeta el orden de llegada y el freno de presupuesto de la cola.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.analysis.models import Post
from apps.analysis.tasks import launch_queued_analyses

User = get_user_model()


class RescateDeNuevosHuerfanos(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username='u619', email='u619@example.org',
                                          password='x')

    def _nuevo(self, minutos, **kw):
        p = Post.objects.create(author=self.u, status='NEW',
                                url=f'https://youtu.be/s619{minutos}', **kw)
        # created_at es auto_now_add: se retrocede a mano para simular la espera
        Post.objects.filter(pk=p.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutos))
        return p

    @patch('apps.analysis.services.budget_left_today', return_value=50.0)
    @patch('apps.analysis.tasks.run_cheap_phase')
    def test_el_huerfano_viejo_se_relanza(self, cheap, _b):
        p = self._nuevo(45)
        launch_queued_analyses()
        cheap.delay.assert_called_once_with(p.pk)

    @patch('apps.analysis.services.budget_left_today', return_value=50.0)
    @patch('apps.analysis.tasks.run_cheap_phase')
    def test_el_recien_posteado_se_deja_en_paz(self, cheap, _b):
        self._nuevo(5)   # acaba de llegar: su .delay original sigue en vuelo
        launch_queued_analyses()
        cheap.delay.assert_not_called()

    @patch('apps.analysis.services.budget_left_today', return_value=0.0)
    @patch('apps.analysis.tasks.run_cheap_phase')
    def test_sin_presupuesto_no_se_relanza_nada(self, cheap, _b):
        self._nuevo(45)
        launch_queued_analyses()
        cheap.delay.assert_not_called()

    @patch('apps.analysis.services.budget_left_today', return_value=50.0)
    @patch('apps.analysis.tasks.run_cheap_phase')
    def test_un_aai_en_vuelo_no_se_toca(self, cheap, _b):
        self._nuevo(45, aai_job_id='trabajo-remoto')
        launch_queued_analyses()
        cheap.delay.assert_not_called()
