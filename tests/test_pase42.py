"""Pase 4.2: relegacion SOLO manual, busquedas ruidosas con sources_ok,
logo por dominio y Opina como primer mensaje del hilo."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.analysis.models import Post
from apps.analysis.tasks import relegate_expired_validations
from config.context_processors import logo_variant

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u1', email='u1@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class RelegacionSoloManual(TestCase):
    """A2: ni el clasificador ni el beat mueven nada a Off-Topic."""

    def test_expirados_se_marcan_pero_no_se_relegan(self):
        post = Post.objects.create(author=make_user(), url='https://youtu.be/abc123x',
                                   status='PENDING_VALIDATION',
                                   validation_deadline=timezone.now() - timedelta(hours=1))
        n = relegate_expired_validations()
        post.refresh_from_db()
        self.assertEqual(n, 1)
        self.assertEqual(post.category, 'MAIN')            # NO se movio
        self.assertEqual(post.status, 'VALIDATION_EXPIRED')
        self.assertTrue(post.offtopic_suggested)           # solo sugiere

    def test_relegar_exige_moderador(self):
        author = make_user()
        post = Post.objects.create(author=author, url='https://youtu.be/abc124x')
        self.client.force_login(author)                    # nivel NEW: no puede
        self.client.post(f'/post/{post.pk}/relegate/')
        post.refresh_from_db()
        self.assertEqual(post.category, 'MAIN')
        mod = make_user(username='mod', email='mod@example.org', level='MOD')
        self.client.force_login(mod)
        self.client.post(f'/post/{post.pk}/relegate/', {'reason': 'es opinión'})
        post.refresh_from_db()
        self.assertEqual(post.category, 'OFFTOPIC')
        self.assertEqual(post.relegation_reason, 'es opinión')


class BusquedaRuidosa(TestCase):
    """C1: un fallo de SearXNG JAMAS es mudo y viaja como sources_ok=False.
    (MOCK off SOLO en el test del 403: con el override a nivel de clase,
    upsert_claim intentaba el pivote EN contra la API real — CI rojo.)"""

    @override_settings(MOCK_AGENTS=False)
    def test_403_devuelve_ok_false_y_avisa(self):
        from apps.agents import search
        fake = mock.Mock(status_code=403)
        with mock.patch.object(search.httpx, 'get', return_value=fake):
            with self.assertLogs('agents.search', level='WARNING') as logs:
                results, ok = search.search_with_status('presos políticos')
        self.assertEqual(results, [])
        self.assertFalse(ok)
        self.assertIn('403', logs.output[0])

    def test_upsert_claim_guarda_sources_ok(self):
        from apps.wiki.services import upsert_claim
        from apps.wiki.models import Claim
        post = Post.objects.create(author=make_user(), url='https://youtu.be/abc125x')
        post.transcript_segments.create(start_seconds=0, end_seconds=5,
                                        text='España tiene 48 millones de habitantes',
                                        signal='FACTUAL_UNVERIFIED')
        upsert_claim(post, {'text': 'España tiene 48 millones de habitantes',
                            'segment_index': 0},
                     {'color': 'GREEN', 'sources': []}, sources_ok=False)
        self.assertFalse(Claim.objects.get().sources_ok)


class LogoPorDominio(TestCase):
    """C6: el logo sigue al host; el idioma no pinta nada aqui."""

    def test_variantes(self):
        rf = RequestFactory()
        for host, expected in [('escierto.xyztserver.com', 'escierto'),
                               ('isthistrue.xyztserver.com', 'isthistrue'),
                               ('wikitrue.xyztserver.com', 'isthistrue')]:
            req = rf.get('/', HTTP_HOST=host)
            self.assertEqual(logo_variant(req)['logo_variant'], expected, host)


class OpinaAbreElHilo(TestCase):
    """A5: el texto de la caja Opina es el PRIMER mensaje del hilo machina."""

    def test_primer_mensaje(self):
        from apps.forum.machina_glue import create_topic_for_post, get_topic_for_post
        post = Post.objects.create(author=make_user(), url='https://youtu.be/abc126x',
                                   author_opinion='Me parece **muy exagerado**.')
        create_topic_for_post(post)
        topic = get_topic_for_post(post)
        first = topic.posts.order_by('created').first()
        self.assertIn('muy exagerado', str(first.content))


class FrasesCompletas(TestCase):
    """D1: la unidad de transcripcion/analisis es la FRASE completa por hablante."""

    def test_agrupa_hasta_el_punto_y_corta_al_cambiar_de_hablante(self):
        from apps.analysis.tasks import merge_into_sentences
        raw = [
            {'start_seconds': 0.0, 'end_seconds': 2.0, 'text': 'España tiene'},
            {'start_seconds': 2.0, 'end_seconds': 4.0, 'text': '48 millones de habitantes.'},
            {'start_seconds': 4.0, 'end_seconds': 6.0, 'text': 'Y eso es mucho.'},
            {'start_seconds': 6.0, 'end_seconds': 8.0, 'text': 'No estoy de acuerdo.'},
        ]
        turns = [(0.0, 6.0, 'SPEAKER_00'), (6.0, 8.0, 'SPEAKER_01')]
        merged = merge_into_sentences(raw, turns)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]['text'], 'España tiene 48 millones de habitantes.')
        self.assertEqual(merged[0]['start_seconds'], 0.0)   # timestamp = inicio de la frase
        self.assertEqual(merged[0]['speaker_label'], 'SPEAKER_00')
        self.assertEqual(merged[2]['speaker_label'], 'SPEAKER_01')


class SuscripcionYTrending(TestCase):
    """D3 + D4: campanita del post y umbral vivo de Trending."""

    def test_suscribirse_y_darse_de_baja(self):
        from apps.analysis.models import PostSubscription
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc127x')
        self.client.force_login(user)
        self.client.post(f'/post/{post.pk}/subscribe/', {'on_messages': 'on'})
        sub = PostSubscription.objects.get(post=post, user=user)
        self.assertTrue(sub.on_messages); self.assertFalse(sub.on_analysis)
        self.client.post(f'/post/{post.pk}/subscribe/', {})  # sin casillas = baja
        self.assertFalse(PostSubscription.objects.filter(post=post, user=user).exists())

    def test_trending_umbral_y_aviso_unico(self):
        from apps.forum.models import Vote
        from apps.accounts.models import Notification
        author = make_user()
        post = Post.objects.create(author=author, url='https://youtu.be/abc128x')
        voters = [make_user(username=f'v{i}', email=f'v{i}@example.org') for i in range(5)]
        for v in voters[:4]:
            Vote.objects.create(post=post, user=v)
        self.assertFalse(post.is_trending())               # 4 < umbral (5)
        self.client.force_login(voters[4])
        self.client.post(f'/post/{post.pk}/upvote/')       # el 5o cruza el umbral
        post.refresh_from_db()
        self.assertTrue(post.is_trending())
        self.assertTrue(post.trending_notified)
        self.assertTrue(Notification.objects.filter(user=author,
                        text__icontains='Trending').exists())


class CampanaViva(TestCase):
    """D2: sondeo de la campana para el numerito y el navegador."""

    def test_poll_devuelve_no_leidas(self):
        from apps.accounts.services import notify
        user = make_user()
        notify(user, 'Veredictos publicados: prueba', '/post/1/')
        self.client.force_login(user)
        data = self.client.get('/accounts/notifications/poll/?after=0').json()
        self.assertEqual(data['unread'], 1)
        self.assertIn('Veredictos', data['items'][0]['text'])


class TituloEnVezDeEnlace(TestCase):
    """F1: el titulo del video sustituye al enlace en bruto en pagina, foro y avisos."""

    @override_settings(MOCK_AGENTS=True)
    def test_mock_rellena_titulo(self):
        from apps.analysis.tasks import _transcribe_first_tranche
        post = Post.objects.create(author=make_user(), url='https://youtu.be/abc129x')
        _transcribe_first_tranche(post, '/tmp')
        post.refresh_from_db()
        self.assertTrue(post.title.strip())

    def test_notificacion_lleva_el_titulo(self):
        from apps.analysis.tasks import notify_post_event
        from apps.accounts.models import Notification
        author = make_user()
        post = Post.objects.create(author=author, url='https://youtu.be/abc130x',
                                   title='Debate electoral completo')
        notify_post_event(post, 'analysis', 'Veredictos publicados')
        note = Notification.objects.get(user=author)
        self.assertIn('Debate electoral completo', note.text)
        self.assertNotIn('youtu.be', note.text)


class BuscadorAdaptado(TestCase):
    """G1: el buscador conoce titulos reales y mensajes del hilo."""

    def test_encuentra_por_titulo_y_por_mensaje(self):
        from apps.forum.machina_glue import create_topic_for_post, add_reply
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc129x',
                                   title='Debate sobre la sanidad pública')
        create_topic_for_post(post)
        add_reply(post, user, 'Las listas de espera son el problema')
        r = self.client.get('/buscar/', {'q': 'sanidad', 'scope': 'posts'})
        self.assertContains(r, 'Debate sobre la sanidad')
        r = self.client.get('/buscar/', {'q': 'listas de espera', 'scope': 'forum'})
        self.assertContains(r, 'listas de espera')


class BloqueH(TestCase):
    """H1/H5/H8: sensibilidad por reportes, Opus por oracion y MP con buzon."""

    def test_umbral_de_reportes_difumina(self):
        from apps.forum.models import MessageSensitive
        users = [make_user(username=f'r{i}', email=f'r{i}@example.org') for i in range(5)]
        for u in users:
            self.client.force_login(u)
            self.client.post('/mensaje/777/reportar/')
        self.assertTrue(MessageSensitive.objects.filter(machina_post_id=777,
                                                        auto=True).exists())

    def test_downvotes_disparan_opus_por_oracion(self):
        from apps.analysis import tasks
        author = make_user()
        post = Post.objects.create(author=author, url='https://youtu.be/abc130x',
                                   status='DONE')
        seg = post.transcript_segments.create(start_seconds=0, end_seconds=5,
                                              text='La luna es de queso.',
                                              signal='FACTUAL_UNVERIFIED')
        voters = [make_user(username=f'd{i}', email=f'd{i}@example.org') for i in range(6)]
        with mock.patch.object(tasks.opus_rescan_segment, 'delay') as delay:
            for v in voters:
                self.client.force_login(v)
                self.client.post(f'/oracion/{seg.pk}/votar/down/')
        delay.assert_called_once_with(seg.pk)  # el 6o ▼ supera el umbral (5), UNA vez... 
        # (el 6o llama; el candado opus_rescanned de la tarea evita repeticiones reales)

    def test_mp_respeta_buzon_y_mods_pasan(self):
        from apps.accounts.models import PrivateMessage
        emisor = make_user(username='e1', email='e1@example.org')
        cerrado = make_user(username='c1', email='c1@example.org')  # buzon OFF por defecto
        self.client.force_login(emisor)
        self.client.post(f'/accounts/mensajes/enviar/{cerrado.pk}/', {'body': 'hola'})
        self.assertEqual(PrivateMessage.objects.count(), 0)
        mod = make_user(username='m1', email='m1@example.org', level='MOD')
        self.client.force_login(mod)
        self.client.post(f'/accounts/mensajes/enviar/{cerrado.pk}/', {'body': 'aviso de moderación'})
        self.assertEqual(PrivateMessage.objects.filter(recipient=cerrado).count(), 1)


class Pase421(TestCase):
    """4.2.1: parser de subtítulos, título inmediato y propuesta de hablante."""

    def test_parse_vtt(self):
        from apps.analysis.tasks import _parse_vtt
        cues = _parse_vtt("WEBVTT\n\n00:00:01.000 --> 00:00:04.000\n<c>Buenas</c> noches\n"
                          "\n00:00:04.000 --> 00:00:07.500\ny bienvenidos al debate.\n")
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]['text'], 'Buenas noches')
        self.assertEqual(cues[1]['end_seconds'], 7.5)

    def test_proponer_hablante(self):
        from apps.wiki.models import SpeakerNameProposal
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc131x')
        post.transcript_segments.create(start_seconds=0, end_seconds=3,
                                        text='Hola.', speaker_label='SPEAKER_00')
        self.client.force_login(user)
        self.client.post(f'/post/{post.pk}/hablante/proponer/',
                         {'label': 'SPEAKER_00', 'name': 'Pedro Sánchez'})
        self.assertTrue(SpeakerNameProposal.objects.filter(
            post=post, candidate_name='Pedro Sánchez', source='user').exists())
        self.client.post(f'/post/{post.pk}/hablante/proponer/',
                         {'label': 'SPEAKER_99', 'name': 'Intruso'})
        self.assertFalse(SpeakerNameProposal.objects.filter(candidate_name='Intruso').exists())

    @override_settings(MOCK_AGENTS=True)
    def test_titulo_inmediato_en_mock(self):
        from apps.embeds.adapters import fetch_title
        self.assertIn('SIMULADO', fetch_title('https://youtu.be/x', 'youtube'))


class Pase43A(TestCase):
    """4.3-A: preferencias por tipo, foro clasico (no leidos) y firma."""

    def test_pref_apagada_silencia_el_tipo(self):
        from apps.accounts.services import notify
        from apps.accounts.models import Notification
        user = make_user()
        user.notify_prefs = {'post_votes': False}
        user.save(update_fields=['notify_prefs'])
        notify(user, 'te han votado', '/x/', kind='post_votes')
        notify(user, 'veredictos listos', '/y/', kind='post_phase')
        textos = list(Notification.objects.filter(user=user).values_list('text', flat=True))
        self.assertEqual(textos, ['veredictos listos'])

    def test_separador_de_no_leidos(self):
        from apps.forum.machina_glue import create_topic_for_post, add_reply, get_topic_for_post
        from apps.forum.models import TopicRead
        lector = make_user()
        autor = make_user(username='a2', email='a2@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/abc132x',
                                   title='Hilo de prueba')
        create_topic_for_post(post)
        self.client.force_login(lector)
        self.client.get(f'/post/{post.pk}/')          # primera visita: marca leido
        add_reply(post, autor, 'mensaje nuevo tras tu visita')
        r = self.client.get(f'/post/{post.pk}/')
        self.assertContains(r, 'Nuevos desde tu última visita')
        topic = get_topic_for_post(post)
        tr = TopicRead.objects.get(user=lector, topic_id=topic.pk)
        self.assertEqual(tr.last_post_id, topic.posts.order_by('created').last().pk)


class Pase43A1(TestCase):
    """Hotfix 4.3-A.1: recarga solo en transición, plantillas sin {# #} rotos,
    registro con candado y candidatos automáticos purgados de la vista."""

    def test_guardia_sin_comentarios_multilinea(self):
        # Los {# #} de Django son de UNA linea: uno multilinea se RENDERIZA como
        # texto (paso dos veces en produccion). Este test rompe el CI a la tercera.
        import pathlib, re
        raiz = pathlib.Path(__file__).resolve().parent.parent / 'templates'
        malos = []
        for f in raiz.rglob('*.html'):
            for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
                if '{#' in line and '#}' not in line:
                    malos.append(f'{f.name}:{i}')
        self.assertEqual(malos, [], f'Comentarios multilínea {{# #}}: {malos}')

    def test_transicion_emite_eventos_y_jamas_recarga(self):
        post = Post.objects.create(author=make_user(), url='https://youtu.be/abc133x',
                                   status='DONE')
        r = self.client.get(f'/post/{post.pk}/status/?prev=CHEAP_RUNNING')
        self.assertIsNone(r.headers.get('HX-Refresh'))          # recargas: EXTINTAS
        self.assertIn('isttBodyRefresh', r.headers.get('HX-Trigger', ''))
        self.assertIn('isttToast', r.headers.get('HX-Trigger', ''))
        r = self.client.get(f'/post/{post.pk}/status/?prev=DONE')
        self.assertIsNone(r.headers.get('HX-Trigger'))          # ya terminal: silencio
        r = self.client.get(f'/post/{post.pk}/status/')
        self.assertIsNone(r.headers.get('HX-Trigger'))          # sin prev: silencio

    def test_bocadillo_de_mensajes_nuevos(self):
        from apps.forum.machina_glue import create_topic_for_post, add_reply
        autor = make_user()
        post = Post.objects.create(author=autor, url='https://youtu.be/abc135x',
                                   title='Hilo bocadillo')
        create_topic_for_post(post)
        primero = add_reply(post, autor, 'primero')
        add_reply(post, autor, 'segundo, el nuevo')
        r = self.client.get(f'/post/{post.pk}/fragmento/hilo/?ultimo={primero.pk}')
        self.assertIn('isttToast', r.headers.get('HX-Trigger', ''))
        r = self.client.get(f'/post/{post.pk}/fragmento/hilo/?ultimo=999999')
        self.assertIsNone(r.headers.get('HX-Trigger'))

    def test_registro_con_candado(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='registration_open',
                                               defaults={'value': '0'})
        r = self.client.get('/accounts/register/')
        self.assertEqual(r.status_code, 302)                    # cerrado: a portada
        SystemSetting.objects.update_or_create(key='registration_open',
                                               defaults={'value': '1'})
        self.assertEqual(self.client.get('/accounts/register/').status_code, 200)

    def test_candidatos_automaticos_fuera_de_la_vista(self):
        from apps.wiki.models import SpeakerNameProposal
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc134x')
        post.transcript_segments.create(start_seconds=0, end_seconds=3,
                                        text='Hola.', speaker_label='SPEAKER_00')
        SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00',
                                           candidate_name='Edición Daniel Castresana',
                                           source='ocr')
        SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00',
                                           candidate_name='Pedro Sánchez', source='user')
        r = self.client.get(f'/post/{post.pk}/')
        self.assertNotContains(r, 'Castresana')
        self.assertContains(r, 'Pedro Sánchez')

    def test_sonido_de_bocadillos_configurable(self):
        user = make_user()
        self.client.force_login(user)
        self.client.post('/accounts/settings/', {'toast_sound': 'on',
                                                 'pref_mentions': 'on',
                                                 'notify_mode': 'WEB',
                                                 'digest_hour': '8'})
        user.refresh_from_db()
        self.assertTrue(user.notify_prefs.get('toast_sound'))
        self.assertTrue(user.wants('mentions'))
        r = self.client.get('/')
        self.assertContains(r, 'data-toast-sound="1"')


class Pase43A3(TestCase):
    """4.3-A.3: página ancha de verdad, panel con nombres y registro como toggle."""

    def test_panel_muestra_permitir_registro(self):
        admin = make_user(username='root1', email='root1@example.org')
        admin.is_staff = admin.is_superuser = True
        admin.save()
        self.client.force_login(admin)
        r = self.client.get('/panel/settings/')
        self.assertContains(r, 'Permitir registro de nuevos usuarios')
        # apagar el toggle (checkbox ausente en el POST) cierra el registro
        self.client.post('/panel/settings/', {'votes_to_validate': '5'})
        from apps.panel.models import SystemSetting
        self.assertEqual(SystemSetting.get_int('registration_open', 1), 0)
        self.client.post('/panel/settings/', {'registration_open': 'on'})
        self.assertEqual(SystemSetting.get_int('registration_open', 1), 1)

    def test_pagina_del_post_es_ancha(self):
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc136x',
                                   title='Ancho total')
        # M2: los data-start/data-end los emite CADA frase — sin transcripcion no
        # hay atributos que comprobar (el test original creaba el post vacio).
        post.transcript_segments.create(start_seconds=0, end_seconds=4.5,
                                        text='Frase de prueba para el seguimiento en vivo.')
        r = self.client.get(f'/post/{post.pk}/')
        self.assertContains(r, '<main class="wide">')
        self.assertContains(r, 'data-end=')
        css = open('static/css/main.css').read()
        self.assertNotIn('100vw', css)   # el contenedor cutre, extinto con test


class Pase43A4(TestCase):
    """4.3-A.4: tres columnas reales (transcripción a la derecha, no debajo),
    scroll desacoplado, y la ficha del hablante activo iluminada en grisáceo."""

    def test_transcripcion_dentro_de_la_columna_derecha(self):
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc137x',
                                   title='Tres columnas')
        r = self.client.get(f'/post/{post.pk}/')
        html = r.content.decode()
        # la caja de transcripción debe estar DENTRO de la aside derecha, no suelta debajo
        i_col = html.find('transcript-col')
        i_box = html.find('transcript transcript-box')
        i_close = html.find('</aside>', i_col)
        self.assertTrue(i_col != -1 and i_box != -1)
        self.assertLess(i_col, i_box)          # la columna abre antes que la caja
        self.assertLess(i_box, i_close)        # y la caja está antes de que cierre la columna
        self.assertEqual(html.count('transcript transcript-box'), 1)  # sin duplicar

    def test_ficha_de_hablante_marcada_para_iluminar(self):
        css = open('static/css/main.css').read()
        js = open('static/js/transcript.js').read()
        self.assertIn('.speaker-block.speaking', css)   # el grisáceo existe
        self.assertIn('iluminarHablante', js)           # y el JS lo activa

    def test_grid_no_es_sticky_global(self):
        # la rejilla entera dejó de ser sticky (eso acoplaba el scroll)
        css = open('static/css/main.css').read()
        bloque = css.split('.media-grid{')[1][:80]
        self.assertNotIn('position:sticky', bloque)


class Pase43A5(TestCase):
    """4.3-A.5: segmentos en orden cronológico (fallo de raíz del desorden),
    intervención activa en negro con texto blanco, y reanálisis manual de moderador."""

    def test_segmentos_en_orden_cronologico(self):
        from apps.analysis.models import TranscriptSegment
        user = make_user()
        post = Post.objects.create(author=user, url='https://youtu.be/abc138x',
                                   title='Orden')
        # se crean DESORDENADOS a propósito, como venían del pipeline
        for start in (194.21, 17.25, 22.25, 5.01, 91.29):
            TranscriptSegment.objects.create(post=post, start_seconds=start,
                                             end_seconds=start + 2, text=f'f{start}')
        r = self.client.get(f'/post/{post.pk}/')
        segs = r.context['segments']
        tiempos = [s.start_seconds for s in segs]
        self.assertEqual(tiempos, sorted(tiempos))          # cronológico, no de inserción
        self.assertEqual(tiempos[0], 5.01)

    def test_frase_activa_en_negro_texto_blanco(self):
        css = open('static/css/main.css').read()
        self.assertIn('.segment.live{background:#141414', css)
        self.assertIn('.segment.live,.segment.live .text{color:#fff}', css)

    def test_reanalizar_solo_moderador(self):
        from apps.analysis.models import TranscriptSegment
        author = make_user()
        post = Post.objects.create(author=author, url='https://youtu.be/abc139x',
                                   title='Rean', status='DONE')
        TranscriptSegment.objects.create(post=post, start_seconds=1.0,
                                         end_seconds=3.0, text='vieja')
        # un usuario normal NO puede reanalizar
        self.client.force_login(author)
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as m:
            self.client.post(f'/post/{post.pk}/reanalizar/')
            m.assert_not_called()
        self.assertEqual(post.transcript_segments.count(), 1)  # intacto
        # un moderador SÍ: borra segmentos y lanza el pipeline
        mod = make_user(username='modx', email='modx@example.org')
        mod.is_staff = True
        mod.save()
        self.client.force_login(mod)
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as m:
            self.client.post(f'/post/{post.pk}/reanalizar/')
            m.assert_called_once()
        post.refresh_from_db()
        self.assertEqual(post.transcript_segments.count(), 0)  # limpiado
        self.assertEqual(post.status, 'NEW')

    def test_toggle_registro_destacado_en_panel(self):
        admin = make_user(username='root9', email='root9@example.org')
        admin.is_staff = admin.is_superuser = True
        admin.save()
        self.client.force_login(admin)
        r = self.client.get('/panel/settings/')
        # el registro va en su sección destacada (reg-gate), separado de los umbrales
        self.assertContains(r, 'reg-gate')
        self.assertContains(r, 'Permitir registro de nuevos usuarios')
        self.assertContains(r, 'name="registration_open"')
        # y sigue guardando 1/0 con el toggle
        self.client.post('/panel/settings/', {'votes_to_validate': '5'})
        from apps.panel.models import SystemSetting
        self.assertEqual(SystemSetting.get_int('registration_open', 1), 0)
        self.client.post('/panel/settings/', {'registration_open': 'on'})
        self.assertEqual(SystemSetting.get_int('registration_open', 1), 1)


class Pase43A6(TestCase):
    """4.3-A.6: el panel deja de ser un archipiélago — cabecera INTEGRADA (un solo
    <h1> "Panel" + pestañas), /panel/ y el menú aterrizan en Ajustes (donde vive la
    puerta del registro), y la píldora "Hablante N" se lee sobre el fondo negro de
    la intervención activa (blanca maciza con texto negro)."""

    RUTAS = ['/panel/settings/', '/panel/codes/', '/panel/donaciones/',
             '/panel/moderadores/', '/panel/moderador/',
             '/panel/reclamaciones/', '/panel/staging/']

    def setUp(self):
        self.admin = make_user(username='rootA6', email='roota6@example.org')
        self.admin.is_staff = self.admin.is_superuser = True
        self.admin.save()
        self.client.force_login(self.admin)

    def test_todas_las_secciones_del_panel_llevan_pestanas(self):
        for ruta in self.RUTAS:
            r = self.client.get(ruta)
            self.assertEqual(r.status_code, 200, ruta)
            self.assertContains(r, 'panel-tabs')                # la barra existe
            self.assertContains(r, 'href="/panel/settings/"')   # Ajustes a un clic
            self.assertContains(r, 'href="/panel/codes/"')

    def test_cabecera_del_panel_integrada(self):
        """David: "Panel" y "Ajustes" se integran — un h1 para todo el panel."""
        for ruta in self.RUTAS:
            html = self.client.get(ruta).content.decode()
            self.assertEqual(html.count('<h1'), 1, ruta)        # ni dos titulos ni cero
            self.assertIn('panel-head', html)
        r = self.client.get('/panel/settings/')
        self.assertNotContains(r, 'Ajustes vivos')              # el titulo viejo, fuera
        self.assertContains(r, 'aria-current="page"')           # la pestaña activa, marcada

    def test_el_menu_y_barra_panel_aterrizan_en_ajustes(self):
        r = self.client.get('/')
        self.assertContains(r, 'href="/panel/settings/"')       # el masthead ya no va a Códigos
        self.assertNotContains(r, 'href="/panel/codes/"')
        self.assertRedirects(self.client.get('/panel/'), '/panel/settings/')

    def test_pildora_de_hablante_legible_sobre_negro(self):
        css = open('static/css/main.css').read()
        self.assertIn('.segment.live .speaker-tag,.speaker-block.speaking .speaker-tag{', css)
        self.assertIn('background:#fff;border-color:#fff;color:#141414', css)

    def test_botones_de_voto_visibles_en_la_frase_activa(self):
        css = open('static/css/main.css').read()
        self.assertIn('.segment.live .ibtn{color:#fff}', css)


class AutocompletadoHablantes(TestCase):
    """Identificación unívoca de hablantes con Wikidata (2026-08-17, David).
    La diarización pone SPEAKER_XX; el usuario pone NOMBRE con identidad (QID)."""

    def _post_con_hablante(self):
        post = Post.objects.create(author=make_user(username='autorwd',
                                                    email='autorwd@example.org'),
                                   url='https://youtu.be/abcwd01', status='DONE')
        post.transcript_segments.create(start_seconds=0, end_seconds=4,
                                        text='Frase del hablante.',
                                        speaker_label='SPEAKER_00')
        return post

    def test_busqueda_filtra_personas_y_degrada_con_aviso(self):
        from apps.agents import wikidata
        from django.core.cache import cache
        cache.clear()
        buscar = {'search': [{'id': 'Q3116471'}, {'id': 'Q27738'}]}
        entidades = {'entities': {
            'Q3116471': {'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}],
                                    'P18': [{'mainsnak': {'datavalue': {'value': 'Foto.jpg'}}}]},
                         'labels': {'es': {'value': 'Pedro Sánchez'}},
                         'descriptions': {'es': {'value': 'político español'}}},
            'Q27738': {'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q4830453'}}}}]},
                       'labels': {'es': {'value': 'Empresa S.A.'}}, 'descriptions': {}}}}
        respuestas = [mock.Mock(status_code=200, **{'json.return_value': buscar,
                                                    'raise_for_status.return_value': None}),
                      mock.Mock(status_code=200, **{'json.return_value': entidades,
                                                    'raise_for_status.return_value': None})]
        with mock.patch.object(wikidata.httpx, 'get', side_effect=respuestas):
            res = wikidata.search_people('Pedro Sánchez')
        self.assertEqual(len(res), 1)                      # la empresa se descarta
        self.assertEqual(res[0]['qid'], 'Q3116471')
        self.assertEqual(res[0]['description'], 'político español')
        self.assertIn('Foto.jpg', res[0]['photo'])
        cache.clear()
        with mock.patch.object(wikidata.httpx, 'get', side_effect=OSError('sin red')):
            with self.assertLogs('agents.wikidata', level='WARNING') as logs:
                self.assertEqual(wikidata.search_people('Pedro Sánchez'), [])
        self.assertTrue(any('Wikidata' in m for m in logs.output))

    def test_endpoint_exige_login_y_devuelve_json(self):
        from apps.agents import wikidata
        post = self._post_con_hablante()
        self.assertEqual(self.client.get('/hablante/buscar/?q=pedro').status_code, 302)
        self.client.force_login(post.author)
        with mock.patch.object(wikidata, 'search_people',
                               return_value=[{'qid': 'Q1', 'name': 'X', 'description': 'y', 'photo': ''}]):
            r = self.client.get('/hablante/buscar/?q=pedro')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['results'][0]['qid'], 'Q1')

    def test_propuesta_guarda_el_qid_y_rechaza_uno_falso(self):
        from apps.wiki.models import SpeakerNameProposal
        from apps.analysis import views as aviews
        post = self._post_con_hablante()
        self.client.force_login(post.author)
        with mock.patch.object(aviews, 'Post', Post):  # no toca red: se mockea la foto
            with mock.patch('apps.agents.wikidata.entity_photo', return_value='http://x/f.jpg'):
                self.client.post(f'/post/{post.pk}/hablante/proponer/',
                                 {'label': 'SPEAKER_00', 'name': 'Pedro Sánchez',
                                  'qid': 'Q3116471', 'qdesc': 'político español'})
        p = SpeakerNameProposal.objects.get(candidate_name='Pedro Sánchez')
        self.assertEqual(p.wikidata_id, 'Q3116471')
        self.assertEqual(p.description, 'político español')
        with mock.patch('apps.agents.wikidata.photo_for', return_value=''):
            self.client.post(f'/post/{post.pk}/hablante/proponer/',
                             {'label': 'SPEAKER_00', 'name': 'Nombre Libre',
                              'qid': '<script>', 'qdesc': 'x'})
        self.assertEqual(SpeakerNameProposal.objects.get(
            candidate_name='Nombre Libre').wikidata_id, '')      # QID falso: ignorado

    def test_homonimos_son_dos_fichas_distintas(self):
        """La prueba de fuego de la identidad unívoca."""
        from apps.wiki.models import Interlocutor, SpeakerNameProposal
        from apps.wiki.naming import _person_for
        p1 = SpeakerNameProposal(post=self._post_con_hablante(), speaker_label='SPEAKER_00',
                                 candidate_name='Pedro Sánchez', wikidata_id='Q3116471',
                                 description='político español')
        p2 = SpeakerNameProposal(post=self._post_con_hablante(), speaker_label='SPEAKER_00',
                                 candidate_name='Pedro Sánchez', wikidata_id='Q9999999',
                                 description='futbolista')
        a, b = _person_for(p1), _person_for(p2)
        self.assertNotEqual(a.pk, b.pk)                 # mismo nombre, DOS personas
        self.assertNotEqual(a.slug, b.slug)
        self.assertEqual(a.wikidata_id, 'Q3116471')
        # El mismo QID SIEMPRE devuelve la misma ficha (idempotente):
        self.assertEqual(_person_for(p1).pk, a.pk)
        self.assertEqual(Interlocutor.objects.filter(name='Pedro Sánchez').count(), 2)
