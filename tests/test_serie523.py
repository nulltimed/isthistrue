"""Serie 5.23 (ordenes de David, 2026-09-08): RunPod con reintento y contador,
transcripcion con scroll real, semaforo centrado, compartir agrupado, karma
con flechas, menu de tres puntos con bocadillos, subforos en arbol con
aprobacion, modo viajero, wiki del video unificada y panel de logs."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u523', email='u523@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class _Resp:
    def __init__(self, data, status_code=200):
        self._data, self.status_code = data, status_code

    def json(self):
        return self._data


class Parche523A_RunpodReintentoYContador(TestCase):
    """A: un trabajo FAILED se reintenta UNA vez en la GPU antes de caer a CPU;
    el motivo de Runpod va al log y el fallo deja su apunte a cero."""

    def test_reintenta_una_vez_y_apunta_el_fallo(self):
        from apps.agents import gpu
        from apps.analysis.models import CostEntry
        from apps.analysis.costs import gpu_jobs_month
        estados = iter([
            _Resp({'status': 'FAILED', 'error': 'CUDA out of memory'}),
            _Resp({'status': 'COMPLETED', 'executionTime': 5000,
                   'output': {'turns': [[0, 1, 'SPEAKER_00']]}}),
        ])
        with mock.patch.object(gpu.httpx, 'post', return_value=_Resp({'id': 'j1'})), \
             mock.patch.object(gpu.httpx, 'get', side_effect=lambda *a, **k: next(estados)), \
             mock.patch.object(gpu.time, 'sleep'), \
             mock.patch.object(gpu.settings, 'RUNPOD_API_KEY', 'k', create=True), \
             self.assertLogs('apps.agents.gpu', level='WARNING') as logs:
            out = gpu._run_job('ep', {'x': 1}, 'diarización')
        self.assertEqual(out, {'turns': [[0, 1, 'SPEAKER_00']]})
        self.assertTrue(any('CUDA out of memory' in l for l in logs.output),
                        'el motivo de Runpod ya no se tira')
        self.assertEqual(CostEntry.objects.filter(
            provider='runpod', concept__endswith=' — fallo').count(), 1)
        ok, fallos = gpu_jobs_month()
        self.assertEqual((ok, fallos), (1, 1))

    def test_dos_fallos_seguidos_caen_a_cpu(self):
        from apps.agents import gpu
        with mock.patch.object(gpu.httpx, 'post', return_value=_Resp({'id': 'j2'})), \
             mock.patch.object(gpu.httpx, 'get',
                               return_value=_Resp({'status': 'TIMED_OUT'})), \
             mock.patch.object(gpu.time, 'sleep'), \
             mock.patch.object(gpu.settings, 'RUNPOD_API_KEY', 'k', create=True):
            self.assertIsNone(gpu._run_job('ep', {}, 'diarización'))
        from apps.analysis.models import CostEntry
        self.assertEqual(CostEntry.objects.filter(
            concept__endswith=' — fallo').count(), 2)

    def test_la_pagina_de_gastos_enseña_el_contador(self):
        from apps.analysis import costs
        costs.record('runpod', 'diarización', 0.01)
        costs.record_failure('runpod', 'diarización', 'x')
        html = self.client.get('/gastos/').content.decode()
        self.assertIn('gpu-contador', html)
        self.assertIn('trabajos completados', html)

    def test_el_dockerfile_slim_no_graba_el_token(self):
        """Leccion del 2026-09-08: el ARG quedaba en el historial de la imagen
        publica. Solo secretos de BuildKit."""
        src = open('workers/gpu/diarize/Dockerfile.slim', encoding='utf-8').read()
        self.assertNotIn('ARG HF_TOKEN', src)
        self.assertIn('--mount=type=secret,id=hf_token', src)


class Parche523B_TranscripcionCabeceraCompartir(TestCase):
    """B: la caja de transcripcion es desplazable DENTRO del post (el karaoke
    tenia sobre que scrollear), titulo y globos centrados con su leyenda, y
    compartir agrupado en un icono."""

    def test_la_caja_de_transcripcion_tiene_scroll_propio(self):
        css = open('static/css/main.css', encoding='utf-8').read()
        regla = css.split('/* B.1:')[1]
        self.assertIn('.transcript-col .transcript-box{max-height:calc(100vh', regla)
        self.assertIn('overflow-y:auto', regla.split('.transcript-col .transcript-box{')[1][:120])
        # el JS sigue scrolleando la CAJA, jamas la pagina (orden 5.10-C)
        js = open('static/js/transcript.js', encoding='utf-8').read()
        self.assertIn('box.scrollTo', js)
        self.assertNotIn('window.scrollTo', js)

    def test_globos_con_leyenda_y_centrados(self):
        from apps.wiki.models import Claim, ClaimAppearance
        u = make_user()
        post = Post.objects.create(author=u, url='https://youtu.be/b523',
                                   platform='youtube', status='DONE', title='B')
        seg = post.transcript_segments.create(start_seconds=5, end_seconds=9, text='x')
        c = Claim.objects.create(text_original='x', color='RED', slug='b523')
        ClaimAppearance.objects.create(claim=c, segment=seg, quote='x')
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('Verificado', html)
        self.assertIn('Falso', html)
        self.assertIn('Sin respuesta', html)
        css = open('static/css/main.css', encoding='utf-8').read()
        self.assertIn('main.wide .post > h1{text-align:center}', css)
        self.assertIn('.semaforo-post{justify-content:center', css)

    def test_compartir_agrupado_en_post_y_claim(self):
        from apps.wiki.models import Claim
        u = make_user()
        post = Post.objects.create(author=u, url='https://youtu.be/b523s', title='S')
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertEqual(html.count('share-menu'), 1)
        for red in ('reddit.com', 'twitter.com', 'wa.me', 't.me', 'facebook.com', 'bsky.app'):
            self.assertIn(red, html)
        self.assertIn('copiar-enlace', html)
        self.assertNotIn('class="share">', html, 'la fila vieja de enlaces sueltos se fue')
        c = Claim.objects.create(text_original='c', color='GREEN', slug='c523')
        html = self.client.get('/wiki/claim/c523/').content.decode()
        self.assertIn('share-menu', html)
        self.assertIn('menus.js', html)
