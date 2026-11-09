"""Serie 6.24 (orden de David, 2026-11-09, 21:18, literal: «quiero que amplíes
antes la compatibilidad para el mayor número de medios/fuentes posibles: sin
límite»): nueve plataformas nuevas reconocidas con su reproductor — Vimeo,
Dailymotion, X/Twitter, Instagram, Facebook, Rumble, Odysee, SoundCloud e
iVoox. La descarga ya era yt-dlp genérico, así que TODAS se analizan; y
cualquier URL desconocida entra como tarjeta-enlace y el análisis SE INTENTA
igualmente (el aviso de la página lo dice en positivo).
"""
from django.test import SimpleTestCase

from apps.analysis.models import Post
from apps.embeds.adapters import NON_ANALYZABLE, build_embed, detect_platform


CASOS = {
    'https://vimeo.com/76979871': ('vimeo', '76979871'),
    'https://player.vimeo.com/video/76979871': ('vimeo', '76979871'),
    'https://www.dailymotion.com/video/x8abcd1': ('dailymotion', 'x8abcd1'),
    'https://x.com/ejemplo/status/1234567890123': ('x', '1234567890123'),
    'https://twitter.com/ejemplo/status/987654321': ('x', '987654321'),
    'https://www.instagram.com/reel/Cx1_ab-23/': ('instagram', 'Cx1_ab-23'),
    'https://www.facebook.com/watch/?v=123456789': ('facebook', '123456789'),
    'https://fb.watch/abc123/': ('facebook', 'abc123'),
    'https://rumble.com/v4abcd-titulo-del-video.html': ('rumble', 'v4abcd'),
    'https://odysee.com/@canal:7/video-titulo:a': ('odysee', '@canal:7/video-titulo:a'),
    'https://soundcloud.com/usuario/mi-episodio': ('soundcloud', 'usuario/mi-episodio'),
    'https://www.ivoox.com/programa-audios-mp3_rf_12345678_1.html': ('ivoox', '12345678'),
}


class CompatibilidadSinLimite(SimpleTestCase):
    def test_las_plataformas_nuevas_se_reconocen(self):
        for url, esperado in CASOS.items():
            self.assertEqual(detect_platform(url), esperado, url)

    def test_un_dominio_parecido_no_cuela(self):
        # maxflix.com contiene «x.com»; netflix no es dailymotion.
        self.assertEqual(detect_platform('https://maxflix.com/a/status/123'),
                         (None, None))
        self.assertEqual(detect_platform('https://www.netflix.com/watch/8123'),
                         (None, None))

    def test_cada_plataforma_nueva_tiene_reproductor(self):
        con_player = {'vimeo': 'player.vimeo.com', 'dailymotion': 'geo.dailymotion.com',
                      'x': 'twitter-tweet', 'instagram': 'instagram-media',
                      'facebook': 'plugins/video.php', 'odysee': '$/embed',
                      'soundcloud': 'w.soundcloud.com', 'ivoox': 'player_ej_'}
        for url, (plat, vid) in CASOS.items():
            post = Post(url=url, platform=plat, external_id=vid, title='t')
            html = build_embed(post)
            if plat in con_player:
                self.assertIn(con_player[plat], html, plat)
            else:   # rumble: tarjeta honesta — el análisis funciona igual
                self.assertIn('link-card', html, plat)

    def test_el_salto_al_segundo_donde_se_puede(self):
        v = Post(url='https://vimeo.com/76979871', platform='vimeo',
                 external_id='76979871')
        self.assertIn('#t=90s', build_embed(v, 90))
        d = Post(url='https://www.dailymotion.com/video/x8abcd1',
                 platform='dailymotion', external_id='x8abcd1')
        self.assertIn('startTime=90', build_embed(d, 90))

    def test_spotify_sigue_siendo_el_unico_no_analizable(self):
        self.assertEqual(NON_ANALYZABLE, ('spotify',))
