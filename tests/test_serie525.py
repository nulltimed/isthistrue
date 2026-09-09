"""Serie 5.25 (ordenes de David, 2026-09-09): la ficha de persona con los
videos al principio; la pagina de emergencia del host con texto aprobado."""
from django.test import TestCase


class Parche525A_VideosAlPrincipio(TestCase):
    def test_la_seccion_videos_va_antes_que_las_estadisticas_y_los_claims(self):
        t = open('templates/analysis/person_detail.html', encoding='utf-8').read()
        i_videos = t.index('Vídeos donde aparece')
        self.assertLess(i_videos, t.index('Análisis de sus intervenciones'))
        self.assertLess(i_videos, t.index('{% for g in grupos %}'))
        self.assertGreater(i_videos, t.index('person-legal'), 'debajo de la cabecera y del aviso legal')

    def test_la_pagina_de_emergencia_tiene_el_texto_nuevo(self):
        p = open('nginx/panic.html', encoding='utf-8').read()
        self.assertNotIn('pausado por el administrador', p)
        self.assertIn('Estamos actualizando la web', p)
        self.assertIn('http-equiv="refresh"', p, 'se recarga sola al volver el servicio')
