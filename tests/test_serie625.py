"""Serie 6.25 (orden de David, 2026-11-09): /medios/ — la pagina publica
«¿Qué puedo postear?», bilingue (patron de las legales), enlazada en el pie.
Candado estructural: TODA plataforma de PATTERNS debe aparecer en la pagina
(ampliar la compatibilidad sin documentarla pone el CI rojo), y el aviso de
plataforma desconocida cuenta la verdad: el analisis se intenta igualmente.
"""
from django.test import TestCase

from apps.embeds.adapters import PATTERNS

NOMBRES_EN_PAGINA = {
    'youtube': 'YouTube', 'tiktok': 'TikTok', 'spotify': 'Spotify',
    'twitch': 'Twitch', 'vimeo': 'Vimeo', 'dailymotion': 'Dailymotion',
    'x': 'X (Twitter)', 'instagram': 'Instagram', 'facebook': 'Facebook',
    'rumble': 'Rumble', 'odysee': 'Odysee', 'soundcloud': 'SoundCloud',
    'ivoox': 'iVoox',
}


class PaginaQuePuedoPostear(TestCase):
    def test_carga_y_documenta_toda_plataforma_soportada(self):
        html = self.client.get('/medios/').content.decode()
        for plat in PATTERNS:
            self.assertIn(plat, NOMBRES_EN_PAGINA,
                          f'plataforma nueva «{plat}» sin nombre de pagina: '
                          f'añadela a /medios/ y a este mapa')
            self.assertIn(NOMBRES_EN_PAGINA[plat], html,
                          f'«{plat}» no aparece en /medios/')
        self.assertIn('Audio directo', html)   # la via RSS tambien se documenta

    def test_esta_en_el_pie(self):
        html = self.client.get('/medios/').content.decode()
        self.assertIn('/medios/', html)
        self.assertIn('Qué puedo postear', html)

    def test_el_aviso_de_plataforma_desconocida_cuenta_la_verdad(self):
        import inspect
        from apps.analysis import views
        src = inspect.getsource(views)
        self.assertIn('se intentará igualmente', src)
        self.assertNotIn('Plataforma no soportada todavía', src)
