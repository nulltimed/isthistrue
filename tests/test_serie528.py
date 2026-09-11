"""Serie 5.28 (reportes de David, 2026-09-11): los bocadillos no se salen de la
ventana (tips.js decide el lado) y el semaforo lleva la transcripcion a la frase."""
from django.test import TestCase


class Parche528A_BocadillosDentroDeLaVentana(TestCase):
    def test_tips_js_se_carga_y_el_css_tiene_los_anclajes(self):
        base = open('templates/base.html', encoding='utf-8').read()
        self.assertIn("js/tips.js", base)
        css = open('static/css/main.css', encoding='utf-8').read()
        for sel in ('.tip-izq::after', '.tip-der::after', '.tip-abajo-auto::after', '.tip-visible::after'):
            self.assertIn(sel, css, sel)
        js = open('static/js/tips.js', encoding='utf-8').read()
        self.assertIn("getComputedStyle(el, '::after')", js)
        self.assertIn('window.innerWidth', js)
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
