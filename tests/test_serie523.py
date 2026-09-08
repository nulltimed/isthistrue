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


class Parche523C_KarmaConFlechas(TestCase):
    """C (ENMIENDA de David al README): ▲/▼ en posts y comentarios; cada voto
    mueve el karma del autor; nadie vota lo suyo; difuminado y plegado por
    puntuacion negativa con umbrales del panel."""

    def _post_con_hilo(self):
        autor = make_user(username='autor523', email='autor523@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/k523',
                                   platform='youtube', title='Karma',
                                   author_opinion='Abro hilo')
        from apps.forum.machina_glue import create_topic_for_post, get_topic_for_post
        create_topic_for_post(post)
        m = get_topic_for_post(post).posts.first()
        return autor, post, m

    def test_el_voto_al_post_mueve_el_karma_y_alterna(self):
        autor, post, _m = self._post_con_hilo()
        votante = make_user(username='vot523', email='vot523@example.org')
        self.client.force_login(votante)
        self.client.post(f'/post/{post.pk}/votar/up/')
        autor.refresh_from_db()
        self.assertEqual(autor.karma, 1)
        self.client.post(f'/post/{post.pk}/votar/down/')     # cambia de signo
        autor.refresh_from_db()
        self.assertEqual(autor.karma, -1)
        self.client.post(f'/post/{post.pk}/votar/down/')     # repetir lo retira
        autor.refresh_from_db()
        self.assertEqual(autor.karma, 0)
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('voto-n-up', html)
        self.assertIn('voto-n-down', html)

    def test_nadie_vota_lo_suyo_ni_ve_sus_flechas(self):
        autor, post, m = self._post_con_hilo()
        self.client.force_login(autor)
        self.client.post(f'/post/{post.pk}/votar/up/')
        self.client.post(f'/mensaje/{m.pk}/votar/up/')
        autor.refresh_from_db()
        self.assertEqual(autor.karma, 0)
        from apps.forum.models import MessageVote, Vote
        self.assertFalse(Vote.objects.exists())
        self.assertFalse(MessageVote.objects.exists())
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('votos-propio', html)
        self.assertNotIn(f'/mensaje/{m.pk}/votar/up/', html)

    def test_el_comentario_se_difumina_y_se_pliega_con_los_umbrales_del_panel(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='karma_fade_threshold', defaults={'value': '1'})
        SystemSetting.objects.update_or_create(key='karma_fold_threshold', defaults={'value': '2'})
        autor, post, m = self._post_con_hilo()
        v1 = make_user(username='v1k', email='v1k@example.org')
        v2 = make_user(username='v2k', email='v2k@example.org')
        self.client.force_login(v1)
        self.client.post(f'/mensaje/{m.pk}/votar/down/')
        html = self.client.get(post.get_absolute_url() + '?pagina=1').content.decode()
        self.assertIn('msg-faded', html)
        self.assertNotIn('msg-folded', html)
        self.client.force_login(v2)
        self.client.post(f'/mensaje/{m.pk}/votar/down/')
        html = self.client.get(post.get_absolute_url() + '?pagina=1').content.decode()
        self.assertIn('msg-folded', html)
        self.assertIn('Comentario plegado', html)
        autor.refresh_from_db()
        self.assertEqual(autor.karma, -2)

    def test_trending_y_mas_votados_cuentan_solo_positivos(self):
        from apps.forum.models import Vote
        autor, post, _m = self._post_con_hilo()
        for i in range(5):
            u = make_user(username=f'neg{i}', email=f'neg{i}@example.org')
            Vote.objects.create(post=post, user=u, value=-1)
        self.assertEqual(post.trending_votes(), 0)
        self.assertFalse(post.is_trending())

    def test_los_umbrales_estan_en_el_panel(self):
        from apps.panel.views import SETTINGS_DEF
        claves = {k for k, *_ in SETTINGS_DEF}
        self.assertIn('karma_fade_threshold', claves)
        self.assertIn('karma_fold_threshold', claves)
        po = open('README.md', encoding='utf-8').read()
        self.assertIn('ENMENDADO 2026-09-08', po)


class Parche523D_MenuTresPuntos(TestCase):
    """D (orden de David): el menu ⋮ en post y comentarios; censura =
    inaccesible para todos, sin analisis y reversible; acciones clasicas de
    foro con bocadillos."""

    def _mod(self):
        return make_user(username='mod523', email='mod523@example.org', is_staff=True)

    def _post(self):
        autor = make_user(username='aut523d', email='aut523d@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/d523',
                                   platform='youtube', title='Menu', topic='politica',
                                   author_opinion='hola')
        from apps.forum.machina_glue import create_topic_for_post, get_topic_for_post
        create_topic_for_post(post)
        return autor, post, get_topic_for_post(post).posts.first()

    def test_todos_ven_copiar_y_reportar_y_solo_el_staff_lo_demas(self):
        _a, post, _m = self._post()
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('class="kebab', html)
        self.assertIn('copiar-enlace', html)
        self.assertIn('Reportar', html)
        self.assertNotIn('Cerrar comentarios', html)
        self.client.force_login(self._mod())
        html = self.client.get(post.get_absolute_url()).content.decode()
        for opcion in ('Cerrar comentarios', 'Fijar arriba', 'Contenido sensible',
                       'Mover de categoría', 'Editar título', 'Censurar',
                       'Notas de moderación', 'Eliminar post'):
            self.assertIn(opcion, html, opcion)
        self.assertIn('data-tip=', html)
        # Reportar llega al formulario DSA con la URL rellena
        r = self.client.get('/reclamaciones/?url=https://x/post/1/')
        self.assertIn('value="https://x/post/1/"', r.content.decode())

    def test_cerrar_comentarios_fijar_sensible_titulo_y_mover(self):
        from apps.analysis.models import Category
        _a, post, _m = self._post()
        mod = self._mod()
        otro = make_user(username='otro523', email='otro523@example.org', email_verified=True)
        self.client.force_login(mod)
        self.client.post(f'/post/{post.pk}/comentarios/')
        post.refresh_from_db()
        self.assertTrue(post.comments_closed)
        self.client.force_login(otro)
        self.client.post(f'/post/{post.pk}/reply/', {'content': 'no deberia entrar'})
        from apps.forum.machina_glue import get_topic_for_post
        self.assertEqual(get_topic_for_post(post).posts.count(), 1, 'cerrado = sin respuestas')
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('Comentarios cerrados', html)
        self.client.force_login(mod)
        self.client.post(f'/post/{post.pk}/fijar/')
        self.client.post(f'/post/{post.pk}/sensible/')
        self.client.post(f'/post/{post.pk}/titulo/', {'title': 'Titulo corregido'})
        Category.objects.get_or_create(slug='ciencia', defaults={'name': 'Ciencia'})
        self.client.post(f'/post/{post.pk}/mover/', {'topic': 'ciencia'})
        post.refresh_from_db()
        self.assertTrue(post.pinned)
        self.assertTrue(post.is_adult)
        self.assertEqual(post.adult_flag_source, 'mod')
        self.assertEqual(post.title, 'Titulo corregido')
        self.assertEqual(post.topic, 'ciencia')
        self.assertEqual(get_topic_for_post(post).subject, 'Titulo corregido')
        from apps.panel.models import AuditLog
        self.assertGreaterEqual(AuditLog.objects.filter(user=mod).count(), 5)

    def test_censurado_es_inaccesible_sin_analisis_y_reversible(self):
        _a, post, _m = self._post()
        mod = self._mod()
        self.client.force_login(mod)
        self.client.post(f'/post/{post.pk}/censurar/', {'reason': 'insultos'})
        post.refresh_from_db()
        self.assertTrue(post.censored)
        # el staff lo ve marcado
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('Este post está censurado', html)
        # el publico: fuera
        self.client.logout()
        r = self.client.get(post.get_absolute_url())
        self.assertEqual(r.status_code, 403)
        self.assertIn('Post censurado por moderación', r.content.decode())
        self.assertNotIn('Ver de todos modos', r.content.decode())
        for url in ('/', '/foro/', '/buscar/?q=Menu'):
            self.assertNotIn('Menu</a>', self.client.get(url).content.decode(), url)
        # sin analisis
        from apps.analysis.tasks import run_cheap_phase
        self.assertEqual(run_cheap_phase(post.pk), 'skipped')
        # reversible
        self.client.force_login(mod)
        self.client.post(f'/post/{post.pk}/censurar/')
        post.refresh_from_db()
        self.assertFalse(post.censored)
        self.client.logout()
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 200)

    def test_eliminar_comentario_es_reversible_y_solo_lo_ve_el_staff(self):
        _a, post, m = self._post()
        mod = self._mod()
        self.client.force_login(mod)
        self.client.post(f'/mensaje/{m.pk}/eliminar/')
        m.refresh_from_db()
        self.assertFalse(m.approved)
        html = self.client.get(post.get_absolute_url() + '?pagina=1').content.decode()
        self.assertIn('Comentario eliminado por moderación', html)
        self.assertIn('Restaurar', html)
        self.client.logout()
        html = self.client.get(post.get_absolute_url() + '?pagina=1').content.decode()
        self.assertNotIn('Comentario eliminado', html)
        self.assertNotIn(f'id="msg-{m.pk}"', html)
        self.client.force_login(mod)
        self.client.post(f'/mensaje/{m.pk}/eliminar/')
        m.refresh_from_db()
        self.assertTrue(m.approved)

    def test_un_usuario_normal_no_puede_usar_el_menu_de_staff(self):
        _a, post, m = self._post()
        u = make_user(username='nor523', email='nor523@example.org')
        self.client.force_login(u)
        for url in (f'/post/{post.pk}/comentarios/', f'/post/{post.pk}/fijar/',
                    f'/post/{post.pk}/sensible/', f'/post/{post.pk}/titulo/',
                    f'/post/{post.pk}/mover/', f'/mensaje/{m.pk}/eliminar/'):
            self.client.post(url, {'title': 'x', 'topic': 'ciencia'})
        post.refresh_from_db(); m.refresh_from_db()
        self.assertFalse(post.comments_closed or post.pinned or post.is_adult)
        self.assertEqual(post.title, 'Menu')
        self.assertTrue(m.approved)
