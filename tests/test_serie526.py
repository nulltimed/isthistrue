"""Serie 5.26 (ordenes de David, 2026-09-11): precios REALES de Qwen en el
catalogo, el libro de cuentas apunta QUE MODELO gasto, y la rueda de
categorias baja a Flash (con Haiku de respaldo)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u526', email='u526@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Parche526A_PreciosReales(TestCase):
    def test_flash_y_plus_llevan_la_tarifa_de_singapur(self):
        from apps.agents.catalog import prices
        self.assertEqual(prices('qwen3.8-flash'), (0.15, 0.47))
        self.assertEqual(prices('qwen3.7-plus'), (0.40, 1.60))
        self.assertEqual(prices('qwen3.8-max'), (2.00, 6.00))

    def test_categorias_va_con_flash_y_haiku_de_respaldo(self):
        from django.conf import settings
        from apps.agents.catalog import TASK_DEFAULTS, FALLBACK_DEFAULTS, fallback_for
        self.assertEqual(TASK_DEFAULTS['categories'], 'qwen3.8-flash')
        self.assertEqual(settings.SETTING_DEFAULTS['model_categories'], 'qwen3.8-flash')
        self.assertEqual(FALLBACK_DEFAULTS['categories'], 'claude-haiku-4-5-20251001')
        self.assertEqual(fallback_for('categories'), 'claude-haiku-4-5-20251001')
        # (5.27-D: la rueda del clasificador se retiro; su sitio lo ocupa el
        # bibliotecario, que ya existia como 'categories'.)
        self.assertNotIn('classify', TASK_DEFAULTS)


class Parche526A_LibroConModelo(TestCase):
    def test_record_guarda_el_modelo_y_sin_el_queda_vacio(self):
        from apps.analysis import costs
        from apps.analysis.models import CostEntry
        costs.record('qwen', 'analisis', 0.01, model='qwen3.8-max')
        costs.record('runpod', 'whisper', 0.01)
        self.assertEqual(CostEntry.objects.get(provider='qwen').model, 'qwen3.8-max')
        self.assertEqual(CostEntry.objects.get(provider='runpod').model, '')

    def test_el_apunte_de_qwen_lleva_el_modelo_en_tokens_y_busquedas(self):
        from apps.agents import qwen
        from apps.analysis.models import CostEntry
        qwen._apunte('qwen3.7-plus', {'input_tokens': 100000, 'output_tokens': 10000}, busquedas=2)
        modelos = set(CostEntry.objects.filter(provider='qwen').values_list('model', flat=True))
        self.assertEqual(modelos, {'qwen3.7-plus'})
        self.assertEqual(CostEntry.objects.filter(provider='qwen').count(), 2)

    def test_el_apunte_de_claude_lleva_el_modelo(self):
        from types import SimpleNamespace
        from apps.agents import client
        from apps.analysis.models import CostEntry
        client._apunte_claude('claude-sonnet-4-6',
                              SimpleNamespace(input_tokens=100000, output_tokens=1000))
        self.assertEqual(CostEntry.objects.get(provider='anthropic').model, 'claude-sonnet-4-6')


class Parche526A_PanelGastosPorModelo(TestCase):
    def setUp(self):
        from apps.analysis import costs
        costs.record('qwen', 'analisis', 3.0, model='qwen3.8-max')
        costs.record('qwen', 'analisis', 0.5, model='qwen3.7-plus')
        costs.record('qwen', 'busqueda', 0.01, model='qwen3.7-plus')
        self.client.force_login(make_user(username='gsup6', email='gsup6@example.org',
                                          is_staff=True, is_superuser=True))

    def test_resumen_por_modelo_y_filtro(self):
        html = self.client.get('/panel/gastos/?atajo=todo').content.decode()
        self.assertIn('Por modelo', html)
        self.assertIn('qwen3.8-max', html)
        html = self.client.get('/panel/gastos/?atajo=todo&modelo=3.7-plus').content.decode()
        self.assertIn('0,5100', html)          # 0,50 + 0,01 del filtro
        self.assertNotIn('3,0000', html)

    def test_el_csv_lleva_la_columna_modelo(self):
        resp = self.client.get('/panel/gastos/?atajo=todo&csv=1')
        cuerpo = resp.content.decode()
        self.assertIn('fecha;hora;servicio;concepto;modelo;post;titulo;eur', cuerpo)
        self.assertIn(';qwen3.8-max;', cuerpo)
