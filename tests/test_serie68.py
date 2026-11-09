"""Serie 6.8 (orden de David, 2026-11-09, literal: «prefiero adelantar Qwen
antes que claude, siempre. Haz lo posible porque eso suceda» / «vamos a
intentar que Qwen sea lo principal, como sea»): Qwen se agota (reintento, y
recortado si la entrada era larga) ANTES de pagar el respaldo de Claude, y
cada fallo deja en el log el tamaño de la entrada y el cuerpo del error de
DashScope — los datos para decidir recortes de fabrica.
"""
from unittest import mock

from django.test import TestCase, override_settings


@override_settings(MOCK_AGENTS=False)
class QwenSeAgotaAntesDelRespaldo(TestCase):
    def test_un_tropiezo_puntual_se_resuelve_sin_claude(self):
        from apps.agents import client
        llamadas = []

        def qwen_falla_una_vez(model, system, content, *a, **kw):
            llamadas.append(content)
            if len(llamadas) == 1:
                raise RuntimeError('400 Bad Request simulado')
            return ('{"ok": true}', model, 1, [])

        with mock.patch('apps.agents.qwen.call_with_search',
                        side_effect=qwen_falla_una_vez):
            texto, usado, n = client.call_with_search(
                'qwen3.8-max', 'sistema', 'expediente corto',
                fallback='claude-opus-4-8')
        self.assertEqual(len(llamadas), 2)          # reintento CON QWEN
        self.assertEqual(usado, 'qwen3.8-max')      # Claude ni se tocó
        self.assertIn('ok', texto)

    def test_la_entrada_larga_se_reintenta_recortada(self):
        from apps.agents import client
        llamadas = []
        largo = 'x' * 6000

        def qwen_exige_recorte(model, system, content, *a, **kw):
            llamadas.append(content)
            if len(content) > 5000:
                raise RuntimeError('entrada demasiado larga')
            return ('{"ok": true}', model, 1, [])

        with mock.patch('apps.agents.qwen.call_with_search',
                        side_effect=qwen_exige_recorte):
            texto, usado, _n = client.call_with_search(
                'qwen3.8-max', 'sistema', largo, fallback='claude-opus-4-8')
        self.assertEqual(usado, 'qwen3.8-max')
        self.assertIn('expediente recortado', llamadas[1])
        self.assertTrue(llamadas[1].startswith('xx'))   # conserva el principio
        self.assertTrue(llamadas[1].endswith('xx'))     # y el final (la misión)

    def test_el_log_apunta_tamano_e_intentos_antes_del_respaldo(self):
        from apps.agents import client
        with mock.patch('apps.agents.qwen.call_with_search',
                        side_effect=RuntimeError('400 simulado')), \
             mock.patch.object(client, '_avisar_suplente'), \
             self.assertLogs('agents.client', level='WARNING') as log, \
             self.assertRaises(Exception):
            # Sin respaldo: tras agotar Qwen, la excepción sube tal cual.
            client.call_with_search('qwen3.8-max', 'sis', 'exp', fallback='')
        unido = '\n'.join(log.output)
        self.assertIn('caracteres de entrada', unido)
        self.assertIn('intento 1/2', unido)
        self.assertIn('intento 2/2', unido)
        self.assertIn('agotado tras 2 intentos', unido)
