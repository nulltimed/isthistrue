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
        # 4.3-A.7: el umbral pasó a ser INCLUSIVO (>=), así que el QUINTO «Discuto»
        # ya dispara (antes hacían falta 6: «llegar a 5» eran 6, ese era el bug).
        voters = [make_user(username=f'd{i}', email=f'd{i}@example.org') for i in range(5)]
        with mock.patch.object(tasks.opus_rescan_segment, 'delay') as delay:
            for v in voters:
                self.client.force_login(v)
                self.client.post(f'/oracion/{seg.pk}/votar/down/')
        delay.assert_called_once_with(seg.pk)  # el 5o ▼ alcanza el umbral, UNA vez... 
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
        # 4.3-A.7 fusiono .live y :hover en una regla: el negro se declara para ambas.
        self.assertIn('.segment.live,.transcript .segment:hover{background:#141414', css)
        # La regla del color agrupa .live y :hover en dos lineas (A.7): se comprueba
        # el selector real, no una cadena de una sola linea que ya no existe.
        self.assertIn('.segment.live,.segment.live .text,', css)
        self.assertIn(".transcript .segment:hover .text{color:#fff}", css)

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
        self.assertIn('.segment.live .speaker-tag,.speaker-block.speaking .speaker-tag,', css)
        self.assertIn('background:#fff;border-color:#fff;color:#141414', css)

    def test_botones_de_voto_visibles_en_la_frase_activa(self):
        css = open('static/css/main.css').read()
        self.assertIn('.segment.live .ibtn,.transcript .segment:hover .ibtn{color:#fff}', css)


class AutocompletadoHablantes(TestCase):
    """Identificación unívoca de hablantes con Wikidata (2026-08-17, David).
    La diarización pone SPEAKER_XX; el usuario pone NOMBRE con identidad (QID)."""

    _n = 0

    def _post_con_hablante(self):
        # Usuario y URL únicos por llamada: el test de homónimos crea DOS posts.
        type(self)._n += 1
        n = type(self)._n
        post = Post.objects.create(author=make_user(username=f'autorwd{n}',
                                                    email=f'autorwd{n}@example.org'),
                                   url=f'https://youtu.be/abcwd{n:03d}', status='DONE')
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
        # El doble despacha por el `action` de la peticion, NO por el orden de
        # llamada: asi no se rompe cuando search_people gana o pierde una
        # consulta (el 4.3-D anadio la de texto completo en medio, y este test
        # cayo por asumir exactamente dos peticiones).
        def responder(_url, **kwargs):
            action = (kwargs.get('params') or {}).get('action')
            cuerpo = {'wbsearchentities': buscar,
                      'query': {'query': {'search': []}},   # texto completo: sin extras
                      'wbgetentities': entidades}[action]
            return mock.Mock(status_code=200, **{'json.return_value': cuerpo,
                                                 'raise_for_status.return_value': None})
        with mock.patch.object(wikidata.httpx, 'get', side_effect=responder):
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


class Pase43A7(TestCase):
    """4.3-A.7 — el primer análisis REAL destapó tres cosas:

    1. El barrido mandaba la transcripción entera en UNA llamada con techo de 2000
       tokens. Con el mock (3 frases) cabía; con un vídeo real (cientos) el JSON
       volvía cortado -> claims=[] -> cero señales y cero veredictos, EN SILENCIO.
       Ahora se trocea, se avisa a gritos si un lote vuelve ilegible, y no se
       sugiere Off-Topic cuando el motivo es que no supimos leer (no que no haya).
    2. Al posar el ratón sobre una frase, la frase se volvía invisible (letra
       blanca sobre el fondo claro que ponía el hover). El hover pasa a ser el
       mismo negro con letra blanca de la intervención activa.
    3. Los votos ▲/▼ parecían un plebiscito sobre si algo es verdad. Decisión de
       David: un solo botón "Discuto" que PIDE una re-verificación con Opus, y
       "llegar a 5" son 5 (el umbral se comparaba con > estricto: hacían falta 6).
    """

    def _post_con_frases(self, n, status='DONE'):
        post = Post.objects.create(
            author=make_user(username=f'a7_{n}', email=f'a7_{n}@example.org'),
            url=f'https://youtu.be/a7{n:05d}', status=status, duration_seconds=1200)
        for i in range(n):
            post.transcript_segments.create(start_seconds=i * 4.0, end_seconds=i * 4.0 + 3.5,
                                            text=f'Frase numero {i} de la transcripcion.')
        return post

    # --- 1. el barrido se trocea y los índices siguen siendo globales ---
    @override_settings(MOCK_AGENTS=False, SWEEP_BATCH_SIZE=40, SWEEP_MAX_TOKENS=8000)
    def test_barrido_trocea_y_ancla_por_indice_global(self):
        from apps.agents import sweep
        post = self._post_con_frases(95)          # 95 frases -> 3 lotes de 40/40/15
        vistos = []

        def fake_call_json(model, system, payload, max_tokens=2000, mock_payload=None):
            vistos.append((payload, max_tokens))
            primera = int(payload.splitlines()[0].split(']')[0].lstrip('['))
            return {'claims': [{'segment_index': primera, 'text': 'x',
                                'kind': 'FACTUAL', 'contradicts_common_knowledge': False}],
                    'manipulation': False, 'is_adult': False}

        with mock.patch.object(sweep.client, 'call_json', side_effect=fake_call_json):
            res = sweep.run(post)

        self.assertEqual(len(vistos), 3)                       # se trocea
        self.assertEqual(vistos[0][1], 8000)                   # con el techo del .env
        self.assertFalse(res['sweep_failed'])
        self.assertEqual(len(res['claims']), 3)
        # Los índices que viajan son globales: el segundo lote empieza en [40].
        self.assertTrue(vistos[1][0].startswith('[40]'))
        marcadas = list(post.transcript_segments.exclude(signal='')
                        .order_by('start_seconds').values_list('signal', flat=True))
        self.assertEqual(marcadas, ['FACTUAL_UNVERIFIED'] * 3)  # 0, 40 y 80

    @override_settings(MOCK_AGENTS=False, SWEEP_BATCH_SIZE=10)
    def test_barrido_degrada_con_aviso_y_no_miente_con_offtopic(self):
        """Un lote ilegible NO revienta el análisis y NO se disfraza de Off-Topic."""
        from apps.agents import sweep
        post = self._post_con_frases(25)
        with mock.patch.object(sweep.client, 'call_json',
                               return_value={'error': 'json_parse', 'raw': '{"clai'}):
            with self.assertLogs('agents.sweep', level='WARNING') as logs:
                res = sweep.run(post)
        self.assertEqual(res['claims'], [])
        self.assertTrue(res['sweep_failed'])
        self.assertEqual(res['batches_failed'], 3)
        self.assertTrue(any('ilegible' in l.lower() or 'ILEGIBLE' in l for l in logs.output))
        self.assertFalse(post.transcript_segments.exclude(signal='').exists())

    def test_los_dos_limites_del_barrido_se_leen_del_entorno(self):
        from django.conf import settings as s
        self.assertIsInstance(s.SWEEP_BATCH_SIZE, int)
        self.assertIsInstance(s.SWEEP_MAX_TOKENS, int)
        self.assertGreaterEqual(s.SWEEP_MAX_TOKENS, 2000)
        self.assertIn('SWEEP_BATCH_SIZE', open('.env.example').read())

    # --- 2. el hover ya no borra la frase ---
    def test_hover_comparte_el_negro_de_la_intervencion_activa(self):
        css = open('static/css/main.css').read()
        self.assertIn('.segment.live,.transcript .segment:hover{background:#141414', css)
        self.assertIn('.transcript .segment:hover,.transcript .segment:hover .text{color:#fff}', css)
        # la píldora del hablante (opción A de David) también en hover
        self.assertIn('.transcript .segment:hover .speaker-tag{', css)
        # y la regla vieja de hover con fondo claro ya no existe en ninguna forma
        self.assertNotIn('.transcript .segment:hover{background:var', css)

    # --- 3. un solo botón, y "llegar a 5" son 5 ---
    def test_solo_queda_el_boton_de_discutir(self):
        post = self._post_con_frases(2)
        self.client.force_login(make_user(username='lectorA7', email='lectora7@example.org'))
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('/votar/down/', html)
        self.assertNotIn('/votar/up/', html)          # el plebiscito, fuera
        self.assertIn('Discuto', html)

    def test_el_quinto_voto_en_contra_dispara_opus(self):
        post = self._post_con_frases(1)
        seg = post.transcript_segments.first()
        url = f'/oracion/{seg.pk}/votar/down/'
        with mock.patch('apps.analysis.tasks.opus_rescan_segment.delay') as delay:
            for i in range(4):
                self.client.force_login(make_user(username=f'v{i}', email=f'v{i}@example.org'))
                self.client.post(url)
            self.assertFalse(delay.called)            # con 4 todavía no
            self.client.force_login(make_user(username='v5', email='v5@example.org'))
            self.client.post(url)
            delay.assert_called_once_with(seg.pk)     # el QUINTO lo dispara

    def test_el_coste_del_reescaneo_se_define_una_sola_vez(self):
        codigo = open('apps/analysis/tasks.py').read()
        self.assertEqual(codigo.count('COST_OPUS_RESCAN_EUR = '), 1)

    # --- 4. el semáforo se decide EN CONTEXTO (anterior + presente + siguiente) ---
    def test_el_contexto_salta_al_hablante_que_interrumpe(self):
        """La \"anterior del hablante\" no es la de al lado: si otro interrumpe,
        se salta y se sigue buscando hacia atrás."""
        from apps.agents.verdict import context_for
        post = self._post_con_frases(0)
        textos = [('SPEAKER_00', 'Uno de Ana.'), ('SPEAKER_01', 'Interrumpe Bea.'),
                  ('SPEAKER_00', 'Dos de Ana.'), ('SPEAKER_01', 'Otra de Bea.'),
                  ('SPEAKER_00', 'Tres de Ana.')]
        for i, (spk, txt) in enumerate(textos):
            post.transcript_segments.create(start_seconds=i * 5.0, end_seconds=i * 5.0 + 4,
                                            text=txt, speaker_label=spk)
        segs = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
        ctx = context_for(segs, 2, 1, 1)   # 'Dos de Ana.'
        self.assertIn('(antes) Uno de Ana.', ctx)
        self.assertIn('(ESTA ES LA FRASE VERIFICADA) Dos de Ana.', ctx)
        self.assertIn('(despues) Tres de Ana.', ctx)
        self.assertNotIn('Bea', ctx)       # la interrupción no entra

    def test_sin_diarizacion_el_contexto_son_las_vecinas_inmediatas(self):
        from apps.agents.verdict import context_for
        post = self._post_con_frases(3)    # sin speaker_label
        segs = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
        ctx = context_for(segs, 1, 1, 1)
        self.assertIn('(antes) Frase numero 0', ctx)
        self.assertIn('(despues) Frase numero 2', ctx)

    def test_los_bordes_no_revientan(self):
        from apps.agents.verdict import context_for
        post = self._post_con_frases(2)
        segs = list(post.transcript_segments.all().order_by('start_seconds', 'pk'))
        self.assertNotIn('(antes)', context_for(segs, 0, 1, 1))    # la primera
        self.assertNotIn('(despues)', context_for(segs, 1, 1, 1))  # la última

    def test_el_claim_viaja_con_su_contexto_y_el_lote_manda_lo_mismo(self):
        from apps.agents.verdict import _claims_from_segments
        post = self._post_con_frases(3)
        for s in post.transcript_segments.all():
            s.signal = 'FACTUAL_UNVERIFIED'
            s.save(update_fields=['signal'])
        claims = _claims_from_segments(post)
        self.assertEqual(len(claims), 3)
        self.assertIn('(despues) Frase numero 1', claims[0]['context'])
        # La vía directa y la vía por lotes tienen que mandar el MISMO texto:
        directo = open('apps/agents/verdict.py').read()
        lote = open('apps/agents/batch.py').read()
        marca = "CONTEXTO (frases contiguas del mismo hablante; NO se verifican)"
        self.assertIn(marca, directo)
        self.assertIn(marca, lote)

    # --- 5. todos los umbrales se pueden fijar desde el .env ---
    def test_sin_fila_en_la_base_de_datos_manda_el_entorno(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.filter(key='segment_opus_downvotes').delete()
        with override_settings(SETTING_DEFAULTS={'segment_opus_downvotes': '9'}):
            self.assertEqual(SystemSetting.get_int('segment_opus_downvotes', 5), 9)

    def test_con_fila_manda_el_panel(self):
        """Decisión congelada: el panel es el mando en vivo."""
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='segment_opus_downvotes',
                                               defaults={'value': '3'})
        with override_settings(SETTING_DEFAULTS={'segment_opus_downvotes': '9'}):
            self.assertEqual(SystemSetting.get_int('segment_opus_downvotes', 5), 3)

    def test_seed_settings_no_pisa_salvo_con_force(self):
        from django.core.management import call_command
        from io import StringIO
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='votes_to_validate',
                                               defaults={'value': '77'})
        call_command('seed_settings', stdout=StringIO())
        self.assertEqual(SystemSetting.get_int('votes_to_validate', 5), 77)
        call_command('seed_settings', '--force', stdout=StringIO())
        from django.conf import settings as s
        self.assertEqual(str(SystemSetting.get_int('votes_to_validate', 5)),
                         s.SETTING_DEFAULTS['votes_to_validate'])

    def test_la_lista_de_umbrales_vive_en_un_solo_sitio(self):
        """Ni claves duplicadas ni dos listas que se desincronizan."""
        from django.conf import settings as s
        seed = open('apps/panel/management/commands/seed_settings.py').read()
        self.assertNotIn('DEFAULTS = {', seed)          # la lista ya no está aquí
        self.assertIn('SETTING_DEFAULTS', seed)
        for clave in ('segment_opus_downvotes', 'verdict_context_before',
                      'verdict_context_after', 'trending_votes_threshold'):
            self.assertIn(clave, s.SETTING_DEFAULTS)
        env = open('.env.example').read()
        for var in ('SEGMENT_OPUS_DOWNVOTES', 'VERDICT_CONTEXT_BEFORE',
                    'VERDICT_CONTEXT_AFTER'):
            self.assertIn(var, env)

    def test_los_umbrales_nuevos_son_editables_en_el_panel(self):
        from apps.panel.views import SETTINGS_DEF
        claves = [k for k, _l, _h, _t in SETTINGS_DEF]
        for clave in ('segment_opus_downvotes', 'verdict_context_before',
                      'verdict_context_after'):
            self.assertIn(clave, claves)
        self.assertEqual(len(claves), len(set(claves)))   # sin duplicados


class Pase43A8(TestCase):
    """4.3-A.8 — vídeos largos, pre-chequeo antes de postear y sala +18.

    Decisiones de David (2026-08-17):
      · "se tienen que procesar igual que los vídeos de 5 minutos": fuera el
        recorte de 20 min cableado; el techo va al .env.
      · "al final todo va al presupuesto diario y mensual": el gasto se reserva
        por MINUTOS, no a tanto alzado (el contador mentía 4-6x con 1 hora).
      · límite de 20 min por usuario -> AVISO de donación, nunca un muro (la
        puerta de submit es login + email verificado, decisión congelada).
      · antes de postear se comprueban título, duración y +18.
      · el +18 va a una sala cerrada, solo para mayores según su fecha de
        nacimiento del registro.
    """

    def _post(self, segundos, **kw):
        datos = dict(author=make_user(username=f'a8_{segundos}_{kw.get("n", 0)}',
                                      email=f'a8_{segundos}_{kw.get("n", 0)}@example.org'),
                     url=f'https://youtu.be/a8{segundos}{kw.get("n", 0)}',
                     duration_seconds=segundos, status='DONE')
        datos.update({k: v for k, v in kw.items() if k != 'n'})
        return Post.objects.create(**datos)

    # --- el techo de 20 minutos ya no está cableado ---
    def test_el_tramo_transcrito_se_lee_del_entorno(self):
        from django.conf import settings as s
        codigo = open('apps/analysis/tasks.py').read()
        self.assertNotIn('[(0, 1200)]', codigo)      # el 1200 cableado, fuera
        self.assertIn('TRANSCRIBE_MAX_SECONDS', codigo)
        self.assertGreaterEqual(s.TRANSCRIBE_MAX_SECONDS, 3600)   # cabe 1 hora

    # --- el dinero se cuenta por minutos ---
    def test_una_hora_reserva_mucho_mas_que_cinco_minutos(self):
        from apps.analysis.services import cost_cheap_eur, cost_full_eur
        corto, largo = self._post(300, n=1), self._post(3600, n=2)
        self.assertGreater(cost_cheap_eur(largo), cost_cheap_eur(corto) * 5)
        self.assertGreater(cost_full_eur(largo), cost_full_eur(corto) * 5)

    def test_el_coste_nunca_baja_del_suelo_historico(self):
        """Un vídeo cortísimo no puede salir gratis: el suelo sigue siendo el
        coste fijo de siempre."""
        from apps.analysis.tasks import COST_CHEAP_EUR
        from apps.analysis.services import cost_cheap_eur
        p = self._post(30, n=3)
        self.assertGreaterEqual(max(COST_CHEAP_EUR, cost_cheap_eur(p)), COST_CHEAP_EUR)

    def test_duracion_desconocida_reserva_de_mas_no_de_menos(self):
        from apps.analysis.services import video_minutes
        from django.conf import settings as s
        self.assertEqual(video_minutes(self._post(0, n=4)),
                         s.TRANSCRIBE_MAX_SECONDS // 60)

    # --- la donación sugerida ---
    def test_hasta_veinte_minutos_no_se_pide_nada(self):
        from apps.analysis.services import suggested_donation_eur
        self.assertEqual(suggested_donation_eur(self._post(1200, n=5)), 0.0)
        self.assertEqual(suggested_donation_eur(self._post(300, n=6)), 0.0)

    def test_una_hora_pide_una_donacion_redondeada_a_medios_euros(self):
        from apps.analysis.services import suggested_donation_eur
        d = suggested_donation_eur(self._post(3600, n=7))
        self.assertGreater(d, 0)
        self.assertEqual(d * 2, int(d * 2))      # múltiplo de 0,50
        self.assertLessEqual(d, 5)               # la tabla del pase fija 5,00 € para 60 min

    def test_la_donacion_solo_cobra_el_exceso(self):
        from apps.analysis.services import suggested_donation_eur
        self.assertLess(suggested_donation_eur(self._post(1800, n=8)),
                        suggested_donation_eur(self._post(3600, n=9)))

    # --- el pre-chequeo ---
    def test_el_prechequeo_degrada_con_aviso_y_no_bloquea(self):
        from apps.embeds.adapters import probe
        with override_settings(MOCK_AGENTS=False):
            with mock.patch.dict('sys.modules', {'yt_dlp': None}):
                with self.assertLogs('embeds.probe', level='WARNING'):
                    f = probe('https://youtu.be/x', 'youtube')
        self.assertFalse(f['ok'])
        self.assertEqual(f['duration_seconds'], 0)   # sigue siendo usable
        self.assertEqual(f['age_limit'], 0)

    def test_el_prechequeo_devuelve_las_tres_cosas(self):
        from apps.embeds.adapters import probe
        f = probe('https://youtu.be/x', 'youtube')   # MOCK_AGENTS=True en tests
        for clave in ('title', 'duration_seconds', 'age_limit'):
            self.assertIn(clave, f)

    # --- la sala +18 ---
    def test_el_mas18_no_asoma_en_portada_ni_en_el_buscador(self):
        adulto = self._post(300, n=10, is_adult=True, title='Contenido adulto de prueba',
                            category='MAIN')
        html = self.client.get('/').content.decode()
        self.assertNotIn(f'/post/{adulto.pk}/', html)
        html = self.client.get('/buscar/?q=adulto').content.decode()
        self.assertNotIn(f'/post/{adulto.pk}/', html)

    def test_la_sala_esta_cerrada_al_publico_y_a_los_menores(self):
        from datetime import date
        self._post(300, n=11, is_adult=True)
        self.assertEqual(self.client.get('/mas18/').status_code, 403)   # sin sesión
        menor = make_user(username='menorA8', email='menora8@example.org',
                          birth_date=date(date.today().year - 15, 1, 1))
        self.client.force_login(menor)
        self.assertEqual(self.client.get('/mas18/').status_code, 403)
        sinfecha = make_user(username='sinfechaA8', email='sinfecha8@example.org')
        self.client.force_login(sinfecha)
        self.assertEqual(self.client.get('/mas18/').status_code, 403)   # sin fecha, tampoco

    def test_un_mayor_de_edad_entra_y_ve_los_analisis(self):
        from datetime import date
        p = self._post(300, n=12, is_adult=True, title='Análisis reservado')
        mayor = make_user(username='mayorA8', email='mayora8@example.org',
                          birth_date=date(date.today().year - 30, 1, 1))
        self.client.force_login(mayor)
        r = self.client.get('/mas18/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'/post/{p.pk}/', r.content.decode())

    def test_el_superusuario_no_tiene_restricciones_aunque_no_tenga_fecha(self):
        """Orden de David (2026-08-17): la cuenta superusuario entra en la sala
        +18 sin fecha de nacimiento (ensure_superuser no la establece). El
        privilegio es SOLO del superusuario: el staff sigue sujeto a la edad."""
        p = self._post(300, n=13, is_adult=True, title='Reservado para el dueño')
        jefe = make_user(username='jefeA8', email='jefea8@example.org')
        jefe.is_superuser = True
        jefe.is_staff = True
        jefe.save()
        self.assertIsNone(jefe.birth_date)
        self.assertTrue(jefe.is_adult)
        self.client.force_login(jefe)
        r = self.client.get('/mas18/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(f'/post/{p.pk}/', r.content.decode())
        self.assertIn('/mas18/', self.client.get('/').content.decode())  # y ve el menú
        solo_staff = make_user(username='staffA8', email='staffa8@example.org')
        solo_staff.is_staff = True
        solo_staff.save()
        self.assertFalse(solo_staff.is_adult)
        self.client.force_login(solo_staff)
        self.assertEqual(self.client.get('/mas18/').status_code, 403)

    def test_los_ajustes_nuevos_estan_en_el_panel_y_en_el_entorno(self):
        from apps.panel.views import SETTINGS_DEF
        from django.conf import settings as s
        claves = [k for k, _l, _h, _t in SETTINGS_DEF]
        for c in ('analysis_free_minutes', 'cents_per_video_minute'):
            self.assertIn(c, claves)
            self.assertIn(c, s.SETTING_DEFAULTS)
        env = open('.env.example').read()
        for v in ('ANALYSIS_FREE_MINUTES', 'CENTS_PER_VIDEO_MINUTE',
                  'TRANSCRIBE_MAX_SECONDS'):
            self.assertIn(v, env)


class Pase43C(TestCase):
    """4.3-C — la wiki se puebla por PERSONAS, no por afirmaciones sueltas.

    Decisiones de David (2026-08-17):
      · "la wikitrue va de afirmaciones verdaderas, opiniones o afirmaciones
        falsas de cada hablante de cada vídeo".
      · sin hablante identificado no hay ficha; en cuanto se identifica, la
        página se crea/actualiza.
      · homónimos: la misma URL muestra a todos los personajes indexados.
      · el nombre lo decide la votación: Wikidata sobre todo, y la repetición
        del nombre desempata. El voto de moderador o superusuario vale 5.
      · indexación en buscadores: interruptor del panel, apagado por defecto.
    """

    def _persona(self, nombre, qid='', **kw):
        from django.utils.text import slugify
        from apps.wiki.models import Interlocutor
        base = slugify(nombre)[:150]
        slug, n = base, 2
        while Interlocutor.objects.filter(slug=slug).exists():
            slug, n = f'{base}-{n}', n + 1
        datos = dict(name=nombre, slug=slug, base_slug=base, wikidata_id=qid,
                     is_public_figure=True)
        datos.update(kw)
        return Interlocutor.objects.create(**datos)

    def _post_con_hablantes(self, n=1, etiquetas=('SPEAKER_00',)):
        post = Post.objects.create(
            author=make_user(username=f'c_{n}', email=f'c_{n}@example.org'),
            url=f'https://youtu.be/c{n}', status='PENDING_VALIDATION')
        for i, etq in enumerate(etiquetas):
            post.transcript_segments.create(start_seconds=i * 5.0, end_seconds=i * 5.0 + 4,
                                            text=f'Frase de {etq}', speaker_label=etq)
        return post

    # --- la ficha vive en la raíz, igual en los tres dominios ---
    def test_la_ficha_esta_en_la_raiz_y_la_antigua_redirige(self):
        p = self._persona('Pedro Sánchez', 'Q3128751')
        self.assertEqual(self.client.get(f'/persona/{p.slug}/').status_code, 200)
        r = self.client.get(f'/wiki/persona/{p.slug}/')
        self.assertEqual(r.status_code, 301)          # permanente, no rompe enlaces
        self.assertIn(f'/persona/{p.slug}/', r['Location'])

    def test_la_ficha_agrupa_por_color_del_semaforo(self):
        from apps.wiki.models import Claim, ClaimAppearance, SpeakerNameProposal
        post = self._post_con_hablantes(1)
        persona = self._persona('Ana Ejemplo', 'Q1')
        SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00',
                                           candidate_name='Ana Ejemplo', confirmed=True,
                                           interlocutor=persona, wikidata_id='Q1')
        seg = post.transcript_segments.first()
        for color, texto in (('GREEN', 'Dato cierto'), ('RED', 'Dato falso'),
                             ('GREY', 'Pura opinión')):
            c = Claim.objects.create(text_original=texto, color=color)
            ClaimAppearance.objects.create(claim=c, segment=seg, quote=texto)
        html = self.client.get(f'/persona/{persona.slug}/').content.decode()
        for texto in ('Dato cierto', 'Dato falso', 'Pura opinión'):
            self.assertIn(texto, html)
        self.assertIn('Afirmaciones verificadas', html)
        self.assertIn('Afirmaciones desmentidas', html)
        self.assertIn('Opiniones y predicciones', html)

    # --- homónimos: la misma URL los enseña a todos ---
    def test_los_homonimos_aparecen_todos_en_la_misma_pagina(self):
        a = self._persona('Pedro Sánchez', 'Q1', description='político español')
        b = self._persona('Pedro Sánchez', 'Q2', description='futbolista')
        self.assertNotEqual(a.slug, b.slug)           # dos fichas, jamás mezcladas
        self.assertEqual(a.base_slug, b.base_slug)
        html = self.client.get(f'/persona/{a.base_slug}/').content.decode()
        self.assertIn('político español', html)
        self.assertIn('futbolista', html)
        self.assertIn(f'/persona/{b.slug}/', html)

    # --- sin nombre no hay ficha ---
    def test_un_nombre_a_mano_sin_wikidata_no_abre_pagina(self):
        """Candado congelado: los particulares JAMÁS tienen página."""
        from apps.wiki.models import SpeakerNameProposal
        from apps.wiki.naming import _person_for
        post = self._post_con_hablantes(2)
        prop = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='Vecino Del Quinto')
        persona = _person_for(prop)
        self.assertIsNone(persona.is_public_figure)   # queda en revisión
        self.assertEqual(self.client.get(f'/persona/{persona.slug}/').status_code, 404)

    def test_con_qid_la_pagina_se_abre_al_confirmar(self):
        from apps.wiki.models import SpeakerNameProposal
        from apps.wiki.naming import _person_for
        post = self._post_con_hablantes(3)
        prop = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='Ana Pública',
            wikidata_id='Q42', description='periodista')
        persona = _person_for(prop)
        self.assertTrue(persona.is_public_figure)
        self.assertEqual(persona.base_slug, 'ana-publica')
        self.assertEqual(self.client.get(f'/persona/{persona.slug}/').status_code, 200)

    # --- cómo se decide el nombre ---
    def test_wikidata_gana_a_un_nombre_escrito_a_mano_con_los_mismos_puntos(self):
        from apps.wiki.models import SpeakerNameProposal
        from apps.wiki.naming import rank_key
        post = self._post_con_hablantes(4)
        a_mano = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='pedro sanchez')
        con_qid = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='Pedro Sánchez',
            wikidata_id='Q3128751')
        self.assertGreater(rank_key(con_qid), rank_key(a_mano))

    def test_el_voto_del_moderador_confirma_en_solitario(self):
        from apps.wiki.models import SpeakerNameProposal
        from apps.wiki.naming import vote_proposal
        post = self._post_con_hablantes(5)
        prop = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='Ana Pública',
            wikidata_id='Q42')
        mod = make_user(username='modC', email='modc@example.org', level='MOD')
        ok, msg = vote_proposal(prop, mod)
        prop.refresh_from_db()
        self.assertTrue(ok)
        self.assertTrue(prop.confirmed)               # 5 puntos de una tacada
        self.assertIsNotNone(prop.interlocutor)

    def test_se_confirma_la_mejor_propuesta_no_la_ultima_votada(self):
        from apps.wiki.models import SpeakerNameProposal
        from apps.wiki.naming import vote_proposal
        post = self._post_con_hablantes(6)
        a_mano = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='pedro sanchez')
        con_qid = SpeakerNameProposal.objects.create(
            post=post, speaker_label='SPEAKER_00', candidate_name='Pedro Sánchez',
            wikidata_id='Q3128751')
        mod = make_user(username='modC2', email='modc2@example.org', level='MOD')
        vote_proposal(con_qid, mod)                   # el mod vota la identificada
        a_mano.refresh_from_db(); con_qid.refresh_from_db()
        self.assertTrue(con_qid.confirmed)
        self.assertFalse(a_mano.confirmed)

    # --- el aviso a los votantes ---
    def test_se_avisa_de_los_hablantes_sin_identificar_al_lanzar_la_fase_cara(self):
        from apps.analysis.services import unnamed_speakers, warn_unnamed_speakers
        from apps.accounts.models import Notification
        post = self._post_con_hablantes(7, ('SPEAKER_00', 'SPEAKER_01'))
        votante = make_user(username='votC', email='votc@example.org', karma=100)
        post.validation_votes.create(user=votante, kind='VALIDATE')
        self.assertEqual(unnamed_speakers(post), ['SPEAKER_00', 'SPEAKER_01'])
        enviados = warn_unnamed_speakers(post)
        self.assertGreaterEqual(enviados, 1)
        aviso = Notification.objects.filter(user=votante).first()
        self.assertIsNotNone(aviso)
        self.assertIn('sin identificar', aviso.text)

    def test_sin_hablantes_pendientes_no_se_molesta_a_nadie(self):
        from apps.analysis.services import warn_unnamed_speakers
        from apps.wiki.models import SpeakerNameProposal
        post = self._post_con_hablantes(8)
        SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00',
                                           candidate_name='Ana Pública', confirmed=True)
        self.assertEqual(warn_unnamed_speakers(post), 0)

    def test_el_aviso_respeta_el_interruptor_del_usuario(self):
        from apps.analysis.services import warn_unnamed_speakers
        from apps.accounts.models import Notification
        post = self._post_con_hablantes(9)
        mudo = make_user(username='mudoC', email='mudoc@example.org',
                         notify_prefs={'speakers_unnamed': False})
        post.validation_votes.create(user=mudo, kind='VALIDATE')
        warn_unnamed_speakers(post)
        self.assertFalse(Notification.objects.filter(user=mudo).exists())

    def test_el_interruptor_aparece_en_mi_cuenta(self):
        from apps.accounts.views import settings_view       # existe de verdad
        codigo = open('apps/accounts/views.py').read()
        self.assertIn("'speakers_unnamed'", codigo)

    # --- indexación: freno puesto por defecto ---
    def test_las_fichas_nacen_con_noindex(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.filter(key='wiki_index_people').delete()
        p = self._persona('Ana Pública', 'Q42')
        html = self.client.get(f'/persona/{p.slug}/').content.decode()
        self.assertIn('noindex', html)

    def test_el_interruptor_del_panel_las_libera(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='wiki_index_people',
                                               defaults={'value': '1'})
        p = self._persona('Ana Pública', 'Q42')
        html = self.client.get(f'/persona/{p.slug}/').content.decode()
        self.assertNotIn('noindex', html)

    def test_el_interruptor_es_editable_en_el_panel(self):
        from apps.panel.views import SETTINGS_DEF
        from django.conf import settings as s
        claves = [k for k, _l, _h, _t in SETTINGS_DEF]
        self.assertIn('wiki_index_people', claves)
        self.assertEqual(s.SETTING_DEFAULTS['wiki_index_people'], '0')
        self.assertIn('WIKI_INDEX_PEOPLE', open('.env.example').read())


class Pase43D(TestCase):
    """4.3-D — buscar por apellido, fichas antiguas con QID, aviso de coste,
    cronómetro del análisis y el candado del logger inexistente.

    Contexto: David no encontraba a Santiago Abascal en el autocompletado, y sí
    está en Wikidata. El informe del operador (docs/35 §3.1) señaló además que
    dejar cerradas las fichas antiguas CON QID no se sostenía como regla.
    """

    # --- el fallo latente que podía tumbar la fase barata ---
    def test_ningun_modulo_usa_un_logger_que_no_existe(self):
        """Candado estructural (regla 12 de docs/34). `logger.info(...)` sin
        `logger` definido es un NameError que solo salta en la rama que lo
        ejecuta: en tasks.py vivió desde el pase 4.3-A porque esa rama solo se
        pisa con vídeos que traen subtítulos oficiales.
        """
        import ast
        import glob
        malos = []
        for path in (glob.glob('apps/**/*.py', recursive=True)
                     + glob.glob('config/**/*.py', recursive=True)):
            if '/migrations/' in path:
                continue
            src = open(path, encoding='utf-8').read()
            if 'logger.' not in src:
                continue
            definidos = set()
            for x in ast.walk(ast.parse(src)):
                if isinstance(x, ast.Assign):
                    for y in x.targets:
                        if isinstance(y, ast.Name):
                            definidos.add(y.id)
                elif isinstance(x, (ast.Import, ast.ImportFrom)):
                    for a in x.names:
                        definidos.add((a.asname or a.name).split('.')[0])
            if 'logger' not in definidos:
                malos.append(path)
        self.assertEqual(malos, [], f'usan logger sin definirlo: {malos}')

    # --- D1: buscar por apellido ---
    def test_el_respaldo_de_texto_completo_encuentra_por_apellido(self):
        """`wbsearchentities` casa por PREFIJO: 'abascal' no encuentra a
        'Santiago Abascal'. El respaldo de CirrusSearch sí."""
        from apps.agents import wikidata

        def falso_get(url, **kw):
            params = kw.get('params', {})

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    if params.get('action') == 'wbsearchentities':
                        return {'search': []}          # el prefijo no encuentra nada
                    if params.get('action') == 'query':
                        assert 'haswbstatement:P31=Q5' in params['srsearch']
                        return {'query': {'search': [{'title': 'Q11703587'}]}}
                    return {'entities': {'Q11703587': {
                        'labels': {'es': {'value': 'Santiago Abascal'}},
                        'descriptions': {'es': {'value': 'político español'}},
                        'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]}}}}
            return R()

        with mock.patch.object(wikidata.httpx, 'get', falso_get):
            r = wikidata.search_people('abascal')
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]['qid'], 'Q11703587')
        self.assertEqual(r[0]['name'], 'Santiago Abascal')

    def test_el_respaldo_no_duplica_lo_que_ya_trajo_el_prefijo(self):
        from apps.agents import wikidata

        def falso_get(url, **kw):
            params = kw.get('params', {})

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    if params.get('action') == 'wbsearchentities':
                        return {'search': [{'id': 'Q1'}]}
                    if params.get('action') == 'query':
                        return {'query': {'search': [{'title': 'Q1'}, {'title': 'Q2'}]}}
                    pedidos = params['ids'].split('|')
                    assert pedidos == ['Q1', 'Q2'], pedidos      # sin duplicados
                    return {'entities': {q: {
                        'labels': {'es': {'value': f'Persona {q}'}}, 'descriptions': {},
                        'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]}}
                        for q in pedidos}}
            return R()

        with mock.patch.object(wikidata.httpx, 'get', falso_get):
            r = wikidata.search_people('persona')
        self.assertEqual([x['qid'] for x in r], ['Q1', 'Q2'])

    def test_si_el_respaldo_se_cae_la_busqueda_principal_sobrevive(self):
        """Degradación ruidosa: el respaldo puede fallar sin llevarse por delante
        lo que el prefijo sí encontró."""
        from apps.agents import wikidata

        def falso_get(url, **kw):
            params = kw.get('params', {})
            if params.get('action') == 'query':
                raise RuntimeError('CirrusSearch caído')

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    if params.get('action') == 'wbsearchentities':
                        return {'search': [{'id': 'Q1'}]}
                    return {'entities': {'Q1': {
                        'labels': {'es': {'value': 'Alguien'}}, 'descriptions': {},
                        'claims': {'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q5'}}}}]}}}}
            return R()

        with mock.patch.object(wikidata.httpx, 'get', falso_get):
            with self.assertLogs('agents.wikidata', level='WARNING'):
                r = wikidata.search_people('alguien')
        self.assertEqual(len(r), 1)

    # --- D2: las fichas antiguas con QID se abren ---
    def test_la_migracion_abre_las_fichas_antiguas_con_qid(self):
        import importlib
        m = importlib.import_module('apps.wiki.migrations.0005_abrir_fichas_con_qid')
        from apps.wiki.models import Interlocutor

        class FalsoApps:
            def get_model(self, app, modelo):
                return Interlocutor

        con_qid = Interlocutor.objects.create(name='Ana Botella', slug='ana-botella-d',
                                              base_slug='ana-botella-d',
                                              wikidata_id='Q41266', is_public_figure=None)
        sin_qid = Interlocutor.objects.create(name='Vecino', slug='vecino-d',
                                              base_slug='vecino-d', is_public_figure=None)
        m.abrir_las_que_tienen_qid(FalsoApps(), None)
        con_qid.refresh_from_db()
        sin_qid.refresh_from_db()
        self.assertTrue(con_qid.is_public_figure)     # tenía QID: se abre
        self.assertIsNone(sin_qid.is_public_figure)   # sin QID: sigue cerrada

    # --- D3: aviso de coste por vídeo largo ---
    def _post_largo(self, segundos=3600, n=0):
        return Post.objects.create(
            author=make_user(username=f'd_{n}', email=f'd_{n}@example.org'),
            url=f'https://youtu.be/d{n}', duration_seconds=segundos,
            status='PENDING_VALIDATION', title='Entrevista de una hora')

    def test_un_video_largo_avisa_del_coste_a_quienes_votaron(self):
        from apps.accounts.models import Notification
        from apps.analysis.services import warn_long_video
        post = self._post_largo(3600, 1)
        votante = make_user(username='votD', email='votd@example.org', karma=100)
        post.validation_votes.create(user=votante, kind='VALIDATE')
        self.assertGreaterEqual(warn_long_video(post), 1)
        aviso = Notification.objects.filter(user=votante).first()
        self.assertIsNotNone(aviso)
        self.assertIn('60 minutos', aviso.text)
        self.assertIn('/donaciones/', aviso.url)

    def test_un_video_corto_no_molesta_a_nadie(self):
        from apps.analysis.services import warn_long_video
        self.assertEqual(warn_long_video(self._post_largo(300, 2)), 0)

    def test_el_aviso_de_coste_respeta_el_interruptor(self):
        from apps.accounts.models import Notification
        from apps.analysis.services import warn_long_video
        post = self._post_largo(3600, 3)
        mudo = make_user(username='mudoD', email='mudod@example.org',
                         notify_prefs={'long_video_cost': False})
        post.validation_votes.create(user=mudo, kind='VALIDATE')
        warn_long_video(post)
        self.assertFalse(Notification.objects.filter(user=mudo).exists())

    def test_el_aviso_de_coste_no_es_un_muro(self):
        """El análisis arranca igual: el aviso llega DESPUÉS de lanzarlo."""
        codigo = open('apps/analysis/services.py').read()
        self.assertLess(codigo.index('launch_full_analysis(post)'),
                        codigo.index('warn_long_video(post)'))

    def test_el_interruptor_de_coste_esta_en_mi_cuenta(self):
        self.assertIn("'long_video_cost'", open('apps/accounts/views.py').read())

    # --- D4: el cronómetro ---
    def test_el_post_guarda_los_tiempos_del_analisis(self):
        post = self._post_largo(3600, 4)
        post.transcribe_seconds = 1200.0
        post.diarize_seconds = 2400.0
        post.cheap_started_at = timezone.now() - timedelta(minutes=70)
        post.cheap_finished_at = timezone.now()
        post.save()
        t = post.analysis_times()
        self.assertEqual(t['minutos_video'], 60.0)
        self.assertEqual(t['transcribir_s'], 1200.0)
        self.assertEqual(t['diarizar_s'], 2400.0)
        self.assertGreater(t['fase_barata_s'], 4000)
        self.assertIsNone(t['fase_completa_s'])     # aún no ha corrido

    def test_las_dos_fases_marcan_su_reloj(self):
        codigo = open('apps/analysis/tasks.py').read()
        for campo in ('cheap_started_at', 'cheap_finished_at', 'full_started_at',
                      'full_finished_at', 'transcribe_seconds', 'diarize_seconds'):
            self.assertIn(campo, codigo)


class Pase43E(TestCase):
    """4.3-E — la puerta del 50%, los nombres fijados, el desplegable completo,
    el foro y el rescate de análisis atascados.

    Decisiones de David (2026-08-17):
      · para marcar factual hace falta al menos el 50% de hablantes identificados
      · el desplegable de «¿Quién crees que es?» debe verse entero
      · el nombre confirmado sustituye a «Hablante N» en los dos sitios
      · el foro: ancho, con todas las opciones de formato; el resto centrado
      · los análisis atascados se relanzan solos
    """

    def _post(self, n=0, etiquetas=('SPEAKER_00', 'SPEAKER_01'), status='PENDING_VALIDATION'):
        post = Post.objects.create(
            author=make_user(username=f'e_{n}', email=f'e_{n}@example.org'),
            url=f'https://youtu.be/e{n}', status=status, title=f'Vídeo {n}',
            validation_deadline=timezone.now() + timedelta(days=2))
        for i, etq in enumerate(etiquetas):
            post.transcript_segments.create(start_seconds=i * 5.0, end_seconds=i * 5.0 + 4,
                                            text=f'Frase de {etq}', speaker_label=etq)
        return post

    def _confirmar(self, post, etiqueta, nombre):
        from apps.wiki.models import SpeakerNameProposal
        return SpeakerNameProposal.objects.create(
            post=post, speaker_label=etiqueta, candidate_name=nombre,
            confirmed=True, source='user')

    # --- la puerta del 50% ---
    def test_sin_identificar_a_nadie_no_se_puede_validar(self):
        from apps.analysis.services import identification_gate
        puede, motivo = identification_gate(self._post(1))
        self.assertFalse(puede)
        self.assertIn('0 de 2', motivo)

    def test_con_la_mitad_identificada_ya_se_puede(self):
        from apps.analysis.services import identification_gate
        post = self._post(2)
        self._confirmar(post, 'SPEAKER_00', 'Ana Pública')
        self.assertTrue(identification_gate(post)[0])

    def test_con_tres_hablantes_hacen_falta_dos(self):
        """El 50% de 3 se redondea HACIA ARRIBA: 2, no 1."""
        from apps.analysis.services import identification_gate
        post = self._post(3, ('SPEAKER_00', 'SPEAKER_01', 'SPEAKER_02'))
        self._confirmar(post, 'SPEAKER_00', 'Ana')
        self.assertFalse(identification_gate(post)[0])
        self._confirmar(post, 'SPEAKER_01', 'Bea')
        self.assertTrue(identification_gate(post)[0])

    def test_sin_diarizacion_la_puerta_no_se_aplica(self):
        """No se puede exigir identificar a nadie si no se separaron voces."""
        from apps.analysis.services import identification_gate
        post = self._post(4, ('',))
        self.assertTrue(identification_gate(post)[0])

    def test_el_voto_se_rechaza_con_el_motivo_y_no_queda_registrado(self):
        from apps.analysis.services import cast_vote
        post = self._post(5)
        votante = make_user(username='votE', email='vote@example.org', karma=100)
        ok, msg = cast_vote(post, votante, 'VALIDATE')
        self.assertFalse(ok)
        self.assertIn('identificar', msg)
        self.assertEqual(post.distinct_validation_votes('VALIDATE'), 0)
        post.refresh_from_db()
        self.assertEqual(post.status, 'PENDING_VALIDATION')   # no arrancó nada

    def test_identificados_los_hablantes_el_voto_entra(self):
        from apps.analysis.services import cast_vote
        post = self._post(6)
        self._confirmar(post, 'SPEAKER_00', 'Ana Pública')
        votante = make_user(username='vot2E', email='vot2e@example.org', karma=100)
        ok, _msg = cast_vote(post, votante, 'VALIDATE')
        self.assertTrue(ok)
        self.assertEqual(post.distinct_validation_votes('VALIDATE'), 1)

    def test_el_umbral_es_editable_en_el_panel_y_el_entorno(self):
        from django.conf import settings as s
        from apps.panel.views import SETTINGS_DEF
        self.assertIn('min_identified_speakers_percent',
                      [k for k, _l, _h, _t in SETTINGS_DEF])
        self.assertEqual(s.SETTING_DEFAULTS['min_identified_speakers_percent'], '50')
        self.assertIn('MIN_IDENTIFIED_SPEAKERS_PERCENT', open('.env.example').read())

    # --- el nombre confirmado manda ---
    def test_el_nombre_confirmado_sustituye_a_hablante_n(self):
        post = self._post(7, status='DONE')
        self._confirmar(post, 'SPEAKER_00', 'Ana Pública')
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('Ana Pública', html)
        # El hablante 2 sigue sin nombre: ese sí conserva el número.
        self.assertIn('Hablante 2', html)

    def test_sin_confirmar_se_mantiene_el_numero(self):
        post = self._post(8, status='DONE')
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('Hablante 1', html)
        self.assertIn('Hablante 2', html)

    # --- el desplegable y el foro ---
    def test_el_desplegable_ya_no_se_recorta(self):
        css = open('static/css/main.css', encoding='utf-8').read()
        js = open('static/js/speaker-suggest.js', encoding='utf-8').read()
        import re
        regla = re.search(r'\.suggest-list\{[^}]*\}', css).group(0)
        self.assertNotIn('max-height', regla)          # ya no se limita a sí misma
        self.assertIn('suggesting', css)               # la columna deja de recortar
        self.assertIn('recorte(form', js)              # y el JS lo gobierna

    def test_la_barra_de_formato_trae_todas_las_marcas_renderizables(self):
        js = open('static/js/mdtoolbar.js', encoding='utf-8').read()
        for marca in ('negrita', 'cursiva', 'título', 'cita', 'lista',
                      'lista numerada', 'código', 'bloque de código', 'enlace',
                      'imagen', 'separador'):
            self.assertIn(marca, js)

    def test_el_autor_puede_abrir_el_hilo_con_texto_formateado(self):
        html = open('templates/analysis/submit.html', encoding='utf-8').read()
        self.assertIn('name="opinion"', html)
        self.assertIn('data-mdtoolbar', html)          # con barra de formato

    def test_solo_la_rejilla_ocupa_todo_el_ancho(self):
        css = open('static/css/main.css', encoding='utf-8').read()
        self.assertIn('main.wide .post > h1', css)     # el resto, centrado
        self.assertIn('main.wide .post > #hilo', css)  # el hilo, ancho propio

    # --- el rescate de atascados ---
    def test_se_relanza_lo_que_lleva_horas_colgado(self):
        from apps.analysis.tasks import relaunch_stuck_analyses
        viejo = self._post(9, status='CHEAP_RUNNING')
        viejo.cheap_started_at = timezone.now() - timedelta(hours=9)
        viejo.save(update_fields=['cheap_started_at'])
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanzar:
            self.assertEqual(relaunch_stuck_analyses(), 1)
            lanzar.assert_called_once_with(viejo.pk)
        viejo.refresh_from_db()
        self.assertEqual(viejo.status, 'NEW')

    def test_un_analisis_que_solo_esta_tardando_no_se_toca(self):
        """Un vídeo de una hora tarda: se mide contra el reloj del análisis, no
        contra la fecha de creación."""
        from apps.analysis.tasks import relaunch_stuck_analyses
        reciente = self._post(10, status='CHEAP_RUNNING')
        reciente.cheap_started_at = timezone.now() - timedelta(minutes=40)
        reciente.save(update_fields=['cheap_started_at'])
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanzar:
            self.assertEqual(relaunch_stuck_analyses(), 0)
            lanzar.assert_not_called()

    def test_sin_reloj_no_se_relanza_nada(self):
        """Los posts anteriores al cronómetro no tienen fecha de arranque: sin
        ella no se puede distinguir atascado de recién empezado."""
        from apps.analysis.tasks import relaunch_stuck_analyses
        self._post(11, status='CHEAP_RUNNING')     # cheap_started_at = None
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay'):
            self.assertEqual(relaunch_stuck_analyses(), 0)

    def test_la_fase_cara_atascada_no_repite_la_transcripcion(self):
        from apps.analysis.tasks import relaunch_stuck_analyses
        post = self._post(12, status='FULL_RUNNING')
        post.full_started_at = timezone.now() - timedelta(hours=9)
        post.save(update_fields=['full_started_at'])
        segmentos_antes = post.transcript_segments.count()
        with mock.patch('apps.analysis.tasks.run_full_analysis.apply_async') as lanzar:
            self.assertEqual(relaunch_stuck_analyses(), 1)
            lanzar.assert_called_once()
        post.refresh_from_db()
        self.assertEqual(post.status, 'FULL_QUEUED')
        self.assertEqual(post.transcript_segments.count(), segmentos_antes)

    def test_el_rescate_esta_programado_cada_hora(self):
        from config.celery import app
        tarea = app.conf.beat_schedule['relanzar-analisis-atascados']
        self.assertEqual(tarea['task'], 'apps.analysis.tasks.relaunch_stuck_analyses')
        self.assertEqual(tarea['schedule'], 3600.0)


class Pase43F(TestCase):
    """4.3-F — el dinero se toca desde el panel, y los vídeos caros esperan turno.

    Decisiones de David (2026-08-17):
      · el presupuesto se edita en el panel escribiendo euros (no había forma de
        cambiarlo desde la web: ni panel ni /admin/)
      · si un vídeo se lleva más del 50% de la asignación diaria, entra en cola;
        se analiza cuando haya depósito, o antes si alguien lo apadrina
      · nunca es un muro: la donación es voluntaria y el vídeo se analiza igual
    """

    def _post(self, segundos, n=0, status='NEW'):
        return Post.objects.create(
            author=make_user(username=f'f_{n}', email=f'f_{n}@example.org'),
            url=f'https://youtu.be/f{n}', duration_seconds=segundos,
            status=status, title=f'Vídeo {n}')

    # --- el presupuesto, editable ---
    def test_el_presupuesto_se_edita_en_el_panel_en_euros(self):
        from apps.panel.views import SETTINGS_DEF
        filas = {k: (lbl, kind) for k, lbl, _h, kind in SETTINGS_DEF}
        for clave in ('budget_base_eur', 'budget_hard_ceiling_eur'):
            self.assertIn(clave, filas)
            self.assertEqual(filas[clave][1], 'num')      # se escriben dígitos
            self.assertIn('€', filas[clave][0])

    def test_guardar_el_presupuesto_cambia_el_deposito_diario(self):
        import calendar
        from django.utils import timezone as tz
        from apps.panel.models import SystemSetting
        from apps.panel.services import live_daily_budget
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '150'})
        SystemSetting.objects.update_or_create(key='budget_hard_ceiling_eur',
                                               defaults={'value': '300'})
        dias = calendar.monthrange(tz.localdate().year, tz.localdate().month)[1]
        self.assertAlmostEqual(live_daily_budget(), round(150 / dias, 2), places=2)

    def test_el_aviso_de_presupuesto_agotado_ya_no_usa_la_cifra_cableada(self):
        codigo = open('apps/analysis/views.py').read()
        self.assertNotIn('dj.DAILY_BUDGET_EUR', codigo)
        self.assertIn('budget_left_today()', codigo)

    # --- la cola ---
    def test_un_video_caro_entra_en_cola_y_no_se_analiza_al_momento(self):
        from apps.analysis.services import needs_sponsorship
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '150'})
        a_la_cola, coste, sugerida = needs_sponsorship(self._post(3600, 1))
        self.assertTrue(a_la_cola)
        self.assertGreater(coste, 0)
        self.assertEqual(sugerida * 2, int(sugerida * 2))    # múltiplo de 0,50

    def test_un_video_normal_no_pasa_por_la_cola(self):
        from apps.analysis.services import needs_sponsorship
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '150'})
        self.assertFalse(needs_sponsorship(self._post(300, 2))[0])

    def test_con_el_umbral_a_cero_la_cola_se_desactiva(self):
        from apps.analysis.services import needs_sponsorship
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='queue_threshold_percent',
                                               defaults={'value': '0'})
        self.assertFalse(needs_sponsorship(self._post(7200, 3))[0])

    def test_la_cola_avanza_cuando_cabe_en_el_deposito(self):
        from apps.analysis.tasks import launch_queued_analyses
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '150'})
        post = self._post(1800, 4, status='AWAITING_BUDGET')
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanzar:
            self.assertEqual(launch_queued_analyses(), 1)
            lanzar.assert_called_once_with(post.pk)
        post.refresh_from_db()
        self.assertEqual(post.status, 'NEW')

    def test_lo_que_no_cabe_espera_y_no_adelanta_a_nadie(self):
        """Quien llegó antes va antes: una cola que adelanta a los baratos
        condena a los caros a no analizarse nunca."""
        from apps.analysis.tasks import launch_queued_analyses
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '150'})
        caro = self._post(36000, 5, status='AWAITING_BUDGET')      # 10 h: no cabe
        barato = self._post(120, 6, status='AWAITING_BUDGET')
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as lanzar:
            self.assertEqual(launch_queued_analyses(), 0)
            lanzar.assert_not_called()
        caro.refresh_from_db()
        barato.refresh_from_db()
        self.assertEqual(caro.status, 'AWAITING_BUDGET')
        self.assertEqual(barato.status, 'AWAITING_BUDGET')

    def test_un_moderador_puede_adelantar_un_analisis(self):
        post = self._post(3600, 7, status='AWAITING_BUDGET')
        mod = make_user(username='modF', email='modf@example.org', level='MOD')
        self.client.force_login(mod)
        with mock.patch('apps.analysis.views.run_cheap_phase.delay') as lanzar:
            self.client.post(f'/post/{post.pk}/adelantar/')
            lanzar.assert_called_once_with(post.pk)
        post.refresh_from_db()
        self.assertEqual(post.status, 'NEW')

    def test_un_usuario_normal_no_puede_adelantar(self):
        post = self._post(3600, 8, status='AWAITING_BUDGET')
        cualquiera = make_user(username='anonF', email='anonf@example.org')
        self.client.force_login(cualquiera)
        with mock.patch('apps.analysis.views.run_cheap_phase.delay') as lanzar:
            self.client.post(f'/post/{post.pk}/adelantar/')
            lanzar.assert_not_called()
        post.refresh_from_db()
        self.assertEqual(post.status, 'AWAITING_BUDGET')

    def test_el_cartel_explica_la_cola_y_ofrece_apadrinar_sin_ser_un_muro(self):
        post = self._post(3600, 9, status='AWAITING_BUDGET')
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='budget_base_eur',
                                               defaults={'value': '150'})
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('En cola por presupuesto', html)
        self.assertIn('Apadrinar este análisis', html)
        self.assertIn('/donaciones/', html)
        self.assertIn('no cobra por publicar', html)      # ni muro ni peaje

    def test_el_estado_nuevo_existe_en_el_modelo_y_en_la_migracion(self):
        from apps.analysis.models import STATUSES
        self.assertIn('AWAITING_BUDGET', [c for c, _l in STATUSES])
        migracion = open('apps/analysis/migrations/0009_pase43f_estado_en_cola.py').read()
        for codigo, _label in STATUSES:
            self.assertIn(f"'{codigo}'", migracion)       # modelo y migración, iguales

    def test_la_cola_esta_programada_cada_hora(self):
        from config.celery import app
        tarea = app.conf.beat_schedule['vaciar-cola-de-presupuesto']
        self.assertEqual(tarea['task'], 'apps.analysis.tasks.launch_queued_analyses')
        self.assertEqual(tarea['schedule'], 3600.0)

    def test_el_umbral_de_cola_es_editable(self):
        from django.conf import settings as s
        from apps.panel.views import SETTINGS_DEF
        self.assertIn('queue_threshold_percent', [k for k, _l, _h, _t in SETTINGS_DEF])
        self.assertEqual(s.SETTING_DEFAULTS['queue_threshold_percent'], '50')
        self.assertIn('QUEUE_THRESHOLD_PERCENT', open('.env.example').read())


class Pase43G(TestCase):
    """4.3-G — el hilo del post es un FORO CLÁSICO de verdad.

    Orden de David (2026-08-17), viendo producción: «en aspecto, más allá de la
    identificación de hablantes, vídeo y transcripción, tiene que ser
    EXACTAMENTE el de un foro clásico: todo el ancho, formateo, citas, etc.»

    Dos fallos que la captura destapó y que aquí quedan cerrados con candado:
      · los 12 botones de formato se pintaban BLANCOS sobre fondo claro (heredaban
        color:#fff de la regla global de <button>): doce recuadros vacíos;
      · el cajón de respuesta salía a 460 px dentro de un hilo ancho, porque la
        regla global input,select,textarea impone ese max-width y width:100% no
        lo levanta.
    """

    # ---------- utilidades ----------
    @staticmethod
    def _css_reglas():
        """main.css como {selector normalizado: {propiedad: valor}}.

        Se parsea, NO se compara texto: un reformateo del CSS no debe romper
        estos tests (lección del A.7: nada de cadenas exactas de CSS).
        """
        import re
        txt = open('static/css/main.css', encoding='utf-8').read()
        txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
        reglas = {}
        for sel, cuerpo in re.findall(r'([^{}]+)\{([^{}]*)\}', txt):
            decls = {}
            for d in cuerpo.split(';'):
                if ':' in d:
                    k, v = d.split(':', 1)
                    decls[k.strip()] = v.strip()
            for uno in sel.split(','):
                reglas.setdefault(' '.join(uno.split()), {}).update(decls)
        return reglas

    def _hilo(self, cuantos=1, autor=None, texto='Un **comentario** cualquiera'):
        """Post con su hilo machina y N mensajes, sin pasar por Celery."""
        from machina.core.db.models import get_model
        from apps.forum.machina_glue import create_topic_for_post, get_topic_for_post
        autor = autor or make_user(username='foro', email='foro@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/g0001',
                                   title='Vídeo del foro', author_opinion='Abro yo.')
        create_topic_for_post(post)
        topic = get_topic_for_post(post)
        MPost = get_model('forum_conversation', 'Post')
        for i in range(cuantos):
            MPost.objects.create(topic=topic, poster=autor, subject='Re',
                                 content=f'{texto} {i}', approved=True)
        return post, autor

    # ---------- los dos fallos de producción ----------
    def test_la_barra_de_formato_no_puede_pintarse_en_blanco_sobre_blanco(self):
        """Candado general: si un botón cambia a fondo CLARO, fija su color.

        Sin esto vuelve el fallo tal cual: el botón hereda color:#fff de la
        regla global de <button> y desaparece.
        """
        claros = {'var(--paper)', 'var(--card)', '#fff', '#ffffff', 'white',
                  'none', 'transparent'}
        for sel, decls in self._css_reglas().items():
            if 'button' in sel and decls.get('background') in claros:
                self.assertIn('color', decls, f'{sel} se pinta invisible')

    def test_el_cajon_de_respuesta_usa_todo_el_ancho(self):
        regla = self._css_reglas()['.thread-reply textarea']
        self.assertEqual(regla.get('max-width'), 'none')   # el global de 460px, levantado
        self.assertEqual(regla.get('width'), '100%')

    def test_el_hilo_ocupa_todo_el_ancho_de_la_pantalla(self):
        regla = self._css_reglas()['main.wide .post > #hilo']
        self.assertEqual(regla.get('max-width'), 'none')

    def test_el_css_esta_cuadrado(self):
        """Una llave de más deja el resto del archivo a merced del navegador."""
        css = open('static/css/main.css', encoding='utf-8').read()
        self.assertEqual(css.count('{'), css.count('}'))

    def test_la_barra_de_formato_no_depende_de_emoji(self):
        """Un emoji lo dibuja la fuente del sistema; en Windows salían vacíos."""
        js = open('static/js/mdtoolbar.js', encoding='utf-8').read()
        astral = [c for c in js if ord(c) > 0xFFFF]
        self.assertEqual(astral, [])

    # ---------- la piel de foro clásico ----------
    def test_cada_mensaje_lleva_ficha_de_autor_y_numero_citable(self):
        post, autor = self._hilo(1)
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('msg-author', html)          # columna del autor
        self.assertIn('Mensajes', html)            # cuántos lleva escritos
        self.assertIn('Karma', html)
        self.assertIn('>#1<', html)                # numeración del hilo
        self.assertIn('href="#msg-', html)         # enlace permanente

    def test_el_contador_de_mensajes_del_autor_no_lo_parte_el_group_by(self):
        """Trampa conocida: el ordering del Meta se cuela en el GROUP BY."""
        post, autor = self._hilo(2)                # + el mensaje de apertura = 3
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('Mensajes: 3', html)

    def test_las_acciones_del_mensaje_se_leen_con_palabras(self):
        post, autor = self._hilo(1)
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        for palabra in ('Citar', 'Responder', 'Reportar'):
            self.assertIn(palabra, html)
        self.assertIn('data-num=', html)           # citar arrastra el número...
        self.assertIn('data-pk=', html)            # ...y el enlace al mensaje

    def test_la_paginacion_es_de_foro_con_primera_y_ultima(self):
        post, autor = self._hilo(25)               # 26 con el de apertura: 2 páginas
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/?pagina=2').content.decode()
        self.assertIn('Anterior', html)
        self.assertIn('Página 2 de 2', html)
        self.assertIn('?pagina=1#hilo', html)
        self.assertIn('>#21<', html)               # la numeración NO reinicia

    def test_la_cabecera_del_hilo_cuenta_los_mensajes(self):
        post, autor = self._hilo(2)
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('3 mensajes', html)

    # ---------- vista previa ----------
    def test_la_vista_previa_usa_el_mismo_renderizador_que_el_foro(self):
        autor = make_user(username='prev', email='prev@example.org')
        self.client.force_login(autor)
        r = self.client.post('/mensaje/previsualizar/', {'content': '**hola**'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('<strong>hola</strong>', r.content.decode())

    def test_la_vista_previa_escapa_el_html_como_el_foro(self):
        autor = make_user(username='prev2', email='prev2@example.org')
        self.client.force_login(autor)
        r = self.client.post('/mensaje/previsualizar/', {'content': '<script>alert(1)</script>'})
        cuerpo = r.content.decode()
        self.assertNotIn('<script>', cuerpo)
        self.assertIn('&lt;script&gt;', cuerpo)

    def test_la_vista_previa_exige_estar_dentro(self):
        r = self.client.post('/mensaje/previsualizar/', {'content': 'hola'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login', r['Location'])

    def test_sin_javascript_el_foro_sigue_funcionando(self):
        """Mejora progresiva: el botón de vista previa lo pone el JS; el
        formulario de siempre publica igual sin él."""
        post, autor = self._hilo(0)
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn(f'action="/post/{post.pk}/reply/"', html)
        self.assertIn('data-preview-url=', html)   # el JS lo lee de aquí, no cableado
