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


class Parche525C_NombreEsestocierto(TestCase):
    """C (orden de David): el proyecto se llama esestocierto — ni «isthistrue.»
    ni «escierto.» de cara al usuario (plantillas, correos, feeds, tarjetas)."""

    def test_ni_una_plantilla_ni_el_catalogo_llevan_el_nombre_viejo(self):
        import glob, re
        malos = []
        for f in glob.glob('templates/**/*.html', recursive=True):
            t = open(f, encoding='utf-8').read()
            t = re.sub(r'https://github\.com/nulltimed/isthistrue[^"\s]*', '', t)   # el repo se llama asi
            t = re.sub(r'[\w.-]*xyztserver\.com', '', t)                              # hosts historicos (redirigen)
            if re.search(r'isthistrue\.|(?<![a-z])escierto\.(?!com)', t):
                malos.append(f)
        self.assertEqual(malos, [])
        po = open('locale/en/LC_MESSAGES/django.po', encoding='utf-8').read()
        self.assertNotIn('isthistrue./escierto.', po)
        html = self.client.get('/donaciones/').content.decode()
        self.assertIn('esestocierto? es un proyecto open source', html)
        self.assertIn('og:site_name" content="esestocierto?"', html)

    def test_correos_feeds_y_logo_con_el_nombre_nuevo(self):
        from django.test import RequestFactory
        from config.context_processors import logo_variant
        from apps.wiki import feeds
        self.assertIn('esestocierto?', feeds.RecentVerdictsFeed.title)
        for host in ('esestocierto.com', 'wiki.esestocierto.com', 'isthistrue.xyztserver.com'):
            self.assertEqual(logo_variant(RequestFactory().get('/', HTTP_HOST=host))['logo_variant'], 'escierto')
        import inspect
        from apps.accounts import services, verification
        self.assertIn("esestocierto:", inspect.getsource(services.notify))
        self.assertIn("esestocierto?", inspect.getsource(verification))
