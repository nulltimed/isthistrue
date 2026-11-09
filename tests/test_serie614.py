"""Serie 6.14 (orden de David, 2026-11-09, 07:09, literal: «No, aplícalo
ahora» — a su pregunta de las 07:07: «¿se puede hacer que la página concreta
sea en modo "live"? Es decir, que cualquier cambio en la transcripción,
los intervinientes, etc, se muestren automáticamente en la página sin tener
que recargarla»).

VIGÍA v2 — modo vivo: cuando cambia la huella del análisis, vigia_post.js ya
no recarga la página — trae /post/<pk>/fragmento/cuerpo/ y lo intercambia en
#post-body con htmx; los scripts del cuerpo (transcripción, autocompletado de
hablantes) se re-enganchan con el evento `istt:post-swap`. Los mensajes
nuevos siguen recargando (el hilo con scroll infinito no se re-pinta, 5.7-B).

Candados de este test:
- la página del post lleva la diana (#post-body) y el data-frag del vigía;
- el fragmento del cuerpo responde 200;
- vigia_post.js hace el intercambio htmx y emite `istt:post-swap`;
- transcript.js y speaker-suggest.js se re-enganchan a ese evento, y
  transcript.js no APILA relojes (clearInterval del anterior) ni carga dos
  veces la IFrame API de YouTube (guard por id del <script>).
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()
RAIZ = Path(__file__).resolve().parent.parent


def _js(nombre):
    return (RAIZ / 'static' / 'js' / nombre).read_text(encoding='utf-8')


class VigiaV2ModoVivo(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(username='u614', email='u614@example.org',
                                          password='x')
        self.post = Post.objects.create(author=self.u, url='https://youtu.be/s614',
                                        title='Vivo', platform='youtube',
                                        status='DONE')

    def test_la_pagina_del_post_lleva_la_diana_y_el_fragmento(self):
        html = self.client.get(f'/post/{self.post.pk}/', follow=True).content.decode()
        self.assertIn('id="post-body"', html)
        self.assertIn('data-frag=', html)
        self.assertIn(f'/post/{self.post.pk}/fragmento/cuerpo/', html)

    def test_el_fragmento_del_cuerpo_responde(self):
        r = self.client.get(f'/post/{self.post.pk}/fragmento/cuerpo/')
        self.assertEqual(r.status_code, 200)

    def test_el_vigia_intercambia_en_vivo_y_avisa_a_los_scripts(self):
        js = _js('vigia_post.js')
        self.assertIn('htmx.ajax', js)
        self.assertIn('#post-body', js)
        self.assertIn('istt:post-swap', js)
        # y conserva la salida de emergencia: sin htmx, recarga como el 5.7
        self.assertIn('location.reload', js)

    def test_los_scripts_del_cuerpo_se_reenganchan(self):
        for nombre in ('transcript.js', 'speaker-suggest.js'):
            self.assertIn("addEventListener('istt:post-swap'", _js(nombre),
                          f'{nombre} no se re-engancha tras el intercambio')

    def test_transcript_no_apila_relojes_ni_duplica_la_api(self):
        js = _js('transcript.js')
        # un re-init sin limpiar el interval anterior apila relojes de karaoke
        self.assertIn('clearInterval(window.__isttTransVivo)', js)
        # y sin el guard, cada intercambio añadiría otro <script> de la API
        self.assertIn("getElementById('istt-yt-api')", js)
