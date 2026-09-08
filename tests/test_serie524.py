"""Serie 5.24 (ordenes de David, 2026-09-09): PayPal por el servidor (sin
ventana emergente), RSS para los podcasts de Spotify, y el panel Gastos."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u524', email='u524@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class _R:
    def __init__(self, status_code, data, text=''):
        self.status_code, self._data, self.text = status_code, data, text or str(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


class Parche524A_PayPalPorElServidor(TestCase):
    """A: el formulario crea el pedido en el servidor y manda a paypal.com; el
    retorno captura, anota VERIFICADA (idempotente) y lanza el apadrinamiento."""

    CRED = dict(PAYPAL_CLIENT_ID='cid', PAYPAL_CLIENT_SECRET='sec')

    def _paypal(self, capture_status='COMPLETED', amount='5.00', custom='donacion'):
        def post(url, **kw):
            if url.endswith('/v1/oauth2/token'):
                return _R(200, {'access_token': 't'})
            if url.endswith('/v2/checkout/orders'):
                self.pedido = kw.get('json')
                return _R(201, {'id': 'ORD524', 'links': [
                    {'rel': 'self', 'href': 'x'},
                    {'rel': 'approve', 'href': 'https://www.paypal.com/checkoutnow?token=ORD524'}]})
            if url.endswith('/capture'):
                return _R(201, {'status': capture_status, 'payer': {'email_address': 'p@x'},
                                'purchase_units': [{'custom_id': custom, 'payments': {'captures': [
                                    {'status': 'COMPLETED', 'amount': {'currency_code': 'EUR', 'value': amount}}]}}]})
            return _R(404, {})
        return mock.patch('apps.analysis.paypal_check.requests.post', side_effect=post)

    def test_el_banner_es_un_formulario_sin_sdk(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('paypal.com/sdk/js', html)
        self.assertIn('action="/donaciones/iniciar/"', html)
        self.assertIn('Donar con PayPal', html)
        self.assertNotIn('istt-pp-cerrar', html)

    def test_iniciar_crea_el_pedido_y_redirige_a_paypal(self):
        from apps.panel.models import AuditLog
        with override_settings(**self.CRED), self._paypal():
            r = self.client.post('/donaciones/iniciar/', {'amount': '7,50'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('https://www.paypal.com/checkoutnow'))
        self.assertEqual(self.pedido['purchase_units'][0]['amount']['value'], '7.50')
        self.assertEqual(self.pedido['application_context']['locale'], 'es-ES')
        self.assertIn('/donaciones/retorno/', self.pedido['application_context']['return_url'])
        self.assertTrue(AuditLog.objects.filter(action='donation_started').exists())

    def test_cantidad_invalida_no_llega_a_paypal(self):
        with override_settings(**self.CRED), self._paypal() as pp:
            r = self.client.post('/donaciones/iniciar/', {'amount': '0.5'})
        self.assertEqual(r['Location'], '/donaciones/')
        pp.assert_not_called()

    def test_sin_credenciales_va_al_enlace_clasico(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='paypal_url', defaults={'value': 'https://paypal.me/x'})
        with override_settings(PAYPAL_CLIENT_ID='', PAYPAL_CLIENT_SECRET=''):
            r = self.client.post('/donaciones/iniciar/', {'amount': '5'})
        self.assertEqual(r['Location'], 'https://paypal.me/x')

    def test_el_retorno_captura_anota_verificada_y_es_idempotente(self):
        from apps.panel.models import Donation
        from apps.panel.services import live_monthly_cap
        cap_antes, _, _ = live_monthly_cap()
        with override_settings(**self.CRED), self._paypal(amount='5.00'):
            r1 = self.client.get('/donaciones/retorno/?token=ORD524&PayerID=P')
            r2 = self.client.get('/donaciones/retorno/?token=ORD524&PayerID=P')
        self.assertEqual(r1.status_code, 302)
        self.assertEqual(Donation.objects.filter(note='paypal-web:ORD524').count(), 1)
        d = Donation.objects.get(note='paypal-web:ORD524')
        self.assertTrue(d.verified, 'la captura la hizo el servidor: nace verificada')
        self.assertEqual(d.amount_eur, Decimal('5.00'))
        cap_despues, _, _ = live_monthly_cap()
        self.assertGreater(cap_despues, cap_antes, 'una donacion verificada sube el tope')
        self.assertEqual(r2.status_code, 302)

    def test_el_apadrinamiento_atado_lanza_el_analisis_al_volver(self):
        from apps.panel.models import Donation
        u = make_user()
        post = Post.objects.create(author=u, url='https://youtu.be/ap524', title='En cola',
                                   status='AWAITING_BUDGET', duration_seconds=600)
        with override_settings(**self.CRED), self._paypal(amount='99.00', custom=f'post:{post.pk}'), \
             mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanza:
            r = self.client.get('/donaciones/retorno/?token=ORD524')
        post.refresh_from_db()
        self.assertEqual(post.status, 'PENDING')
        lanza.assert_called_once_with(post.pk)
        self.assertEqual(Donation.objects.get(note='paypal-web:ORD524').post_id, post.pk)
        self.assertEqual(r['Location'], post.get_absolute_url())
        # y el boton de apadrinar es un formulario al servidor con la cantidad exacta
        post.status = 'AWAITING_BUDGET'
        post.save(update_fields=['status'])
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('action="/donaciones/iniciar/"', html)
        self.assertIn(f'name="post" value="{post.pk}"', html)
        self.assertNotIn('paypal.Buttons', html)

    def test_una_captura_fallida_no_anota_nada(self):
        from apps.panel.models import AuditLog, Donation
        with override_settings(**self.CRED), self._paypal(capture_status='DECLINED', amount='0'):
            r = self.client.get('/donaciones/retorno/?token=ORD524')
        self.assertEqual(r['Location'], '/donaciones/')
        self.assertFalse(Donation.objects.exists())
        self.assertTrue(AuditLog.objects.filter(action='donation_reject').exists())


class Parche524B_AudioOriginalPorRSS(TestCase):
    """B (orden de David): al pegar un enlace de Spotify se ofrece ademas el
    MP3 original del podcast (RSS), con el aviso de que una version con video
    analiza mejor; el MP3 elegido entra como plataforma 'audio' y se analiza
    (transcripcion + voces, sin fotogramas)."""

    HTML_SPOTIFY = ('<html><head><title>El episodio 12 - Mi Programa | Podcast on Spotify</title>'
                    '<meta property="og:title" content="El episodio 12"/></head></html>')
    FEED = ('<?xml version="1.0"?><rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"><channel>'
            '<item><title>El episodio 11</title><enclosure url="https://cdn.x/ep11.mp3" type="audio/mpeg"/></item>'
            '<item><title>El episodio 12</title><itunes:duration>1:02:03</itunes:duration>'
            '<enclosure url="https://cdn.x/ep12.mp3" type="audio/mpeg"/><pubDate>Mon, 01 Sep 2026</pubDate></item>'
            '</channel></rss>')

    def _requests(self):
        class R:
            def __init__(self, status, text=b'', data=None):
                self.status_code, self.content, self._data = status, text, data
                self.text = text.decode() if isinstance(text, bytes) else text
            def json(self):
                return self._data
            def iter_content(self, n):
                yield self.content
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def raise_for_status(self):
                pass
        def get(url, **kw):
            if 'open.spotify.com' in url:
                return R(200, self.HTML_SPOTIFY)
            if 'itunes.apple.com' in url:
                return R(200, b'{}', {'results': [{'feedUrl': 'https://feeds.x/mi-programa', 'collectionName': 'Mi Programa'}]})
            if 'feeds.x' in url:
                return R(200, self.FEED.encode())
            return R(404)
        return mock.patch('apps.embeds.rss.requests.get', side_effect=get)

    def test_detecta_el_mp3_como_plataforma_audio_y_lo_reproduce(self):
        from apps.embeds.adapters import build_embed, detect_platform
        p, vid = detect_platform('https://cdn.x/ep12.mp3?ts=1')
        self.assertEqual(p, 'audio')
        self.assertTrue(vid)
        self.assertEqual(detect_platform('https://cdn.x/pagina.html')[0], None)
        u = make_user()
        post = Post.objects.create(author=u, url='https://cdn.x/ep12.mp3', platform='audio',
                                   external_id=vid, title='Ep 12')
        self.assertIn('id="istt-audio"', build_embed(post))
        js = open('static/js/transcript.js', encoding='utf-8').read()
        self.assertIn("getElementById('istt-audio')", js)
        self.assertIn('audioEl.currentTime = t', js)

    def test_encuentra_el_audio_original_del_episodio(self):
        from apps.embeds.rss import alternativas_rss, segundos
        with self._requests():
            alts = alternativas_rss('https://open.spotify.com/episode/abc')
        self.assertEqual(len(alts), 1)
        self.assertEqual(alts[0]['url'], 'https://cdn.x/ep12.mp3', 'casa el episodio 12, no el 11')
        self.assertEqual(alts[0]['plataforma'], 'audio')
        self.assertEqual(alts[0]['duracion'], 3723)
        self.assertEqual(segundos('62:03'), 3723)

    def test_la_pantalla_de_alternativas_ofrece_el_rss_y_avisa_del_video(self):
        u = make_user(username='rss524', email='rss524@example.org')
        u.email_verified = True
        u.save()
        self.client.force_login(u)
        with self._requests(), mock.patch('apps.analysis.views._alternativas_web', return_value=[
                {'url': 'https://youtu.be/vid524', 'titulo': 'Version con video', 'plataforma': 'youtube'}]):
            html = self.client.post('/submit/', {'url': 'https://open.spotify.com/episode/abc',
                                                 'topic': 'politica'}).content.decode()
        self.assertIn('audio original (RSS)', html)
        self.assertIn('https://cdn.x/ep12.mp3', html)
        self.assertIn('https://youtu.be/vid524', html)
        self.assertIn('CON VÍDEO', html)
        self.assertIn('name="titulo"', html)
        self.assertFalse(Post.objects.filter(url__contains='spotify').exists())

    def test_elegir_el_mp3_crea_un_post_de_audio_con_titulo_y_duracion(self):
        u = make_user(username='mp3524', email='mp3524@example.org')
        u.email_verified = True
        u.save()
        self.client.force_login(u)
        with mock.patch('apps.embeds.adapters.probe', return_value={'ok': False, 'title': '',
                        'duration_seconds': 0, 'age_limit': 0, 'reason': 'x'}), \
             mock.patch('apps.analysis.views.run_cheap_phase') as rcp:
            self.client.post('/submit/', {'url': 'https://cdn.x/ep12.mp3', 'topic': 'politica',
                                          'titulo': 'El episodio 12', 'duracion': '300'})
        post = Post.objects.get(url='https://cdn.x/ep12.mp3')
        self.assertEqual(post.platform, 'audio')
        self.assertEqual(post.title, 'El episodio 12')
        self.assertEqual(post.duration_seconds, 300)   # 5 min: cabe en el dia (>media asignacion iria a la cola)
        rcp.delay.assert_called_once_with(post.pk)

    def test_la_descarga_directa_escribe_el_fichero_y_respeta_el_tope(self):
        import os
        import tempfile
        from apps.analysis.tasks import _descargar_audio_directo
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
            def iter_content(self, n):
                yield b'ID3' + b'\0' * 1000
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
        with tempfile.TemporaryDirectory() as td, \
             mock.patch('requests.get', return_value=R()):
            destino = _descargar_audio_directo('https://cdn.x/ep.mp3', os.path.join(td, 'audio.mp3'))
            self.assertEqual(os.path.getsize(destino), 1003)
            with self.assertRaises(RuntimeError):
                _descargar_audio_directo('https://cdn.x/ep.mp3', os.path.join(td, 'b.mp3'), tope_bytes=100)
        from apps.agents.vision import mirar
        u = make_user()
        post = Post.objects.create(author=u, url='https://cdn.x/ep.mp3', platform='audio')
        self.assertIsNone(mirar(post, 'frase', 3), 'sin video no hay fotogramas')
