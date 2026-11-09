"""Serie 6.5 (orden de David, 2026-11-09): producto — «aplica todo salvo lo
que tenga que esperar a la SL» + regla permanente «para cada cambio nuevo
intenta implementar un sistema de revenue».

Cubre: (1) el reparador de JSON truncado del cliente (tanda real del
2026-11-08: 16 de 31 rastreos fallaron con json_parse porque qwen3.8-max
truncaba por max_tokens); (2) el bulo de la semana en la portada (manual por
featured_claim_slug o automatico); (3) el marcado ClaimReview de schema.org
en las fichas (el canal de captacion que no cuesta un euro);
(4) el comando rastrear_origen (adios a los one-liners por chat).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u65', email='u65@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def _claim_rojo_con_cadena(slug='bulo-65', consolidated=True):
    from apps.wiki.models import Claim
    return Claim.objects.create(
        text_original='el café cura el cáncer', slug=slug, color='RED',
        consolidated=consolidated, what_evidence_says='No lo cura.',
        origin_chain=[
            {'kind': 'study', 'date': '2013-02-25', 'title': 'El estudio',
             'url': 'https://example.org/e', 'note': '', 'twisted': False},
            {'kind': 'press', 'date': '2013-03-01', 'title': 'El titular',
             'url': 'https://example.org/p', 'note': 'aquí se torció',
             'twisted': True},
        ], origin_status='DONE')


class ReparadorDeJsonTruncado(TestCase):
    """El JSON cortado por max_tokens se repara cerrando lo abierto; si el
    corte cayo a mitad de un eslabon, ese eslabon se descarta y el resto
    sobrevive. Jamas se inventa contenido."""

    def test_cierra_llaves_y_corchetes_pendientes(self):
        from apps.agents.client import _salvage_json
        v = _salvage_json('{"chain": [{"kind": "press", "url": "https://x.org"}')
        self.assertEqual(v['chain'][0]['kind'], 'press')

    def test_corte_en_mitad_de_una_cadena_descarta_el_eslabon_a_medias(self):
        from apps.agents.client import _salvage_json
        v = _salvage_json('{"chain": [{"kind": "press", "url": "https://x.org"},'
                          ' {"kind": "study", "title": "a medias y sin cerr')
        self.assertEqual(len(v['chain']), 1)   # el eslabon truncado, fuera
        self.assertEqual(v['chain'][0]['kind'], 'press')

    def test_corte_despues_de_una_clave_sin_valor(self):
        from apps.agents.client import _salvage_json
        v = _salvage_json('{"summary": "nacio en prensa", "chain": [{"kind": '
                          '"press", "url": "https://x.org"}], "extra":')
        self.assertEqual(v['summary'], 'nacio en prensa')
        self.assertEqual(len(v['chain']), 1)

    def test_la_basura_sin_remedio_sigue_siendo_error(self):
        from apps.agents.client import _salvage_json
        self.assertIsNone(_salvage_json('esto no es json ni lo sera'))

    def test_un_escape_dentro_de_la_cadena_no_confunde_al_reparador(self):
        from apps.agents.client import _salvage_json
        v = _salvage_json('{"summary": "dijo \\"hola\\"", "chain": '
                          '[{"kind": "press", "url": "https://x.org"}], "ex')
        self.assertEqual(v['summary'], 'dijo "hola"')
        self.assertEqual(len(v['chain']), 1)

    def test_un_texto_cortado_a_medias_no_se_publica_mutilado(self):
        # Mejor perder la respuesta que publicar un titulo o una URL a medias.
        from apps.agents.client import _salvage_json
        self.assertIsNone(_salvage_json('{"summary": "dijo \\"hola\\" y corto aqu'))


class BuloDeLaSemana(TestCase):
    def test_automatico_el_ultimo_rojo_consolidado_con_cadena(self):
        _claim_rojo_con_cadena()
        html = self.client.get('/').content.decode()
        self.assertIn('bulo-semana', html)
        self.assertIn('el café cura el cáncer', html)
        self.assertIn('/wiki/claim/bulo-65/', html)

    def test_sin_candidato_la_portada_queda_como_estaba(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('bulo-semana', html)
        self.assertIn('cta-hero', html)   # el CTA de siempre sigue ahi

    def test_el_panel_lo_fija_a_mano(self):
        from apps.panel.models import SystemSetting
        _claim_rojo_con_cadena(slug='bulo-auto')
        _claim_rojo_con_cadena(slug='bulo-mas-nuevo')   # el automatico elegiria este
        SystemSetting.objects.update_or_create(
            key='featured_claim_slug', defaults={'value': 'bulo-auto'})
        html = self.client.get('/').content.decode()
        self.assertIn('/wiki/claim/bulo-auto/', html)
        self.assertNotIn('bulo-mas-nuevo', html)

    def test_un_rojo_sin_cadena_no_sale_en_el_escaparate(self):
        from apps.wiki.models import Claim
        Claim.objects.create(text_original='rojo sin cadena', slug='sin-cadena-65',
                             color='RED', consolidated=True)
        html = self.client.get('/').content.decode()
        self.assertNotIn('bulo-semana', html)


class MarcadoClaimReview(TestCase):
    """6.5: schema.org/ClaimReview en cada ficha con veredicto — lo que leen
    Google y los agregadores de fact-checking cuando la web abra."""

    def test_la_ficha_roja_lleva_el_marcado(self):
        import json
        _claim_rojo_con_cadena()
        html = self.client.get('/wiki/claim/bulo-65/').content.decode()
        self.assertIn('application/ld+json', html)
        ini = html.index('application/ld+json')
        bloque = html[html.index('>', ini) + 1:html.index('</script>', ini)]
        datos = json.loads(bloque)
        self.assertEqual(datos['@type'], 'ClaimReview')
        self.assertEqual(datos['reviewRating']['ratingValue'], 1)   # RED
        self.assertIn('cáncer', datos['claimReviewed'])

    def test_sin_veredicto_no_hay_marcado(self):
        from apps.wiki.models import Claim
        Claim.objects.create(text_original='pendiente', slug='pend-65',
                             color='PENDING')
        html = self.client.get('/wiki/claim/pend-65/').content.decode()
        self.assertNotIn('application/ld+json', html)

    def test_las_opiniones_quedan_fuera(self):
        # Un verde de OPINION significa «fundada», no «verificada» (5.3-C):
        # etiquetarla como ClaimReview mentiria a Google.
        from apps.wiki.models import Claim
        Claim.objects.create(text_original='me parece bien', slug='opi-65',
                             color='GREEN', kind='OPINION')
        html = self.client.get('/wiki/claim/opi-65/').content.decode()
        self.assertNotIn('application/ld+json', html)


class ComandoRastrearOrigen(TestCase):
    def _claim_pendiente(self, u, status=''):
        from apps.wiki.models import Claim, ClaimAppearance
        post = Post.objects.create(author=u, url='https://youtu.be/s65',
                                   title='O65')
        seg = post.transcript_segments.create(start_seconds=5, end_seconds=7,
                                              text='frase 65')
        claim = Claim.objects.create(text_original='frase 65',
                                     slug=f'c65-{status or "nuevo"}',
                                     color='RED', origin_status=status)
        ClaimAppearance.objects.create(claim=claim, segment=seg, quote='frase 65')
        return claim

    def test_rastrea_los_pendientes_y_reintenta_failed_solo_si_se_pide(self):
        from io import StringIO
        from django.core.management import call_command
        u = make_user()
        nuevo = self._claim_pendiente(u, status='')
        fallido = self._claim_pendiente(u, status='FAILED')
        out = StringIO()
        call_command('rastrear_origen', stdout=out)
        nuevo.refresh_from_db(); fallido.refresh_from_db()
        self.assertEqual(nuevo.origin_status, 'DONE')     # el MOCK responde
        self.assertEqual(fallido.origin_status, 'FAILED')  # sin --reintentar, ni tocarlo
        call_command('rastrear_origen', '--reintentar', stdout=out)
        fallido.refresh_from_db()
        self.assertEqual(fallido.origin_status, 'DONE')
        self.assertIn('cadenas nuevas publicadas', out.getvalue())
