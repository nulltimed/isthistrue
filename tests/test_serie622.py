"""Serie 6.22 (ordenes de David, 2026-11-09, 21:11): backfill de atrasados
«todo de golpe», con la puerta 5.27-A intacta para lo nuevo («ni una ni
otra, tal y como está»). El comando salta los VOTOS (con la web privada no
se juntan nunca), respeta el 65 %% de voces por defecto y solo lo salta con
--sin-voces.
"""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def _correr(*args):
    out = StringIO()
    call_command('verificar_atrasados', *args, stdout=out)
    return out.getvalue()


class BarridoDeAtrasados(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username='u622', email='u622@example.org',
                                          password='x')

    def _pendiente(self, n):
        return Post.objects.create(author=self.u, status='PENDING_VALIDATION',
                                   url=f'https://youtu.be/s622{n}')

    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(True, 'ok'))
    def test_lanza_sin_esperar_votos(self, _gate, lanzar):
        p = self._pendiente(1)
        salida = _correr()
        p.refresh_from_db()
        self.assertEqual(p.status, 'FULL_QUEUED')
        lanzar.assert_called_once()
        self.assertIn('Lanzados: 1', salida)

    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(False, 'faltan voces'))
    def test_respeta_la_puerta_de_voces_por_defecto(self, _gate, lanzar):
        p = self._pendiente(2)
        salida = _correr()
        p.refresh_from_db()
        self.assertEqual(p.status, 'PENDING_VALIDATION')
        lanzar.assert_not_called()
        self.assertIn('Retenido', salida)

    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(False, 'faltan voces'))
    def test_sin_voces_salta_la_puerta(self, gate, lanzar):
        p = self._pendiente(3)
        _correr('--sin-voces')
        p.refresh_from_db()
        self.assertEqual(p.status, 'FULL_QUEUED')
        lanzar.assert_called_once()
        gate.assert_not_called()

    @patch('apps.analysis.management.commands.verificar_atrasados.launch_full_analysis')
    @patch('apps.analysis.management.commands.verificar_atrasados.identification_gate',
           return_value=(True, 'ok'))
    def test_el_limite_acota_la_tanda(self, _gate, lanzar):
        for n in (4, 5, 6):
            self._pendiente(n)
        _correr('--limite', '2')
        self.assertEqual(lanzar.call_count, 2)

    def test_la_puerta_527a_sigue_intacta(self):
        """El literal de David («tal y como está») convertido en candado: la
        puerta normal sigue exigiendo votos E identificacion."""
        import inspect
        from apps.analysis import services
        src = inspect.getsource(services.try_launch_full)
        self.assertIn("distinct_validation_votes('VALIDATE')", src)
        self.assertIn('identification_gate', src)
