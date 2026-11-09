"""Serie 6.20 (orden de David, 2026-11-09, 12:40, literal: «Elimina los
límites diarios y mensuales, pero mantenlos en el panel de superusuario»).

El interruptor `budget_limits_enabled` (panel, APAGADO de fabrica en
produccion) decide si los topes 4.3-F frenan o no. Apagado: ningun freno —
ni deposito diario, ni techo mensual, ni cola por presupuesto — pero el
gasto SE SIGUE APUNTANDO integro (el libro no miente). Encendido: los
frenos vuelven tal cual. Las ruedas (base, techo) siguen en el panel.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import DailyBudget, MonthlyCap, Post
from apps.analysis.services import budget_left_today, needs_sponsorship
from apps.panel.models import SystemSetting

User = get_user_model()


def _interruptor(valor):
    SystemSetting.objects.update_or_create(key='budget_limits_enabled',
                                           defaults={'value': valor})


class LimitesDeGastoConInterruptor(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username='u620', email='u620@example.org',
                                          password='x')
        # topes ridiculos: con el interruptor encendido frenan seguro
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '0'})
        SystemSetting.objects.update_or_create(key='budget_hard_ceiling_eur',
                                               defaults={'value': '0'})

    def test_apagado_nada_frena_pero_todo_se_apunta(self):
        _interruptor('0')
        self.assertTrue(DailyBudget.try_spend(5.0))
        self.assertTrue(MonthlyCap.try_spend(5.0))
        fila = DailyBudget.objects.first()
        self.assertGreaterEqual(float(fila.spent_eur), 5.0,   # el libro no miente
                                'el gasto tiene que apuntarse aunque no frene')
        self.assertEqual(budget_left_today(), float('inf'))
        p = Post(author=self.u, url='https://youtu.be/s620', duration_seconds=7200)
        a_la_cola, _coste, _sug = needs_sponsorship(p)
        self.assertFalse(a_la_cola, 'sin límites no hay cola por presupuesto')

    def test_encendido_los_frenos_vuelven_tal_cual(self):
        _interruptor('1')
        self.assertFalse(DailyBudget.try_spend(5.0),
                         'con el interruptor encendido el tope diario frena')
        self.assertNotEqual(budget_left_today(), float('inf'))

    def test_el_interruptor_esta_en_el_panel(self):
        from apps.panel.views import SETTINGS_DEF
        claves = [k for k, *_r in SETTINGS_DEF]
        self.assertIn('budget_limits_enabled', claves)
        from django.conf import settings
        self.assertIn('budget_limits_enabled', settings.SETTING_DEFAULTS)
