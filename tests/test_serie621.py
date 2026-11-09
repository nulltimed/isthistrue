"""Serie 6.21 (respuestas de David, 2026-11-09, 12:53): «sí» al aviso diario
de gasto (umbral en el panel, campana + email, UNA vez al dia, SIN frenar
nada), «sí» al total mensual grande en /gastos/, y fusible 100 % MANUAL
(no se construye ningun encendido automatico de los limites).
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.analysis import costs
from apps.panel.models import SystemSetting

User = get_user_model()


class AvisoDiarioDeGasto(TestCase):
    def setUp(self):
        cache.clear()
        self.su = User.objects.create_superuser(username='su621',
                                                email='su621@example.org',
                                                password='x')

    def _umbral(self, valor):
        SystemSetting.objects.update_or_create(key='spend_alert_daily_eur',
                                               defaults={'value': valor})

    def test_cruzar_el_umbral_avisa_una_sola_vez(self):
        self._umbral('1')
        costs.record('anthropic', 'prueba', 2.0)
        avisos = self.su.notifications.filter(text__icontains='Gasto de hoy')
        self.assertEqual(avisos.count(), 1)
        costs.record('anthropic', 'prueba', 2.0)   # mismo dia: no repite
        self.assertEqual(self.su.notifications.filter(
            text__icontains='Gasto de hoy').count(), 1)

    def test_a_cero_esta_apagado(self):
        self._umbral('0')
        costs.record('anthropic', 'prueba', 50.0)
        self.assertFalse(self.su.notifications.filter(
            text__icontains='Gasto de hoy').exists())

    def test_el_aviso_jamas_frena_el_apunte(self):
        from apps.analysis.models import CostEntry
        self._umbral('1')
        costs.record('anthropic', 'prueba', 2.0)
        self.assertEqual(CostEntry.objects.count(), 1)

    def test_el_umbral_esta_en_el_panel(self):
        from apps.panel.views import SETTINGS_DEF
        self.assertIn('spend_alert_daily_eur', [k for k, *_r in SETTINGS_DEF])


class TotalMensualGrande(TestCase):
    def test_gastos_abre_con_el_total_del_mes(self):
        html = self.client.get('/gastos/').content.decode()
        self.assertIn('gasto-total-mes', html)
        self.assertIn('gastados este mes', html)
