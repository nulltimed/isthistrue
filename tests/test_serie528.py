"""Serie 5.28 (reportes de David, 2026-09-11): los bocadillos no se salen de la
ventana (tips.js decide el lado) y el semaforo lleva la transcripcion a la frase."""
from django.test import TestCase


class Parche528A_BocadillosDentroDeLaVentana(TestCase):
    def test_tips_js_se_carga_y_el_globo_no_se_sale_de_la_ventana(self):
        base = open('templates/base.html', encoding='utf-8').read()
        self.assertIn("js/tips.js", base)
        css = open('static/css/main.css', encoding='utf-8').read()
        # 5.30-C: un globo flotante (fixed, fuera de toda caja con scroll); el
        # ::after queda de respaldo sin JS
        self.assertIn('#tip-globo{position:fixed;z-index:9999', css)
        self.assertIn('html.tips-js [data-tip]::after{display:none!important}', css)
        js = open('static/js/tips.js', encoding='utf-8').read()
        self.assertIn("globo.id = 'tip-globo'", js)
        self.assertIn('window.innerWidth - w - MARGEN', js)     # no se sale por los lados
        self.assertIn('y = r.bottom + 7', js)                   # abajo si no cabe arriba
        self.assertIn("closest('dialog[open]')", js)            # dentro de un dialog modal
        self.assertIn('touchstart', js)


class Parche528B_SemaforoALaFrase(TestCase):
    def test_el_semaforo_llama_a_irAFrase_y_transcript_la_define(self):
        js = open('static/js/transcript.js', encoding='utf-8').read()
        self.assertIn('window.irAFrase = function', js)
        self.assertIn("box.scrollTo({ top: box.scrollTop + (r.top - rb.top) - 4", js)
        t = open('templates/analysis/post_detail.html', encoding='utf-8').read()
        self.assertEqual(t.count('irAFrase({{ f.s }})'), 2)
        w = open('templates/wiki/video.html', encoding='utf-8').read()
        self.assertIn('irAFrase({{ f.t }})', w)
