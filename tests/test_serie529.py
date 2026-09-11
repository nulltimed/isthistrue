"""Serie 5.29 (ordenes de David, 2026-09-11): bocadillos en TODA la web desde un
mapa central, y el voto de moderacion del reanalisis profundo UNA vez por post."""
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u529', email='u529@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class Parche529A_MapaDeBocadillos(TestCase):
    def test_el_mapa_existe_es_amplio_y_va_en_todas_las_paginas(self):
        base = open('templates/base.html', encoding='utf-8').read()
        self.assertIn("partials/tips_map.html", base)
        mapa = open('templates/partials/tips_map.html', encoding='utf-8').read()
        filas = re.findall(r'<span data-k="([^"]+)">\{% trans "([^"]+)" %\}</span>', mapa)
        self.assertGreaterEqual(len(filas), 120)
        self.assertEqual(len({k for k, _ in filas}), len(filas), 'clave repetida')
        js = open('static/js/tips.js', encoding='utf-8').read()
        selectores = dict(re.findall(r'^    (b\d{3}): "([^"]+)"', js, re.M))
        self.assertEqual(set(selectores), {k for k, _ in filas}, 'claves distintas en JS y plantilla')
        self.assertEqual(len(set(selectores.values())), len(selectores), 'selector repetido')
        for k, texto in filas:
            self.assertTrue(texto.strip().endswith(('.', '…')), texto)
        # el HTML no lleva selectores: los tests de «no debe verse X» siguen valiendo
        self.assertNotIn('data-sel=', mapa)
        self.assertIn("getElementById('tips-map')", js)
        self.assertIn("htmx:afterSwap", js)
        self.assertIn("closest('label')", js)

    def test_la_portada_lleva_el_mapa_renderizado(self):
        html = self.client.get('/').content.decode()
        self.assertIn('<template id="tips-map">', html)
        self.assertIn('data-k="b001"', html)
        self.assertIn('Portada: los últimos análisis.', html)


class Parche529B_VotoDeModeracionUnaVez(TestCase):
    def test_el_voto_del_admin_relanza_el_post_una_sola_vez(self):
        from apps.analysis.tasks import maybe_trigger_opus_rescan
        root = make_user(username='root529', email='root529@example.org',
                         is_superuser=True, is_staff=True)
        post = Post.objects.create(author=make_user(username='a529', email='a529@example.org'),
                                   url='https://youtu.be/r529', status='DONE')
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            self.assertTrue(maybe_trigger_opus_rescan(post, root))
        tarea.assert_called_once()
        self.assertFalse(tarea.call_args.kwargs.get('forced'))
        post.opus_rescanned = True
        post.save(update_fields=['opus_rescanned'])
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            self.assertFalse(maybe_trigger_opus_rescan(post, root))
        tarea.assert_not_called()

    def test_la_llave_inglesa_sigue_pudiendo_forzar(self):
        from apps.analysis.tasks import opus_rescan
        post = Post.objects.create(author=make_user(username='b529', email='b529@example.org'),
                                   url='https://youtu.be/w529', status='DONE', opus_rescanned=True)
        self.assertEqual(opus_rescan(post.pk), 'skip')
        with mock.patch('apps.agents.verdict.run'), \
                mock.patch('apps.analysis.tasks._submit_batch', return_value=False), \
                mock.patch('apps.panel.services.alert_admin'):
            self.assertEqual(opus_rescan(post.pk, forced=True, skip_charge=True), 'rescanned')
