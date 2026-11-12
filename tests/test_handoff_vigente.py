"""Candado del handoff (orden de David, 2026-11-12).

El handoff debe permitir que un chat NUEVO retome el proyecto sin que David explique
nada. El 12-nov se descubrió que llevaba semanas remendándose por líneas y que el
prompt de arranque describía un régimen que ya no existía. Este test no puede saber
si el contenido es bueno, pero sí caza las dos formas en que se pudrió.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
HANDOFF = RAIZ / 'docs' / '21-handoff-operador-claude-code.md'


class HandoffVigenteTests(SimpleTestCase):
    def setUp(self):
        self.texto = HANDOFF.read_text(encoding='utf-8')
        corte = self.texto.index('# HISTÓRICO')
        self.vigente = self.texto[:corte]

    def test_el_prompt_de_arranque_va_el_primero(self):
        self.assertLess(self.texto.index('PROMPT DE ARRANQUE'), 600,
                        'El prompt de arranque debe abrir el documento.')
        self.assertLess(self.texto.index('PROMPT DE ARRANQUE'),
                        self.texto.index('§0. ESTADO EXACTO'))

    def test_el_prompt_describe_el_canal_actual(self):
        prompt = self.vigente.split('```')[1]
        for pieza in ('nulltimed/isthistrue', 'castellano', 'TRES preguntas',
                      'bash desplegar.sh', 'UNA sola línea', 'CLAUDE.md', 'README.md'):
            self.assertIn(pieza, prompt, f'Falta «{pieza}» en el prompt de arranque.')
        # El régimen de agosto (operador dentro del VPS) no puede volver al prompt.
        self.assertNotIn('operador de despliegue', prompt)
        self.assertNotIn('VPS REAL', prompt)

    def test_el_estado_lleva_fecha_y_apartados(self):
        self.assertRegex(self.vigente, r'§0\. ESTADO EXACTO — actualizado el \d{4}-\d{2}-\d{2}')
        for apartado in ('### Producción', '### Órdenes permanentes de David',
                         '### Pendientes abiertos', '### Oficio de este canal'):
            self.assertIn(apartado, self.vigente)

    def test_la_parte_vigente_se_puede_leer(self):
        # La podredumbre empezó con una sola línea de 7.000 caracteres parcheada con sed.
        largas = [n for n, linea in enumerate(self.vigente.split('\n'), 1) if len(linea) > 400]
        self.assertEqual(largas, [], f'Líneas ilegibles en la parte vigente: {largas}')

    def test_no_se_cuelan_secretos(self):
        self.assertIsNone(re.search(r'hf_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9-]{20,}|rpa_[A-Za-z0-9]{20,}',
                                    self.texto))
