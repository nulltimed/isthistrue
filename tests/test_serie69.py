"""Serie 6.9 (orden de David, 2026-11-09, 04:46, literal: «Elimina las
donaciones de cualquier página. Es ahora una SL. Ya hemos establecido el
modelo de negocio»): purga del LENGUAJE de donación de todas las páginas.

La 6.1 retiró el producto; esta serie caza las reliquias de texto (insignia
«Apadrinable», «donados este mes», bocadillos de donar, cookies con el botón
de PayPal, página muerta /donaciones/). El modelo Donation sigue como libro
interno (puente CREDIT del 4.3-F y legado IPN) — eso no es una página.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


class SinDonacionesEnNingunaPagina(TestCase):
    def test_las_paginas_publicas_no_hablan_de_donar(self):
        u = User.objects.create_user(username='u69', email='u69@example.org',
                                     password='x')
        # Un post en cola, para que la insignia nueva se pinte en / y /foro/.
        Post.objects.create(author=u, url='https://youtu.be/s69', title='Cola',
                            status='AWAITING_BUDGET')
        for ruta in ('/', '/foro/', '/gastos/', '/creditos/',
                     '/legal/cookies/', '/transparencia/', '/quienes-somos/'):
            html = self.client.get(ruta, follow=True).content.decode()
            for palabra in ('donaci', 'Donaci', 'Donar', 'Apadrinable',
                            'apadrinarlo', 'apadrinamiento'):
                self.assertNotIn(palabra, html, f'{palabra!r} en {ruta}')

    def test_la_insignia_de_la_cola_habla_de_creditos(self):
        u = User.objects.create_user(username='u69b', email='u69b@example.org',
                                     password='x')
        Post.objects.create(author=u, url='https://youtu.be/s69b', title='Cola2',
                            status='AWAITING_BUDGET')
        html = self.client.get('/').content.decode()
        self.assertIn('Adelantable con créditos', html)

    def test_la_pagina_de_donaciones_sigue_redirigiendo_a_creditos(self):
        r = self.client.get('/donaciones/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/creditos/', r['Location'])
