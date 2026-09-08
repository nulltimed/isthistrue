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


class Parche523E_SubforosYAprobacion(TestCase):
    """E (ENMIENDA de David al README): categorias en arbol bajo Principal,
    categoria obligatoria, propuesta = post pendiente (sin analisis, invisible,
    solo staff en /pendiente/), aprobacion que publica y lanza, panel del arbol
    y foro agrupado por categoria."""

    def _autor(self):
        u = make_user(username='prop523', email='prop523@example.org')
        u.email_verified = True
        u.save()
        return u

    def _mod(self):
        return make_user(username='modE', email='mode@example.org', is_staff=True)

    def _proponer(self, autor, url='https://youtu.be/e523', etiqueta='Energía'):
        self.client.force_login(autor)
        with mock.patch('apps.embeds.adapters.probe',
                        return_value={'title': 'Molinos', 'duration_seconds': 60,
                                      'age_limit': 0}), \
             mock.patch('apps.analysis.views.run_cheap_phase'):
            self.client.post('/submit/', {'url': url, 'topic': '', 'topic_new': etiqueta})
        return Post.objects.get(url=url)

    def test_la_migracion_colgo_los_doce_temas_de_principal(self):
        from apps.analysis.models import Category
        raiz = Category.objects.get(slug='principal')
        self.assertEqual(Category.objects.get(slug='politica').parent, raiz)
        self.assertEqual(Category.objects.get(slug='politica').path_label(),
                         'Principal › Política')
        self.assertNotIn(raiz, Category.elegibles())

    def test_la_categoria_es_obligatoria(self):
        autor = self._autor()
        self.client.force_login(autor)
        with mock.patch('apps.embeds.adapters.probe',
                        return_value={'title': 'V', 'duration_seconds': 60, 'age_limit': 0}):
            r = self.client.post('/submit/', {'url': 'https://youtu.be/sin523', 'topic': ''})
        self.assertFalse(Post.objects.filter(url='https://youtu.be/sin523').exists())
        self.assertIn('Elige una categoría', r.content.decode())

    def test_la_propuesta_queda_pendiente_invisible_y_avisa_al_staff(self):
        from apps.accounts.models import Notification
        mod = self._mod()
        autor = self._autor()
        post = self._proponer(autor)
        self.assertEqual(post.status, 'PENDING_APPROVAL')
        self.assertTrue(Notification.objects.filter(user=mod, text__icontains='pendiente').exists())
        # invisible: portada, foro, buscador, y 404 para el autor
        for url in ('/', '/foro/', '/buscar/?q=Molinos'):
            self.assertNotIn(post.get_absolute_url(), self.client.get(url).content.decode(), url)
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get('/pendiente/').status_code, 302)
        # el staff lo ve listado y en su ficha de revision
        self.client.force_login(mod)
        self.assertIn('Molinos', self.client.get('/pendiente/').content.decode())
        html = self.client.get(f'/pendiente/{post.slug}/').content.decode()
        self.assertIn('Energía', html)
        self.assertIn('Aprobar y analizar', html)
        # el post page del staff redirige a la revision
        self.assertRedirects(self.client.get(post.get_absolute_url()),
                             f'/pendiente/{post.slug}/', fetch_redirect_response=False)

    def test_aprobar_crea_la_categoria_bajo_su_padre_y_lanza(self):
        from apps.analysis.models import Category
        from apps.accounts.models import Notification
        mod = self._mod()
        autor = self._autor()
        post = self._proponer(autor)
        self.client.force_login(mod)
        with mock.patch('apps.analysis.views.run_cheap_phase') as rcp:
            self.client.post(f'/pendiente/{post.slug}/', {
                'accion': 'aprobar', 'title': 'Molinos de viento', 'tags': 'eolica',
                'crear': 'on', 'nombre': 'Energía', 'parent': 'ciencia'})
        post.refresh_from_db()
        cat = Category.objects.get(slug='energia')
        self.assertEqual(cat.parent.slug, 'ciencia')
        self.assertEqual(post.topic, 'energia')
        self.assertEqual(post.status, 'NEW')
        self.assertEqual(post.title, 'Molinos de viento')
        self.assertEqual(post.approved_by, mod)
        rcp.delay.assert_called_once_with(post.pk)
        self.assertTrue(Notification.objects.filter(user=autor, text__icontains='aprobado').exists())
        # y ahora aparece en el foro, bajo su categoria
        html = self.client.get('/foro/').content.decode()
        self.assertIn('Principal › Ciencia › Energía', html)
        self.assertIn('Molinos de viento', html)
        # la pagina del subforo padre incluye a la hija
        html = self.client.get('/foro/c/ciencia/').content.decode()
        self.assertIn('Molinos de viento', html)
        self.assertIn('↳ Energía', html)

    def test_aprobar_encajando_en_una_existente_y_rechazar(self):
        from apps.analysis.models import Category
        mod = self._mod()
        autor = self._autor()
        p1 = self._proponer(autor, 'https://youtu.be/e523b', 'dinero')
        p2 = self._proponer(autor, 'https://youtu.be/e523c', 'basura')
        self.client.force_login(mod)
        with mock.patch('apps.analysis.views.run_cheap_phase'):
            self.client.post(f'/pendiente/{p1.slug}/', {'accion': 'aprobar', 'topic': 'economia'})
        p1.refresh_from_db()
        self.assertEqual(p1.topic, 'economia')
        self.assertFalse(Category.objects.filter(name='dinero').exists())
        self.client.post(f'/pendiente/{p2.slug}/', {'accion': 'rechazar', 'motivo': 'spam'})
        self.assertFalse(Post.objects.filter(pk=p2.pk).exists())

    def test_el_panel_cuida_el_arbol(self):
        from apps.analysis.models import Category
        mod = make_user(username='sup523', email='sup523@example.org',
                        is_staff=True, is_superuser=True)
        self.client.force_login(mod)
        self.client.post('/panel/categorias/', {'accion': 'crear', 'nombre': 'Elecciones', 'parent': 'politica'})
        cat = Category.objects.get(slug='elecciones')
        self.assertEqual(cat.parent.slug, 'politica')
        self.client.post('/panel/categorias/', {'accion': 'renombrar', 'pk': cat.pk, 'nombre': 'Comicios'})
        self.client.post('/panel/categorias/', {'accion': 'mover', 'pk': cat.pk, 'parent': 'sociedad'})
        cat.refresh_from_db()
        self.assertEqual((cat.name, cat.parent.slug), ('Comicios', 'sociedad'))
        html = self.client.get('/panel/categorias/').content.decode()
        self.assertIn('Comicios', html)
        self.client.post('/panel/categorias/', {'accion': 'borrar', 'pk': cat.pk})
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())
        # la raiz no se borra ni se cuelga de si misma
        raiz = Category.root()
        self.client.post('/panel/categorias/', {'accion': 'borrar', 'pk': raiz.pk})
        self.assertTrue(Category.objects.filter(slug='principal').exists())

    def test_la_tarea_no_analiza_un_pendiente(self):
        from apps.analysis.tasks import run_cheap_phase
        autor = self._autor()
        post = self._proponer(autor)
        self.assertEqual(run_cheap_phase(post.pk), 'skipped')


class Parche523FG_ViajeroYWikiDelVideo(TestCase):
    """F: modo viajero (boton junto a la campana y el ⋮, apagado por defecto,
    recordado en el navegador; hablantes y transcripcion fijos a los lados, el
    video sigue arriba). G: la wiki del video ES la vista del post sin
    comentarios, con acordeon por color y filtro por hablante."""

    def _escena(self):
        from apps.wiki.models import Claim, ClaimAppearance
        u = make_user(username='fg523', email='fg523@example.org')
        post = Post.objects.create(author=u, url='https://youtu.be/fg523',
                                   platform='youtube', status='DONE', title='Wiki unificada')
        for i, (col, txt) in enumerate([('RED', 'mentira uno'), ('GREEN', 'verdad uno'),
                                        ('UNDECIDED', 'duda uno')]):
            seg = post.transcript_segments.create(start_seconds=i * 20 + 3, end_seconds=i * 20 + 7,
                                                  text=txt, speaker_label='SPEAKER_00')
            c = Claim.objects.create(text_original=txt, color=col, slug=f'fg523-{i}')
            ClaimAppearance.objects.create(claim=c, segment=seg, quote=txt)
        return post

    def test_el_boton_viajero_existe_en_post_y_wiki_y_esta_apagado_por_defecto(self):
        post = self._escena()
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertIn('id="viajero-btn"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn('viajero.js', html)
        html = self.client.get(f'/wiki/video/{post.slug}/').content.decode()
        self.assertIn('id="viajero-btn"', html)
        js = open('static/js/viajero.js', encoding='utf-8').read()
        self.assertIn("localStorage.getItem(KEY) === '1'", js, 'apagado salvo que el navegador recuerde lo contrario')
        css = open('static/css/main.css', encoding='utf-8').read()
        self.assertIn('#viajero-izq{left:', css)
        self.assertIn('#viajero-der{right:', css)
        self.assertIn('body.viajero main.wide .post{padding-left:', css)

    def test_la_wiki_del_video_es_el_post_sin_comentarios_con_acordeon(self):
        post = self._escena()
        html = self.client.get(f'/wiki/video/{post.slug}/').content.decode()
        # misma rejilla que el post (hablantes | video | transcripcion)
        self.assertIn('transcript transcript-box', html)
        self.assertIn('speakers-col', html)
        self.assertIn('semaforo-post', html)
        # sin conversacion
        self.assertNotIn('id="hilo"', html)
        self.assertNotIn('thread-reply', html)
        # acordeon por color en el orden rojo, ambar, verde, sin respuesta
        self.assertLess(html.index('id="grupo-RED"'), html.index('id="grupo-AMBER"'))
        self.assertLess(html.index('id="grupo-AMBER"'), html.index('id="grupo-GREEN"'))
        self.assertLess(html.index('id="grupo-GREEN"'), html.index('id="grupo-SIN"'))
        self.assertIn('mentira uno', html)
        self.assertIn('duda uno', html)
        self.assertIn('seekTo(3)', html)         # la fila reproduce (seekTo resta 1)
        self.assertIn('wv-hablantes', html)      # chips por hablante
        self.assertIn('Hablante 1', html)
        self.assertIn('share-menu', html)
        # la rejilla es UNA plantilla para las dos paginas
        self.assertTrue(open('templates/partials/post_body.html', encoding='utf-8').read()
                        .count("include 'partials/media_grid.html'") == 1)
        self.assertNotIn('media-grid', open('templates/partials/post_body.html', encoding='utf-8').read().split('media_grid.html')[0])

    def test_ver_las_n_solo_cuando_hay_mas_de_ocho(self):
        from apps.wiki.models import Claim, ClaimAppearance
        post = self._escena()
        for i in range(10):
            seg = post.transcript_segments.create(start_seconds=100 + i, end_seconds=101 + i, text=f'v{i}')
            c = Claim.objects.create(text_original=f'verdad {i}', color='GREEN', slug=f'fgv-{i}')
            ClaimAppearance.objects.create(claim=c, segment=seg, quote='x')
        html = self.client.get(f'/wiki/video/{post.slug}/').content.decode()
        self.assertIn('Ver las 11', html)
        self.assertIn('oculta-por-tope', html)


class Parche523H_PanelDeLogs(TestCase):
    """H (orden de David): «un apartado Logs donde se podrán consultar, limpiar,
    copiar todos los tipos de logs sobre el sistema, potente y completo»."""

    def _sup(self):
        return make_user(username='logsup', email='logsup@example.org',
                         is_staff=True, is_superuser=True)

    def test_el_handler_guarda_lo_que_escribe_el_logger(self):
        import logging
        from apps.panel.models import SystemLog
        logging.getLogger('apps.agents.gpu').warning('GPU (prueba): trabajo j9 -> FAILED: CUDA OOM')
        fila = SystemLog.objects.filter(logger='apps.agents.gpu', message__icontains='CUDA OOM').first()
        self.assertIsNotNone(fila, 'el registro debe llegar a la BD')
        self.assertEqual(fila.level, 'WARNING')
        self.assertIn(fila.role, ('web', 'worker', 'beat', 'other'))
        # los loggers ruidosos de la BD no se guardan (bucle)
        logging.getLogger('django.db.backends').warning('ruido')
        self.assertFalse(SystemLog.objects.filter(message='ruido').exists())

    def test_el_panel_lista_filtra_copia_y_limpia(self):
        import logging
        from apps.panel.models import AuditLog, SystemLog
        self.client.force_login(self._sup())
        logging.getLogger('apps.analysis.tasks').info('Post 7: transcribir 12.0s')
        logging.getLogger('apps.agents.gpu').error('GPU (diarización): agotados los intentos')
        html = self.client.get('/panel/logs/').content.decode()
        self.assertIn('transcribir 12.0s', html)
        self.assertIn('agotados los intentos', html)
        self.assertIn('id="logs-texto"', html)          # lo que copia el boton
        self.assertIn('Copiar lo visible', html)
        self.assertIn('Limpiar los filtrados', html)
        html = self.client.get('/panel/logs/?tipo=errores').content.decode()
        self.assertIn('agotados los intentos', html)
        self.assertNotIn('transcribir 12.0s', html)
        html = self.client.get('/panel/logs/?tipo=gpu&q=diarizaci').content.decode()
        self.assertIn('agotados los intentos', html)
        # auditoria: aparte y visible
        AuditLog.objects.create(action='prueba_audit', detail='hecho por el test')
        html = self.client.get('/panel/logs/?tipo=auditoria').content.decode()
        self.assertIn('hecho por el test', html)
        # limpiar SOLO los filtrados y dejar rastro
        antes = SystemLog.objects.count()
        self.client.post('/panel/logs/', {'accion': 'limpiar', 'tipo': 'errores'})
        self.assertFalse(SystemLog.objects.filter(level='ERROR', message__icontains='agotados').exists())
        self.assertTrue(SystemLog.objects.filter(message__icontains='transcribir 12.0s').exists())
        self.assertTrue(AuditLog.objects.filter(action='logs_cleared').exists())
        # la auditoria jamas se limpia
        self.client.post('/panel/logs/', {'accion': 'limpiar', 'tipo': 'auditoria'})
        self.assertTrue(AuditLog.objects.filter(action='prueba_audit').exists())

    def test_solo_el_staff_entra(self):
        u = make_user(username='nolog', email='nolog@example.org')
        self.client.force_login(u)
        self.assertNotEqual(self.client.get('/panel/logs/').status_code, 200)

    def test_la_purga_respeta_la_retencion_del_panel(self):
        from django.utils import timezone
        from apps.panel.models import SystemLog, SystemSetting
        from apps.panel.tasks import purge_system_logs
        from config.celery import app
        SystemSetting.objects.update_or_create(key='logs_retention_days', defaults={'value': '7'})
        viejo = SystemLog.objects.create(level='INFO', logger='x', role='web', message='viejo')
        SystemLog.objects.filter(pk=viejo.pk).update(created_at=timezone.now() - timezone.timedelta(days=9))
        nuevo = SystemLog.objects.create(level='INFO', logger='x', role='web', message='nuevo')
        purge_system_logs()
        self.assertFalse(SystemLog.objects.filter(pk=viejo.pk).exists())
        self.assertTrue(SystemLog.objects.filter(pk=nuevo.pk).exists())
        self.assertEqual(app.conf.beat_schedule['purgar-logs-del-sistema']['task'],
                         'apps.panel.tasks.purge_system_logs')

    def test_los_contenedores_declaran_su_rol(self):
        for f in ('docker-compose.yml', 'docker-compose.staging.yml'):
            s = open(f, encoding='utf-8').read()
            for rol in ('web', 'worker', 'beat'):
                self.assertIn(f'ISTT_ROLE: {rol}', s, f'{f}: {rol}')
        from django.conf import settings as st
        self.assertFalse(st.CELERY_WORKER_HIJACK_ROOT_LOGGER)
        self.assertIn('db', st.LOGGING['root']['handlers'])
