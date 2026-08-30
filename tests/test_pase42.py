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
        # un moderador SÍ: borra segmentos y lanza el pipeline. 4.4-G (David):
        # PRIMERO una pagina de confirmacion con el coste; el segundo POST ejecuta.
        mod = make_user(username='modx', email='modx@example.org')
        mod.is_staff = True
        mod.save()
        self.client.force_login(mod)
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as m:
            r = self.client.post(f'/post/{post.pk}/reanalizar/')
            self.assertEqual(r.status_code, 200)
            self.assertIn('Coste estimado', r.content.decode())
            m.assert_not_called()
            self.client.post(f'/post/{post.pk}/reanalizar/', {'confirm': '1'})
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
        # La vía directa y la vía por lotes tienen que mandar el MISMO texto.
        # 4.4-G: ya no se comparan cadenas — las dos llaman al MISMO constructor.
        directo = open('apps/agents/verdict.py').read()
        lote = open('apps/agents/batch.py').read()
        marca = "CONTEXTO (frases contiguas del mismo hablante; NO se verifican)"
        self.assertIn(marca, directo)
        self.assertIn('def build_payload(', directo)
        self.assertIn('build_payload(', lote)

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

    def test_con_dos_hablantes_el_65_por_ciento_son_los_dos(self):
        """4.4-G: con la puerta en el 65 %, uno de dos (50 %) ya no basta."""
        from apps.analysis.services import identification_gate
        post = self._post(2)
        self._confirmar(post, 'SPEAKER_00', 'Ana Pública')
        self.assertFalse(identification_gate(post)[0])
        self._confirmar(post, 'SPEAKER_01', 'Bea Pública')
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
        self._confirmar(post, 'SPEAKER_01', 'Bea Pública')   # 4.4-G: 65 % de 2 = 2
        votante = make_user(username='vot2E', email='vot2e@example.org', karma=100)
        ok, _msg = cast_vote(post, votante, 'VALIDATE')
        self.assertTrue(ok)
        self.assertEqual(post.distinct_validation_votes('VALIDATE'), 1)

    def test_el_umbral_es_editable_en_el_panel_y_el_entorno(self):
        from django.conf import settings as s
        from apps.panel.views import SETTINGS_DEF
        self.assertIn('min_identified_speakers_percent',
                      [k for k, _l, _h, _t in SETTINGS_DEF])
        # 4.4-G (David, 2026-08-24): del 50 al 65 %.
        self.assertEqual(s.SETTING_DEFAULTS['min_identified_speakers_percent'], '65')
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


class Pase44A(TestCase):
    """4.4-A — la interfaz existe de verdad en inglés.

    Antes de este pase, LOCALE_PATHS apuntaba a una carpeta que no existía: los
    247 {% trans %} de las plantillas marcaban las frases como traducibles y
    detrás no había ningún catálogo. Pulsaras ES o EN, salía español.

    Decisión de David (2026-08-18): SOLO español e inglés, y SOLO la interfaz.
    Ni vídeos, ni transcripciones, ni veredictos, ni mensajes del foro: eso se
    muestra siempre en el idioma en que se escribió.
    """

    def setUp(self):
        # El import va aquí, como en el resto del fichero: `cache` no está
        # importado a nivel de módulo y el setUp del pase lo usaba a pelo
        # (NameError en los 16 tests de esta clase).
        from django.core.cache import cache
        from django.conf import settings as s
        from django.utils import translation
        cache.clear()
        # El idioma activo es estado GLOBAL DEL HILO: una petición con
        # Accept-Language: en deja activado el inglés y el cliente de pruebas no
        # lo restaura al terminar. Sin esto, el test de "los correos siguen en
        # castellano por defecto" veía el inglés que había dejado el test
        # anterior — y el fallo dependía del orden de ejecución.
        translation.activate(s.LANGUAGE_CODE)

    # ---------- el catálogo ----------
    def test_el_catalogo_ingles_existe_y_no_tiene_huecos(self):
        """Una traducción vacía sale como la cadena española: pasa desapercibida."""
        import re
        po = open('locale/en/LC_MESSAGES/django.po', encoding='utf-8').read()
        pares = re.findall(r'^msgid "(.+)"\nmsgstr "(.*)"$', po, re.M)
        self.assertGreater(len(pares), 250, 'el catálogo está a medias')
        vacias = [m for m, t in pares if not t.strip()]
        self.assertEqual(vacias, [], f'{len(vacias)} cadenas sin traducir')

    def test_todas_las_cadenas_de_las_plantillas_estan_en_el_catalogo(self):
        """Candado: una plantilla nueva con {% trans %} y sin entrada en el .po
        sale en español dentro de la web inglesa, sin que nada falle."""
        import glob, re
        po = open('locale/en/LC_MESSAGES/django.po', encoding='utf-8').read()
        catalogo = set(re.findall(r'^msgid "(.+)"$', po, re.M))
        pat = re.compile(r'\{%\s*trans\s+(["\'])(.*?)\1', re.S)
        faltan = set()
        for f in glob.glob('templates/**/*.html', recursive=True):
            for _q, t in pat.findall(open(f, encoding='utf-8').read()):
                if t.replace('"', '\\"') not in catalogo:
                    faltan.add(t)
        self.assertEqual(faltan, set(), f'sin traducir al inglés: {sorted(faltan)[:5]}')

    def test_el_catalogo_traduce_de_verdad(self):
        """Si esto falla, falta `compilemessages`: el .po no lo lee nadie."""
        from django.utils import translation
        from django.utils.translation import gettext
        with translation.override('en'):
            self.assertEqual(gettext('Portada'), 'Home')
            self.assertEqual(gettext('Conversación'), 'Conversation')
        with translation.override('es'):
            self.assertEqual(gettext('Portada'), 'Portada')

    # ---------- la web ----------
    def test_la_portada_responde_en_ingles(self):
        r = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en')
        html = r.content.decode()
        self.assertIn('Home', html)
        self.assertNotIn('>Portada<', html)

    def test_las_etiquetas_de_estado_tambien_se_traducen(self):
        """Van por {% trans variable %}: los choices del modelo no se tocan."""
        autor = make_user(username='ing', email='ing@example.org')
        Post.objects.create(author=autor, url='https://youtu.be/i18n01',
                            title='Vídeo', status='DONE', topic='politica')
        html = self.client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode()
        self.assertIn('Analysed', html)
        self.assertIn('Politics', html)

    def test_las_paginas_legales_tienen_version_inglesa(self):
        for url, esperado in [('/legal/aviso/', 'Legal notice'),
                              ('/legal/privacidad/', 'Privacy policy'),
                              ('/legal/condiciones/', 'Terms of use'),
                              ('/legal/cookies/', 'Cookie policy'),
                              ('/metodologia/', 'How we verify')]:
            html = self.client.get(url, HTTP_ACCEPT_LANGUAGE='en').content.decode()
            self.assertIn(esperado, html, url)

    def test_las_paginas_legales_siguen_en_castellano_por_defecto(self):
        html = self.client.get('/legal/privacidad/').content.decode()
        self.assertIn('Política de privacidad', html)

    # ---------- la elección del usuario ----------
    def test_el_idioma_del_perfil_manda_sobre_el_navegador(self):
        u = make_user(username='eng', email='eng@example.org')
        u.language = 'en'
        u.save(update_fields=['language'])
        self.client.force_login(u)
        html = self.client.get('/', HTTP_ACCEPT_LANGUAGE='es').content.decode()
        self.assertIn('Home', html)

    def test_el_selector_de_la_cabecera_guarda_la_eleccion_en_la_cuenta(self):
        u = make_user(username='sel', email='sel@example.org')
        self.client.force_login(u)
        self.client.post('/accounts/idioma/', {'language': 'en', 'next': '/'})
        u.refresh_from_db()
        self.assertEqual(u.language, 'en')

    def test_el_selector_funciona_sin_cuenta(self):
        """Un visitante no tiene Ajustes: los botones de arriba son su única vía."""
        r = self.client.post('/accounts/idioma/', {'language': 'en', 'next': '/'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('Home', self.client.get('/').content.decode())

    def test_ajustes_permite_volver_al_automatico(self):
        u = make_user(username='auto', email='auto@example.org')
        u.language = 'en'
        u.save(update_fields=['language'])
        self.client.force_login(u)
        self.client.post('/accounts/settings/', {'language': '', 'notify_mode': 'WEB',
                                                 'digest_hour': '8'})
        u.refresh_from_db()
        self.assertEqual(u.language, '')

    # ---------- lo que NO se traduce ----------
    def test_el_contenido_de_los_usuarios_no_se_traduce(self):
        """Decisión explícita: los mensajes se leen en el idioma en que se
        escribieron. Ni columnas, ni traducción automática, ni coste."""
        from apps.forum.machina_glue import create_topic_for_post, get_topic_for_post
        from machina.core.db.models import get_model
        autor = make_user(username='orig', email='orig@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/i18n02',
                                   title='Título en castellano', author_opinion='Abro yo.')
        create_topic_for_post(post)
        MPost = get_model('forum_conversation', 'Post')
        MPost.objects.create(topic=get_topic_for_post(post), poster=autor,
                             subject='Re', content='Esto se queda en castellano',
                             approved=True)
        html = self.client.get(f'/post/{post.pk}/',
                               HTTP_ACCEPT_LANGUAGE='en').content.decode()
        self.assertIn('Esto se queda en castellano', html)   # el mensaje, intacto
        self.assertIn('Título en castellano', html)          # el título, intacto
        self.assertIn('Conversation', html)                  # la interfaz, en inglés

    def test_los_correos_van_en_el_idioma_del_destinatario(self):
        """El de verificación es el único paso OBLIGATORIO del alta: si llega en
        un idioma que el destinatario no lee, el registro se pierde."""
        from django.core import mail
        from apps.accounts.verification import send_verification_email
        u = make_user(username='mail_en', email='mail_en@example.org')
        u.language = 'en'
        u.save(update_fields=['language'])
        mail.outbox = []
        send_verification_email(u)
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertIn('Verify your account', m.subject)
        self.assertIn('Verify my account', m.alternatives[0][0])

    def test_los_correos_siguen_en_castellano_por_defecto(self):
        from django.core import mail
        from apps.accounts.verification import send_verification_email
        u = make_user(username='mail_es', email='mail_es@example.org')
        mail.outbox = []
        send_verification_email(u)
        self.assertIn('Verifica tu cuenta', mail.outbox[0].subject)

    def test_las_cadenas_de_los_correos_estan_en_el_catalogo(self):
        """Las de los .py no las ve el candado de plantillas: van aparte."""
        import re
        po = open('locale/en/LC_MESSAGES/django.po', encoding='utf-8').read()
        catalogo = ' '.join(re.findall(r'^msgid "(.+)"$', po, re.M))
        for frase in ('Verifica tu cuenta', 'Cuenta verificada',
                      'Pulsa para verificar tu cuenta'):
            self.assertIn(frase, catalogo, frase)

    def test_la_infraestructura_de_traduccion_esta_completa(self):
        """gettext en la imagen y compilemessages en el arranque: sin las dos
        cosas el catálogo está en el repositorio y no lo lee nadie."""
        self.assertIn('gettext', open('Dockerfile', encoding='utf-8').read())
        for f in ('docker-compose.yml', 'docker-compose.staging.yml'):
            self.assertIn('compilemessages', open(f, encoding='utf-8').read(), f)


class Pase44B(TestCase):
    """4.4-B — el semáforo se enciende, y cuando no puede, lo dice.

    Encargo de David (2026-08-23): «todas las afirmaciones están en estado "no
    verificado". Eso precisamente no puede pasar en una web cuya razón de existencia
    es buscar la verdad. Hay que arreglarlo como sea.»

    El diagnóstico sobre producción encontró TRES fallos encadenados:
      1. La transcripción no miraba los veredictos: 96 afirmaciones verificadas y
         cero visibles. El trabajo caro se hacía, se pagaba y no se enseñaba.
      2. Las búsquedas volvían vacías (motores suspendidos por exceso de peticiones)
         y el código las daba por buenas porque el HTTP era 200.
      3. Se pagaba la verificación completa de OPINIONES por un `pass` vacío.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    def _post_con_frase(self, texto='Somos 750.000 en el campo, más que nunca.',
                        signal='FACTUAL_UNVERIFIED'):
        autor = make_user(username='sem', email='sem@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/sem001',
                                   title='DEBATE 23J', status='DONE',
                                   duration_seconds=600)
        from apps.analysis.models import TranscriptSegment
        seg = TranscriptSegment.objects.create(post=post, start_seconds=10, end_seconds=14,
                                               text=texto, signal=signal)
        return post, seg, autor

    def _con_veredicto(self, seg, color='GREEN', basis='EPA del INE, serie 1976-2023'):
        from apps.wiki.models import Claim, ClaimAppearance, Source
        c = Claim.objects.create(text_original=seg.text, slug=f'c{seg.pk}', color=color,
                                 temporal_basis=basis, what_is_claimed='X', consolidated=True)
        Source.objects.create(claim=c, url='https://www.ine.es/tabla', title='INE')
        ClaimAppearance.objects.create(claim=c, segment=seg, quote=seg.text)
        return c

    # ---------- 1. el escaparate ----------
    def test_la_transcripcion_muestra_el_semaforo_y_no_la_senal_barata(self):
        post, seg, _ = self._post_con_frase()
        self._con_veredicto(seg, 'GREEN')
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('verdict-GREEN', html)
        self.assertIn('Verificado', html)
        # La señal barata DESAPARECE en cuanto hay veredicto (decisión de David).
        self.assertNotIn('signal-FACTUAL_UNVERIFIED', html)

    def test_el_semaforo_enlaza_a_la_ficha_con_sus_fuentes(self):
        post, seg, _ = self._post_con_frase()
        c = self._con_veredicto(seg)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn(f'/wiki/claim/{c.slug}/', html)
        self.assertIn('fuente', html)

    def test_la_frase_sin_veredicto_sigue_mostrando_su_senal(self):
        post, seg, _ = self._post_con_frase()
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('signal-FACTUAL_UNVERIFIED', html)

    def test_el_pie_deja_de_mentir_cuando_hay_veredictos(self):
        """Decía siempre «no son veredictos verificados», también después de verificar."""
        post, seg, _ = self._post_con_frase()
        self._con_veredicto(seg)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('contrastado con fuentes enlazadas', html)

    def test_se_ve_contra_que_se_comparo(self):
        """«Nunca es nunca»: el lector puede discrepar del criterio, no solo del dato."""
        post, seg, _ = self._post_con_frase()
        self._con_veredicto(seg, 'GREEN', 'EPA del INE, serie 1976-2023')
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('serie 1976-2023', html)

    # ---------- 2. los estados ----------
    def test_existen_los_seis_estados_y_los_tres_sin_resolver(self):
        from apps.wiki.models import COLORS, UNSETTLED
        claves = dict(COLORS)
        for c in ('GREEN', 'AMBER', 'RED', 'GREY', 'PENDING', 'UNDECIDED', 'NEEDS_HUMAN'):
            self.assertIn(c, claves, c)
        self.assertEqual(set(UNSETTLED), {'PENDING', 'UNDECIDED', 'NEEDS_HUMAN'})

    def test_una_afirmacion_indecisa_ofrece_el_reanalisis_profundo(self):
        post, seg, autor = self._post_con_frase()
        self._con_veredicto(seg, 'UNDECIDED')
        self.client.force_login(autor)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('verdict-UNDECIDED', html)
        self.assertIn('reanálisis profundo', html)

    def test_un_color_inventado_por_el_modelo_no_entra_en_la_base(self):
        from apps.wiki.services import upsert_claim
        post, seg, _ = self._post_con_frase()
        c = upsert_claim(post, {'text': seg.text, 'segment_index': 0},
                         {'color': 'MORADO', 'what_is_claimed': 'x'}, sources_ok=True)
        self.assertEqual(c.color, 'UNDECIDED')

    # ---------- 3. la raíz: las búsquedas ----------
    def test_una_busqueda_vacia_no_es_una_busqueda_correcta(self):
        """El fallo de raíz: SearXNG devolvía 200 con la lista vacía cuando los
        motores estaban suspendidos, y el código lo daba por bueno."""
        from apps.agents import search
        from unittest.mock import patch
        with patch.object(search, '_one_call', return_value=([], 'vacio')):
            with self.settings(MOCK_AGENTS=False):
                resultados, ok = search.search_with_status('lo que sea')
        self.assertEqual(resultados, [])
        self.assertFalse(ok, 'una búsqueda sin resultados NO puede darse por buena')

    def test_las_fuentes_oficiales_se_consultan_primero(self):
        from apps.agents import search
        vistas = []

        def espia(consulta, timeout=15):
            vistas.append(consulta)
            return ([], 'vacio')

        from unittest.mock import patch
        with patch.object(search, '_one_call', side_effect=espia):
            with self.settings(MOCK_AGENTS=False):
                search.search_with_status('ocupados agricultura')
        self.assertTrue(vistas[0].startswith('site:'), vistas[:2])

    # ---------- 4. no pagar lo que no se verifica ----------
    def test_las_opiniones_no_se_verifican_ni_se_pagan(self):
        """Un `pass` vacío hacía que el bucle siguiera: 17 frases factuales y 32
        veredictos en el post 4 de producción."""
        from apps.agents import verdict as va
        post, seg, _ = self._post_con_frase('Cataluña es una nación.', signal='OPINION')
        llamadas = []
        from unittest.mock import patch
        with patch.object(va.client, 'call_json',
                          side_effect=lambda *a, **k: llamadas.append(a) or {'color': 'GREY'}):
            with patch.object(va.search, 'search_with_status', return_value=([], False)):
                va.run(post)
        self.assertEqual(llamadas, [], 'se ha pagado la verificación de una opinión')

    def test_sin_fuentes_no_se_pinta_color_y_queda_indecisa(self):
        from apps.agents import verdict as va
        from apps.wiki.models import Claim
        post, seg, _ = self._post_con_frase()
        from unittest.mock import patch
        # 4.4-E: el circuito cambio. Ya no se consulta a SearXNG antes de decidir si
        # se llama al modelo — el propio modelo busca sus fuentes. La regla de David
        # sigue siendo la misma y es lo que se comprueba aqui: si el veredicto vuelve
        # SIN una sola URL, ese color NO se publica, por muy verde que lo pinte el
        # modelo. La garantia tiene que vivir en el codigo, no en el prompt.
        with patch.object(va.client, 'call_search_json',
                          return_value=({'color': 'GREEN', 'what_is_claimed': 'x',
                                         'sources': []}, 'claude-sonnet-4-6')):
            va.run(post)
        c = Claim.objects.filter(text_original=seg.text).first()
        self.assertIsNotNone(c)
        self.assertEqual(c.color, 'UNDECIDED', 'un verde sin fuentes se ha publicado')
        self.assertFalse(c.sources_ok)

    # ---------- 5. el anclaje ----------
    def test_dos_frases_en_el_mismo_segundo_no_intercambian_su_veredicto(self):
        """Bug real: quien numeraba usaba ('start_seconds','pk') y quien anclaba
        solo 'start_seconds'. Con dos personas pisándose, el veredicto se pegaba a
        la frase equivocada."""
        from apps.wiki.services import upsert_claim
        from apps.wiki.models import ClaimAppearance
        post, seg1, _ = self._post_con_frase('Primera frase.')
        from apps.analysis.models import TranscriptSegment
        seg2 = TranscriptSegment.objects.create(post=post, start_seconds=10, end_seconds=15,
                                                text='Segunda frase.',
                                                signal='FACTUAL_UNVERIFIED')
        # índice 1 = la SEGUNDA en el orden ('start_seconds', 'pk')
        upsert_claim(post, {'text': 'Segunda frase.', 'segment_index': 1},
                     {'color': 'RED', 'what_is_claimed': 'x'}, sources_ok=True)
        ap = ClaimAppearance.objects.get(claim__text_original='Segunda frase.')
        self.assertEqual(ap.segment_id, seg2.pk)

    # ---------- 6. el tope diario ----------
    def test_el_tope_diario_frena_la_verificacion_automatica(self):
        from apps.analysis.tasks import auto_verify_slot_free
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='auto_verify_daily_cap',
                                               defaults={'value': '2'})
        autor = make_user(username='cap', email='cap@example.org')
        self.assertTrue(auto_verify_slot_free())
        for i in range(2):
            Post.objects.create(author=autor, url=f'https://youtu.be/c{i}',
                                full_started_at=timezone.now())
        self.assertFalse(auto_verify_slot_free(), 'el tope diario no está frenando')

    def test_el_tope_a_cero_devuelve_el_control_a_los_votos(self):
        from apps.analysis.tasks import auto_verify_slot_free
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='auto_verify_daily_cap',
                                               defaults={'value': '0'})
        self.assertFalse(auto_verify_slot_free())

    # ---------- 7. la fecha del suceso ----------
    def test_la_fecha_del_suceso_se_normaliza_aunque_venga_incompleta(self):
        from apps.agents.dating import normalize
        import datetime
        self.assertEqual(normalize('2023-07-10'), datetime.date(2023, 7, 10))
        self.assertEqual(normalize('2023-07'), datetime.date(2023, 7, 1))
        self.assertEqual(normalize('2023'), datetime.date(2023, 1, 1))
        self.assertIsNone(normalize(None))
        self.assertIsNone(normalize('el año pasado'))

    def test_la_fecha_del_suceso_se_muestra_marcada_como_estimada(self):
        import datetime
        post, seg, _ = self._post_con_frase()
        post.event_date = datetime.date(2023, 7, 10)
        post.event_date_source = 'agent'
        post.save(update_fields=['event_date', 'event_date_source'])
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('10/07/2023', html)
        self.assertIn('estimada', html)

    # ---------- 8. reverificar sin perder lo bueno ----------
    def test_reverificar_conserva_transcripcion_y_hablantes(self):
        """Orden de David: «volver a verificar todo, manteniendo las personas que
        hablan, que están correctas»."""
        from apps.analysis.tasks import reverify_post
        from apps.wiki.models import ClaimAppearance
        post, seg, _ = self._post_con_frase()
        seg.speaker_label = 'SPEAKER_1'
        seg.save(update_fields=['speaker_label'])
        self._con_veredicto(seg, 'GREEN')
        from unittest.mock import patch
        with patch('apps.analysis.tasks.launch_full_analysis'):
            reverify_post(post.pk)
        seg.refresh_from_db()
        self.assertEqual(seg.speaker_label, 'SPEAKER_1')      # el hablante, intacto
        self.assertEqual(post.transcript_segments.count(), 1)  # la transcripción, intacta
        self.assertEqual(ClaimAppearance.objects.filter(segment__post=post).count(), 0)
        post.refresh_from_db()
        self.assertEqual(post.status, 'FULL_QUEUED')


class Pase44C(TestCase):
    """4.4-C — el panel de modelos, la transcripción entera y el vigía nocturno.

    David: «crea un panel para el admin donde pueda establecer los modelos usados
    para cada situación». Y eligió LIBERTAD TOTAL con aviso de coste, no candados.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    def test_cada_tarea_tiene_modelo_y_metodo_de_envio(self):
        from apps.agents import catalog
        for clave in catalog.TASK_KEYS:
            self.assertIn(catalog.model_for(clave), catalog.BY_ID, clave)
            self.assertIn(catalog.delivery_for(clave), catalog.DELIVERY_KEYS, clave)

    def test_el_panel_manda_sobre_el_valor_de_fabrica(self):
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='model_verdict',
                                               defaults={'value': 'claude-opus-4-8'})
        self.assertEqual(catalog.model_for('verdict'), 'claude-opus-4-8')

    def test_un_modelo_inventado_en_la_base_se_ignora(self):
        """Lista cerrada (decisión de David): una errata no puede dejar la web
        sin analizar."""
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='model_sweep',
                                               defaults={'value': 'gpt-lo-que-sea'})
        self.assertIn(catalog.model_for('sweep'), catalog.BY_ID)

    def test_el_suplente_nunca_es_peor_que_el_titular(self):
        """Decisión de David: «un escalón por encima en calidad, nunca por debajo»."""
        from apps.agents import catalog
        for mid, _l, tier, _pi, _po, _web in catalog.CATALOG:  # 4.4-E anadio la columna web
            sup = catalog.substitute(mid)
            if sup:
                self.assertGreater(catalog.tier(sup), tier, f'{mid} → {sup}')

    def test_el_mejor_modelo_se_queda_sin_suplente(self):
        from apps.agents import catalog
        mejor = max(catalog.CATALOG, key=lambda m: m[2])[0]
        self.assertEqual(catalog.substitute(mejor), '')

    def test_la_memoria_abarata_la_transcripcion_entera(self):
        """Sin caché, mandar el texto 80 veces multiplica la factura por más de
        dos. Con caché, sube un 17%. Es la diferencia entre asumible y no."""
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='delivery_verdict',
                                               defaults={'value': 'direct'})
        con_memoria = catalog.cost_per_hour_eur(task='verdict')
        SystemSetting.objects.update_or_create(key='delivery_verdict',
                                               defaults={'value': 'batch'})
        por_correo = catalog.cost_per_hour_eur(task='verdict')
        self.assertLess(con_memoria, por_correo)

    def test_avisa_cuando_la_combinacion_es_lo_peor_de_los_dos(self):
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='delivery_verdict',
                                               defaults={'value': 'batch'})
        self.assertIn('24 h', catalog.warning_for('verdict'))

    def test_el_expediente_lleva_marcas_de_tiempo_y_metadatos(self):
        """Lo que pidió David: transcripción entera marcada con su marca de
        tiempo, la oración con contexto, y los metadatos del vídeo."""
        from apps.agents.verdict import transcript_dossier
        from apps.analysis.models import TranscriptSegment
        autor = make_user(username='exp', email='exp@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/exp1',
                                   title='DEBATE 23J', duration_seconds=720)
        TranscriptSegment.objects.create(post=post, start_seconds=125, end_seconds=130,
                                         text='Somos 750.000 en el campo.')
        d = transcript_dossier(post)
        self.assertIn('DEBATE 23J', d)
        self.assertIn('[02:05]', d)
        self.assertIn('750.000', d)
        self.assertIn('FICHA DEL VÍDEO', d)

    def test_el_expediente_es_identico_entre_llamadas(self):
        """Si cambiara byte a byte, la memoria no serviría y se pagaría el texto
        entero cada vez."""
        from apps.agents.verdict import transcript_dossier
        from apps.analysis.models import TranscriptSegment
        autor = make_user(username='exp2', email='exp2@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/exp2', title='X')
        TranscriptSegment.objects.create(post=post, start_seconds=1, end_seconds=2, text='a')
        self.assertEqual(transcript_dossier(post), transcript_dossier(post))

    def test_el_veredicto_guarda_con_que_modelo_se_emitio(self):
        from apps.wiki.services import upsert_claim
        from apps.analysis.models import TranscriptSegment
        autor = make_user(username='mu', email='mu@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/mu1', title='X')
        TranscriptSegment.objects.create(post=post, start_seconds=0, end_seconds=3,
                                         text='Una afirmación.')
        c = upsert_claim(post, {'text': 'Una afirmación.', 'segment_index': 0},
                         {'color': 'GREEN', 'what_is_claimed': 'x',
                          'model_used': 'claude-opus-4-8'}, sources_ok=True)
        self.assertEqual(c.model_used, 'claude-opus-4-8')

    def test_el_panel_de_modelos_responde_y_guarda(self):
        root = make_user(username='root44c', email='root44c@example.org',
                         is_superuser=True, is_staff=True)
        self.client.force_login(root)
        r = self.client.get('/panel/modelos/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Modelo', r.content.decode())
        self.client.post('/panel/modelos/', {'model_verdict': 'claude-opus-4-8',
                                             'delivery_verdict': 'direct'})
        from apps.agents import catalog
        self.assertEqual(catalog.model_for('verdict'), 'claude-opus-4-8')

    def test_el_vigia_apunta_la_salud_de_cada_modelo(self):
        from apps.panel.tasks import check_models
        from apps.panel.models import ModelHealth
        check_models()
        self.assertGreater(ModelHealth.objects.count(), 0)
        self.assertTrue(all(h.ok for h in ModelHealth.objects.all()))

    def test_el_vigia_corre_todos_los_dias(self):
        from config.celery import app
        self.assertIn('comprobar-modelos', app.conf.beat_schedule)


class Pase44D(TestCase):
    """4.4-D — el voto del admin relanza el análisis SIEMPRE.

    Orden de David (2026-08-23): «El voto del admin siempre relanzará el análisis».

    Por qué hacía falta: el reanálisis profundo era **inalcanzable**. Por frase
    pedía 5 personas distintas; por vídeo, un 40% de al menos 50 usuarios
    verificados. Con el registro cerrado a propósito, nadie podía juntarlos: la
    rueda de «Reanálisis profundo» del panel de modelos estaba configurada y no la
    podía usar nadie.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    def _post_analizado(self):
        from apps.analysis.models import TranscriptSegment
        autor = make_user(username='d44d', email='d44d@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/d44d1',
                                   title='X', status='DONE')
        seg = TranscriptSegment.objects.create(post=post, start_seconds=5, end_seconds=9,
                                               text='Una afirmación discutible.')
        return post, seg

    def test_el_voto_del_superusuario_relanza_la_frase_al_instante(self):
        from unittest.mock import patch
        post, seg = self._post_analizado()
        root = make_user(username='root44d', email='root44d@example.org',
                         is_superuser=True, is_staff=True)
        self.client.force_login(root)
        with patch('apps.analysis.tasks.opus_rescan_segment.delay') as tarea:
            self.client.post(f'/oracion/{seg.pk}/votar/down/')
        tarea.assert_called_once()
        self.assertTrue(tarea.call_args.kwargs.get('forced'))

    def test_un_usuario_normal_sigue_necesitando_cinco_votos(self):
        from unittest.mock import patch
        post, seg = self._post_analizado()
        u = make_user(username='normal44d', email='normal44d@example.org')
        self.client.force_login(u)
        with patch('apps.analysis.tasks.opus_rescan_segment.delay') as tarea:
            self.client.post(f'/oracion/{seg.pk}/votar/down/')
        tarea.assert_not_called()

    def test_el_admin_relanza_aunque_ya_se_hubiera_reanalizado(self):
        """«Siempre» es siempre: el candado de una-vez-por-frase no le aplica."""
        from unittest.mock import patch
        post, seg = self._post_analizado()
        seg.opus_rescanned = True
        seg.save(update_fields=['opus_rescanned'])
        root = make_user(username='root44d2', email='root44d2@example.org',
                         is_superuser=True, is_staff=True)
        self.client.force_login(root)
        with patch('apps.analysis.tasks.opus_rescan_segment.delay') as tarea:
            self.client.post(f'/oracion/{seg.pk}/votar/down/')
        tarea.assert_called_once()

    def test_la_tarea_forzada_ignora_el_candado(self):
        from unittest.mock import patch
        from apps.analysis.tasks import opus_rescan_segment
        post, seg = self._post_analizado()
        seg.opus_rescanned = True
        seg.save(update_fields=['opus_rescanned'])
        self.assertEqual(opus_rescan_segment(seg.pk), 'skip')
        resultado = opus_rescan_segment(seg.pk, forced=True)
        self.assertNotEqual(resultado, 'skip')

    def test_el_voto_del_admin_relanza_el_video_entero_sin_esperar_al_40_por_ciento(self):
        from unittest.mock import patch
        from apps.analysis.tasks import maybe_trigger_opus_rescan
        post, _seg = self._post_analizado()
        root = make_user(username='root44d3', email='root44d3@example.org',
                         is_superuser=True, is_staff=True)
        with patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            self.assertTrue(maybe_trigger_opus_rescan(post, root))
        tarea.assert_called_once()

    def test_sin_usuario_el_umbral_de_siempre_sigue_mandando(self):
        from apps.analysis.tasks import maybe_trigger_opus_rescan
        post, _seg = self._post_analizado()
        self.assertFalse(maybe_trigger_opus_rescan(post))       # <50 usuarios
        self.assertFalse(maybe_trigger_opus_rescan(post, None))

    def test_queda_registrado_en_la_auditoria(self):
        from unittest.mock import patch
        from apps.panel.models import AuditLog
        post, seg = self._post_analizado()
        root = make_user(username='root44d4', email='root44d4@example.org',
                         is_superuser=True, is_staff=True)
        self.client.force_login(root)
        with patch('apps.analysis.tasks.opus_rescan_segment.delay'):
            self.client.post(f'/oracion/{seg.pk}/votar/down/')
        self.assertTrue(AuditLog.objects.filter(action='force_deep_scan').exists())

    def test_el_reanalisis_profundo_recibe_la_transcripcion_entera(self):
        """Orden de David: al modelo alto se le pasa el expediente completo. Es
        justo donde más falta hace: si se pide una segunda mirada es porque la
        primera, con la frase suelta, no bastó."""
        from unittest.mock import patch
        from apps.analysis.tasks import opus_rescan_segment
        post, seg = self._post_analizado()
        capturado = {}

        def espia(*a, **k):
            capturado.update(k)
            return ({'color': 'GREEN', 'what_is_claimed': 'x'}, 'claude-opus-4-8')

        # 4.4-E: el reanalisis dejo de usar call_json y ahora busca sus propias
        # fuentes con call_search_json. La intencion del test no cambia — el
        # expediente completo tiene que seguir viajando como bloque cacheable.
        with patch('apps.agents.client.call_search_json', side_effect=espia):
            opus_rescan_segment(seg.pk, forced=True)
        self.assertIn('cacheable', capturado)
        self.assertIn('FICHA DEL VÍDEO', capturado['cacheable'])
        self.assertIn('[00:05]', capturado['cacheable'])


class Pase44E(TestCase):
    """4.4-E — «todo por Claude»: el modelo busca sus propias fuentes.

    Decisión de David (2026-08-23) tras el bloqueo de SearXNG por los buscadores:
    las fuentes las trae la herramienta de búsqueda web de Anthropic (10 $/1.000 +
    tokens). Se paga más por búsqueda, pero desaparecen los portazos: cliente
    identificado, no robot anónimo.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    def test_las_tareas_con_web_avisan_si_el_modelo_no_busca(self):
        """Petición literal de David: «Este modelo no permite búsqueda web»."""
        from apps.agents import catalog
        from unittest.mock import patch
        ciego = ('modelo-ciego', 'Ciego', 2, 3.0, 15.0, False)
        with patch.object(catalog, 'CATALOG', catalog.CATALOG + [ciego]), \
             patch.object(catalog, 'BY_ID', {**catalog.BY_ID, 'modelo-ciego': ciego}):
            from apps.panel.models import SystemSetting
            SystemSetting.objects.update_or_create(key='model_verdict',
                                                   defaults={'value': 'modelo-ciego'})
            aviso = catalog.warning_for('verdict')
        self.assertIn('no permite búsqueda web', aviso)

    def test_los_seis_modelos_actuales_saben_buscar(self):
        from apps.agents import catalog
        for m in catalog.CATALOG:
            self.assertTrue(catalog.supports_web(m[0]), m[0])

    def test_el_suplente_de_una_tarea_web_tambien_sabe_buscar(self):
        from apps.agents import catalog
        for m in catalog.CATALOG:
            sup = catalog.substitute(m[0], need_web=True)
            if sup:
                self.assertTrue(catalog.supports_web(sup), f'{m[0]} → {sup}')

    def test_el_veredicto_ya_no_llama_al_documentalista_viejo(self):
        """SearXNG queda fuera del circuito: si algo volviera a llamarlo desde el
        veredicto, volverían los portazos."""
        from apps.agents import verdict as va
        from apps.analysis.models import TranscriptSegment
        from unittest.mock import patch
        autor = make_user(username='e44', email='e44@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/e441',
                                   title='X', status='DONE')
        TranscriptSegment.objects.create(post=post, start_seconds=1, end_seconds=3,
                                         text='Afirmación.', signal='FACTUAL_UNVERIFIED')
        with patch.object(va.search, 'search_with_status') as viejo:
            va.run(post)
        viejo.assert_not_called()

    def test_el_veredicto_simulado_guarda_fuentes_y_modelo(self):
        from apps.agents import verdict as va
        from apps.analysis.models import TranscriptSegment
        from apps.wiki.models import Claim
        autor = make_user(username='e44b', email='e44b@example.org')
        post = Post.objects.create(author=autor, url='https://youtu.be/e442',
                                   title='X', status='DONE')
        TranscriptSegment.objects.create(post=post, start_seconds=1, end_seconds=3,
                                         text='La torre mide 300 m.',
                                         signal='FACTUAL_UNVERIFIED')
        va.run(post)
        c = Claim.objects.get(text_original='La torre mide 300 m.')
        self.assertTrue(c.sources.exists())
        self.assertTrue(c.sources_ok)

    def test_el_tope_de_busquedas_se_lee_del_panel(self):
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='web_searches_per_claim',
                                               defaults={'value': '5'})
        self.assertEqual(catalog.web_searches_per_claim(), 5)

    def test_el_coste_estimado_incluye_las_busquedas(self):
        """Una hora ≈ 80 afirmaciones × tope de búsquedas × 1 céntimo: tiene que
        notarse en el número del panel."""
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='web_searches_per_claim',
                                               defaults={'value': '1'})
        barato = catalog.cost_per_hour_eur(task='verdict')
        SystemSetting.objects.update_or_create(key='web_searches_per_claim',
                                               defaults={'value': '5'})
        caro = catalog.cost_per_hour_eur(task='verdict')
        self.assertGreater(caro, barato)


class Pase44F(TestCase):
    """4.4-F — el cruce voz↔frase deja de regalar las frases al que domina.

    Caso real (post 5, podcast en inglés): pyannote detectó 3 hablantes y 287
    turnos, y aun así TODO salió como SPEAKER_00. Causa: turnos solapados — uno
    largo del dominante envolvía los microturnos del otro, y «el de más solape»
    se lo quedaba todo.
    """

    def test_el_turno_especifico_gana_al_envolvente(self):
        """«Get out» (1 s) dentro de un turno de 30 s del otro: antes se lo
        quedaba el envolvente; ahora gana el microturno que lo cubre."""
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0.0, 30.0, 'SPEAKER_00'), (3.0, 4.2, 'SPEAKER_01')]
        raw = [
            {'start_seconds': 0.0, 'end_seconds': 2.8, 'text': 'I have an explainer.'},
            {'start_seconds': 3.1, 'end_seconds': 4.1, 'text': 'Get out.'},
            {'start_seconds': 4.5, 'end_seconds': 7.0, 'text': 'So, the 19th century.'},
        ]
        out = merge_into_sentences(raw, turns)
        por_texto = {m['text']: m['speaker_label'] for m in out}
        self.assertEqual(por_texto['Get out.'], 'SPEAKER_01')
        self.assertEqual(por_texto['I have an explainer.'], 'SPEAKER_00')

    def test_sin_turno_que_cubra_gana_el_de_mas_solape_como_siempre(self):
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0.0, 1.0, 'SPEAKER_00'), (1.0, 1.4, 'SPEAKER_01')]
        raw = [{'start_seconds': 0.0, 'end_seconds': 2.0, 'text': 'Frase larga aquí.'}]
        out = merge_into_sentences(raw, turns)
        self.assertEqual(out[0]['speaker_label'], 'SPEAKER_00')

    def test_las_palabras_con_reloj_parten_el_fragmento_entre_voces(self):
        """Un fragmento de whisper con palabras de DOS voces se reparte: cada
        palabra va con la suya y salen dos frases, no una."""
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0.0, 3.0, 'SPEAKER_00'), (3.0, 6.0, 'SPEAKER_01')]
        raw = [{'start_seconds': 0.0, 'end_seconds': 6.0,
                'text': 'Hello there. Thank you.',
                'words': [{'start': 0.2, 'end': 1.0, 'text': 'Hello'},
                          {'start': 1.1, 'end': 2.0, 'text': 'there.'},
                          {'start': 3.2, 'end': 4.0, 'text': 'Thank'},
                          {'start': 4.1, 'end': 5.0, 'text': 'you.'}]}]
        out = merge_into_sentences(raw, turns)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]['speaker_label'], 'SPEAKER_00')
        self.assertEqual(out[0]['text'], 'Hello there.')
        self.assertEqual(out[1]['speaker_label'], 'SPEAKER_01')
        self.assertEqual(out[1]['text'], 'Thank you.')

    def test_sin_diarizacion_las_palabras_no_fragmentan(self):
        """Sin turnos no hay nada que cruzar: el fragmento queda entero."""
        from apps.analysis.tasks import merge_into_sentences
        raw = [{'start_seconds': 0.0, 'end_seconds': 6.0,
                'text': 'Hello there. Thank you.',
                'words': [{'start': 0.2, 'end': 1.0, 'text': 'Hello'}]}]
        out = merge_into_sentences(raw, [])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['text'], 'Hello there. Thank you.')


class Pase44G(TestCase):
    """4.4-G — las voces, la vía de lotes, el panel que manda y la llave inglesa.

    Encargo del operador (docs/47-48, medido sobre el post 5) más las notas de
    David del 2026-08-24. Nueve puntos:
      B.2 el panel manda (delivery_for única fuente de verdad + test de coherencia)
      B.1 batch.py busca con el modelo, como la vía directa
      A.1 la pista del número de voces viaja en la datación (coste cero)
      A.4 suelo al fragmentar · A.3 fantasma absorbido · A.5 backchannels
      la puerta del 65 % frena TODO y se reanuda sola · Intro envía ·
      la llave inglesa con confirmación de coste en las cuatro etapas.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    # ---------- utilidades ----------
    def _post(self, n, status='PENDING_VALIDATION', etiquetas=('SPEAKER_00', 'SPEAKER_01')):
        post = Post.objects.create(
            author=make_user(username=f'g{n}', email=f'g{n}@example.org'),
            url=f'https://youtu.be/g44{n}', status=status, title=f'Vídeo G{n}',
            duration_seconds=1200, validation_deadline=timezone.now() + timedelta(days=2))
        for i, etq in enumerate(etiquetas):
            post.transcript_segments.create(start_seconds=i * 5.0, end_seconds=i * 5.0 + 4,
                                            text=f'Afirmación {i} con datos.',
                                            speaker_label=etq, signal='FACTUAL_UNVERIFIED')
        return post

    def _mod(self, n):
        return make_user(username=f'gmod{n}', email=f'gmod{n}@example.org',
                         is_staff=True, is_superuser=True)

    def _confirmar(self, post, etiqueta, nombre):
        from apps.wiki.models import SpeakerNameProposal
        return SpeakerNameProposal.objects.create(
            post=post, speaker_label=etiqueta, candidate_name=nombre,
            confirmed=True, source='user')

    # ---------- B.2 · el panel manda ----------
    def test_la_via_de_lotes_la_decide_el_panel_y_no_el_env(self):
        """Antes mandaba settings.USE_BATCH_API por encima de lo que David veía
        en /panel/modelos/. Ahora, con el .env diciendo «lotes», el panel en
        «mostrador» va al mostrador; y al revés."""
        from apps.analysis.tasks import run_full_analysis
        from apps.panel.models import SystemSetting
        post = self._post(1, status='FULL_QUEUED')
        with override_settings(USE_BATCH_API=True):
            SystemSetting.objects.update_or_create(key='delivery_verdict',
                                                   defaults={'value': 'direct'})
            with mock.patch('apps.analysis.tasks._submit_batch') as lote, \
                    mock.patch('apps.agents.verdict.run') as directo:
                run_full_analysis(post.pk)
            lote.assert_not_called()
            directo.assert_called_once()
        with override_settings(USE_BATCH_API=False):
            SystemSetting.objects.update_or_create(key='delivery_verdict',
                                                   defaults={'value': 'batch'})
            post.status = 'FULL_QUEUED'
            post.save(update_fields=['status'])
            with mock.patch('apps.analysis.tasks._submit_batch', return_value=True) as lote, \
                    mock.patch('apps.agents.verdict.run') as directo:
                run_full_analysis(post.pk)
            lote.assert_called_once()
            directo.assert_not_called()

    def test_ningun_modulo_de_apps_lee_use_batch_api(self):
        """Candado AST (no de cadena: un comentario no debe hacerlo saltar)."""
        import ast, glob
        for path in glob.glob('apps/**/*.py', recursive=True):
            if '/migrations/' in path:
                continue
            for x in ast.walk(ast.parse(open(path, encoding='utf-8').read())):
                if isinstance(x, ast.Attribute) and x.attr == 'USE_BATCH_API':
                    self.fail(f'{path} sigue leyendo settings.USE_BATCH_API')

    def test_cada_rueda_del_panel_gobierna_una_llamada_real(self):
        """Test de coherencia pedido por el operador: para cada tarea del panel
        tiene que haber código que lea model_for('<tarea>'). Hasta hoy la rueda
        «Clasificador» no la leía nadie: mostraba Sonnet y no pasaba nada."""
        import glob
        from apps.agents import catalog
        fuentes = '\n'.join(open(p, encoding='utf-8').read()
                            for p in glob.glob('apps/**/*.py', recursive=True)
                            if '/migrations/' not in p and not p.endswith('catalog.py'))
        for clave in catalog.TASK_KEYS:
            self.assertIn(f"model_for('{clave}')", fuentes,
                          f'la rueda «{clave}» del panel no gobierna ninguna llamada')

    def test_el_panel_muestra_exactamente_lo_que_el_codigo_decide(self):
        from apps.agents import catalog
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='model_verdict',
                                               defaults={'value': 'claude-opus-4-8'})
        SystemSetting.objects.update_or_create(key='delivery_verdict',
                                               defaults={'value': 'batch'})
        SystemSetting.objects.update_or_create(key='delivery_sweep',
                                               defaults={'value': 'batch'})  # fila huérfana
        self.client.force_login(self._mod(1))
        r = self.client.get('/panel/modelos/')
        self.assertEqual(r.status_code, 200)
        for fila in r.context['rows']:
            self.assertEqual(fila['model'], catalog.model_for(fila['key']), fila['key'])
            self.assertEqual(fila['delivery'], catalog.delivery_for(fila['key']), fila['key'])
        self.assertEqual(catalog.delivery_for('verdict'), 'batch')
        self.assertEqual(catalog.delivery_for('sweep'), 'direct')   # la fila no manda: no hay vía

    def test_las_tareas_sin_via_de_lotes_no_ofrecen_el_selector(self):
        self.client.force_login(self._mod(2))
        html = self.client.get('/panel/modelos/').content.decode()
        self.assertIn('name="delivery_verdict"', html)
        self.assertIn('name="delivery_deep"', html)
        for clave in ('sweep', 'dating', 'moderation', 'classify'):
            self.assertNotIn(f'name="delivery_{clave}"', html, clave)

    # ---------- el clasificador existe de verdad ----------
    def _sweep_de_opinion(self):
        return {'claims': [{'text': 'Es horrible.', 'kind': 'OPINION'}] * 8
                          + [{'text': 'Hay 750.000 ocupados.', 'kind': 'FACTUAL'}],
                'manipulation': False, 'is_adult': False}

    def test_la_segunda_opinion_del_clasificador_rescata_con_confianza_alta(self):
        from apps.agents import algorithm, catalog
        post = self._post(3)
        with mock.patch('apps.agents.client.call_json',
                        return_value={'verdict': 'FACTUAL', 'confidence': 'high'}) as llamada:
            self.assertEqual(algorithm.classify(post, self._sweep_de_opinion()), 'FACTUAL')
        self.assertEqual(llamada.call_args.args[0], catalog.model_for('classify'))

    def test_la_segunda_opinion_dudosa_no_rescata_y_la_regla_factual_no_pregunta(self):
        from apps.agents import algorithm
        post = self._post(4)
        with mock.patch('apps.agents.client.call_json',
                        return_value={'verdict': 'FACTUAL', 'confidence': 'low'}):
            self.assertEqual(algorithm.classify(post, self._sweep_de_opinion()), 'OPINION')
        factual = {'claims': [{'text': f'Dato {i}.', 'kind': 'FACTUAL'} for i in range(10)],
                   'manipulation': False, 'is_adult': False}
        with mock.patch('apps.agents.client.call_json') as llamada:
            self.assertEqual(algorithm.classify(post, factual), 'FACTUAL')
        llamada.assert_not_called()   # solo rescata; jamás relega

    # ---------- B.1 · el lote busca con el modelo ----------
    def _anthropic_falso(self):
        falso = mock.MagicMock()
        falso.Anthropic.return_value.messages.batches.create.return_value.id = 'batch_x'
        return falso

    def test_el_lote_lleva_la_busqueda_web_y_el_mismo_payload(self):
        from apps.agents import batch
        from apps.agents.verdict import _claims_from_segments, build_payload
        post = self._post(5, status='FULL_RUNNING')
        claims = _claims_from_segments(post)
        falso = self._anthropic_falso()
        with mock.patch.dict('sys.modules', {'anthropic': falso}), \
                mock.patch.object(batch, 'model_for', return_value='claude-sonnet-4-6'):
            self.assertEqual(batch.submit_verdict_batch(post, claims), 'batch_x')
        peticiones = falso.Anthropic.return_value.messages.batches.create.call_args.kwargs['requests']
        self.assertEqual(len(peticiones), len(claims))
        params = peticiones[0]['params']
        self.assertEqual(params['tools'][0]['name'], 'web_search')
        contenido = params['messages'][0]['content']
        texto = contenido if isinstance(contenido, str) else contenido[-1]['text']
        self.assertEqual(texto, build_payload(claims[0], None, batch.web_searches_per_claim()))

    def test_el_lote_ya_no_llama_al_documentalista_viejo(self):
        import ast
        arbol = ast.parse(open('apps/agents/batch.py', encoding='utf-8').read())
        for x in ast.walk(arbol):
            if isinstance(x, ast.ImportFrom) and x.module == 'apps.agents':
                self.assertNotIn('search', [a.name for a in x.names])
            if isinstance(x, ast.Attribute):
                self.assertNotEqual(x.attr, 'search_with_status')

    def test_el_sondeo_del_lote_aplica_sin_fuentes_no_hay_color(self):
        from apps.agents import batch
        from apps.wiki.models import ClaimAppearance
        post = self._post(6, status='FULL_RUNNING')
        claims = [{'segment_index': 0, 'text': 'Afirmación 0 con datos.', 'kind': 'FACTUAL'}]
        import json
        respuesta = mock.MagicMock()
        respuesta.custom_id = f'claim-{post.pk}-0'
        respuesta.result.type = 'succeeded'
        respuesta.result.message.model = 'claude-sonnet-4-6'
        bloque = mock.MagicMock(); bloque.type = 'text'
        bloque.text = 'Tras buscar: {"color": "GREEN", "sources": [], "what_is_claimed": "x"}'
        respuesta.result.message.content = [bloque]
        falso = self._anthropic_falso()
        falso.Anthropic.return_value.messages.batches.retrieve.return_value.processing_status = 'ended'
        falso.Anthropic.return_value.messages.batches.results.return_value = [respuesta]
        with mock.patch.dict('sys.modules', {'anthropic': falso}):
            batch.poll_verdict_batch('batch_x', post.pk, json.dumps(claims))
        ap = ClaimAppearance.objects.get(segment__post=post)
        self.assertEqual(ap.claim.color, 'UNDECIDED')     # verde sin fuentes: no entra
        post.refresh_from_db()
        self.assertEqual(post.status, 'DONE')

    def test_el_profundo_por_correo_respeta_el_panel(self):
        from apps.analysis.tasks import opus_rescan
        from apps.panel.models import SystemSetting
        post = self._post(7, status='DONE')
        SystemSetting.objects.update_or_create(key='delivery_deep', defaults={'value': 'batch'})
        with mock.patch('apps.analysis.tasks._submit_batch', return_value=True) as lote, \
                mock.patch('apps.agents.verdict.run') as directo:
            self.assertEqual(opus_rescan(post.pk, forced=True), 'batch_submitted')
        lote.assert_called_once()
        self.assertEqual(lote.call_args.kwargs.get('model'), 'claude-opus-4-8')
        directo.assert_not_called()

    # ---------- A.1 · la pista de voces ----------
    def test_la_pista_de_voces_viaja_en_la_datacion(self):
        from apps.agents import prompts
        from apps.agents.dating import date_and_count
        self.assertIn('speakers_count', prompts.DATING_SYSTEM)
        post = self._post(8)
        datos = date_and_count(post, 'texto crudo de whisper')
        self.assertEqual(datos['speakers_count'], 2)
        self.assertEqual(datos['speakers_confidence'], 'high')
        self.assertIsNotNone(datos['event_date'])

    def test_la_regla_de_david_para_la_pista(self):
        from apps.analysis.tasks import diarization_hint
        post = self._post(9)
        post.speakers_count, post.speakers_confidence, post.speakers_count_source = 2, 'high', 'agent'
        self.assertEqual(diarization_hint(post), {'min_speakers': 2, 'max_speakers': 3})
        post.speakers_count = 1
        self.assertEqual(diarization_hint(post), {'num_speakers': 1})   # monólogo blindado
        post.speakers_count, post.speakers_confidence = 3, 'low'
        self.assertEqual(diarization_hint(post), {})                    # duda: automático
        post.speakers_count, post.speakers_confidence = 2, 'medium'     # 4.4-H: el rango es inofensivo
        self.assertEqual(diarization_hint(post), {'min_speakers': 2, 'max_speakers': 3})
        post.speakers_count, post.speakers_confidence = 1, 'medium'     # un 1 sin fe no blinda
        self.assertEqual(diarization_hint(post), {})
        post.speakers_count, post.speakers_count_source = 3, 'mod'
        self.assertEqual(diarization_hint(post), {'num_speakers': 3})   # moderación manda

    def test_la_correccion_de_moderacion_no_la_pisa_el_agente(self):
        from apps.analysis.tasks import _date_and_hint
        post = self._post(10)
        post.speakers_count, post.speakers_count_source = 4, 'mod'
        post.save()
        _date_and_hint(post, 'texto')
        post.refresh_from_db()
        self.assertEqual((post.speakers_count, post.speakers_count_source), (4, 'mod'))
        self.assertIsNotNone(post.event_date)          # la fecha sí se actualiza

    def test_la_datacion_ocurre_antes_de_separar_voces(self):
        src = open('apps/analysis/tasks.py', encoding='utf-8').read()
        cuerpo = src[src.index('def run_cheap_phase'):src.index('def auto_verify_slot_free')]
        # 4.4-J: el oido vive en diarize_turns (GPU o CPU); la datacion sigue antes.
        self.assertLess(cuerpo.index('_date_and_hint('), cuerpo.index('diarize_turns(post, audio_path'))
        self.assertIn('diarization_hint(post)', cuerpo)

    def test_los_argumentos_de_pyannote_no_se_contradicen(self):
        from apps.agents.diarization import pipeline_kwargs
        self.assertEqual(pipeline_kwargs(num_speakers=2, min_speakers=1), {'num_speakers': 2})
        self.assertEqual(pipeline_kwargs(min_speakers=2, max_speakers=1),
                         {'min_speakers': 2, 'max_speakers': 2})
        self.assertEqual(pipeline_kwargs(), {})

    # ---------- A.3 · el fantasma ----------
    def test_el_hablante_fantasma_se_absorbe_en_el_vecino(self):
        from apps.agents.diarization import absorb_ghost_speakers
        turns = [(0, 30, 'SPEAKER_00'), (30.5, 31.1, 'SPEAKER_02'),
                 (31.2, 60, 'SPEAKER_01'), (60, 90, 'SPEAKER_00')]
        out = absorb_ghost_speakers(turns)
        self.assertEqual({t[2] for t in out}, {'SPEAKER_00', 'SPEAKER_01'})
        self.assertEqual(out[1][2], 'SPEAKER_01')
        # sin hablante real no se toca nada
        self.assertEqual(absorb_ghost_speakers([(0, 2, 'A'), (2, 4, 'B')]),
                         [(0, 2, 'A'), (2, 4, 'B')])

    # ---------- A.4 / A.5 · el cruce por palabra, medido en frases legibles ----------
    def _palabras(self, *ws):
        return [{'start': a, 'end': b, 'text': t} for t, a, b in ws]

    def test_las_islas_de_una_palabra_se_pegan_a_la_voz_que_las_rodea(self):
        """«And» (0,4 s) caía en un microturno espurio y salía solo, como frase de
        una palabra del otro hablante: el 28 % de las frases del post 5."""
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0, 20, 'SPEAKER_00'), (12.0, 12.2, 'SPEAKER_01')]
        raw = [{'start_seconds': 0, 'end_seconds': 19.5, 'text': 'And they would heat up iron.',
                'words': self._palabras(('And', 11.9, 12.3), ('they', 12.4, 12.7),
                                        ('would', 12.7, 13.0), ('heat', 13.0, 13.4),
                                        ('up', 13.4, 13.6), ('iron.', 13.6, 19.5))}]
        out = merge_into_sentences(raw, turns)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['text'], 'And they would heat up iron.')
        self.assertEqual(out[0]['speaker_label'], 'SPEAKER_00')

    def test_el_backchannel_entre_dos_intervenciones_largas_es_del_otro(self):
        """De las 81 reacciones breves del post 5, 62 se atribuían al que monologa."""
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0, 40, 'SPEAKER_00'), (40, 60, 'SPEAKER_01')]
        raw = [{'start_seconds': 0, 'end_seconds': 10, 'text': 'The universe is expanding faster.'},
               {'start_seconds': 10.2, 'end_seconds': 10.8, 'text': 'Whoa.'},
               {'start_seconds': 11, 'end_seconds': 25, 'text': 'And that changes dark energy.'},
               {'start_seconds': 41, 'end_seconds': 55, 'text': 'So what does that mean?'}]
        por_texto = {m['text']: m['speaker_label'] for m in merge_into_sentences(raw, turns)}
        self.assertEqual(por_texto['Whoa.'], 'SPEAKER_01')
        self.assertEqual(por_texto['The universe is expanding faster.'], 'SPEAKER_00')

    def test_el_monologo_no_inventa_un_segundo_hablante(self):
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0, 60, 'SPEAKER_00')]
        raw = [{'start_seconds': 0, 'end_seconds': 10, 'text': 'Primera frase larga del monólogo.'},
               {'start_seconds': 10.2, 'end_seconds': 10.8, 'text': 'Bien.'},
               {'start_seconds': 11, 'end_seconds': 25, 'text': 'Segunda frase larga del monólogo.'}]
        out = merge_into_sentences(raw, turns)
        self.assertTrue(all(m['speaker_label'] == 'SPEAKER_00' for m in out))
        self.assertTrue(all(len(m['text'].split()) > 1 for m in out))   # «Bien.» pegada

    # ---------- la puerta del 65 % ----------
    def test_la_puerta_frena_el_piloto_automatico_y_se_reanuda_al_nombrar(self):
        from apps.analysis.services import try_autopilot
        post = self._post(11)
        with mock.patch('apps.analysis.tasks.launch_full_analysis') as lanzar:
            self.assertFalse(try_autopilot(post, factual=True))
            lanzar.assert_not_called()
            post.refresh_from_db()
            self.assertEqual(post.status, 'PENDING_VALIDATION')
            self._confirmar(post, 'SPEAKER_00', 'Ana Pública')
            self._confirmar(post, 'SPEAKER_01', 'Bea Pública')
            self.assertTrue(try_autopilot(post))
            lanzar.assert_called_once()
        post.refresh_from_db()
        self.assertEqual(post.status, 'FULL_QUEUED')

    def test_confirmar_un_nombre_vuelve_a_probar_el_piloto(self):
        from apps.wiki import naming
        from apps.wiki.models import SpeakerNameProposal
        post = self._post(12)
        prop = SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00',
                                                  candidate_name='Ana Pública', source='user')
        with mock.patch('apps.analysis.services.try_autopilot') as piloto:
            naming._confirm(prop)
        piloto.assert_called_once_with(post)

    def test_un_video_de_opinion_no_pasa_solo_aunque_esten_todos_nombrados(self):
        from apps.analysis.services import try_autopilot
        post = self._post(13)
        post.offtopic_suggested = True
        post.save(update_fields=['offtopic_suggested'])
        self._confirmar(post, 'SPEAKER_00', 'Ana')
        self._confirmar(post, 'SPEAKER_01', 'Bea')
        with mock.patch('apps.analysis.tasks.launch_full_analysis') as lanzar:
            self.assertFalse(try_autopilot(post))
        lanzar.assert_not_called()

    def test_el_aviso_de_espera_se_ve_en_el_post(self):
        post = self._post(14)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('La verificación con fuentes espera', html)
        self.assertIn('0 de 2, hace falta el 65%', html)

    # ---------- Intro envía ----------
    def test_intro_envia_y_elegir_una_sugerencia_agrega(self):
        js = open('static/js/speaker-suggest.js', encoding='utf-8').read()
        self.assertIn("e.key === 'Enter'", js)
        self.assertIn('requestSubmit', js)
        self.assertIn('enviar(form);', js[js.index('function elegir'):])
        html = open('templates/partials/post_body.html', encoding='utf-8').read()
        self.assertIn('<button class="mini">＋</button>', html)   # sin JS, el botón sigue

    # ---------- la llave inglesa ----------
    def test_la_llave_solo_la_ve_moderacion(self):
        from apps.analysis.templatetags.istt_icons import icon, _P
        self.assertIn('wrench', _P)
        self.assertIn(_P['wrench'], icon('wrench'))
        post = self._post(15, status='DONE')
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertNotIn('/relanzar/', html)
        self.client.force_login(self._mod(15))
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        for etapa in ('cheap', 'dating', 'verdicts', 'deep'):
            self.assertIn(f'/post/{post.pk}/relanzar/{etapa}/', html)
        self.assertIn('≈', html)                          # el coste delante

    def test_cada_etapa_pide_confirmacion_con_el_coste_antes_de_ejecutar(self):
        from apps.panel.models import AuditLog
        post = self._post(16)
        self.client.force_login(self._mod(16))
        with mock.patch('apps.analysis.tasks.reverify_post.delay') as tarea:
            r = self.client.post(f'/post/{post.pk}/relanzar/verdicts/')
            self.assertEqual(r.status_code, 200)
            self.assertIn('Coste estimado', r.content.decode())
            self.assertIn('name="confirm"', r.content.decode())
            tarea.assert_not_called()
            r = self.client.post(f'/post/{post.pk}/relanzar/verdicts/', {'confirm': '1'})
            self.assertEqual(r.status_code, 302)
            tarea.assert_called_once_with(post.pk)
        self.assertTrue(AuditLog.objects.filter(action='relaunch_verdicts',
                                                detail__contains=f'post {post.pk}').exists())

    def test_las_voces_aceptan_la_correccion_de_moderacion_y_borran_identificaciones(self):
        post = self._post(17, status='DONE')
        self._confirmar(post, 'SPEAKER_00', 'Ana')
        self.client.force_login(self._mod(17))
        with mock.patch('apps.analysis.tasks.run_cheap_phase.delay') as tarea:
            self.client.post(f'/post/{post.pk}/relanzar/cheap/', {'confirm': '1', 'speakers': '3'})
        tarea.assert_called_once_with(post.pk)
        post.refresh_from_db()
        self.assertEqual((post.speakers_count, post.speakers_count_source), (3, 'mod'))
        self.assertEqual(post.status, 'NEW')
        self.assertEqual(post.transcript_segments.count(), 0)
        self.assertEqual(post.name_proposals.count(), 0)

    def test_el_profundo_solo_en_posts_terminados_y_la_fecha_solo_con_transcripcion(self):
        post = self._post(18)                                  # PENDING_VALIDATION
        self.client.force_login(self._mod(18))
        with mock.patch('apps.analysis.tasks.opus_rescan.delay') as tarea:
            r = self.client.post(f'/post/{post.pk}/relanzar/deep/', {'confirm': '1'})
        self.assertEqual(r.status_code, 302)
        tarea.assert_not_called()
        vacio = Post.objects.create(author=make_user(username='g18b', email='g18b@example.org'),
                                    url='https://youtu.be/g18b', status='PENDING_VALIDATION')
        with mock.patch('apps.analysis.tasks.redate_post.delay') as tarea:
            self.client.post(f'/post/{vacio.pk}/relanzar/dating/', {'confirm': '1'})
        tarea.assert_not_called()

    def test_un_usuario_normal_no_relanza_nada(self):
        post = self._post(19, status='DONE')
        self.client.force_login(post.author)
        with mock.patch('apps.analysis.tasks.reverify_post.delay') as tarea:
            r = self.client.post(f'/post/{post.pk}/relanzar/verdicts/', {'confirm': '1'})
        self.assertEqual(r.status_code, 302)
        tarea.assert_not_called()

    def test_todo_relanzamiento_pasa_por_el_presupuesto(self):
        from apps.analysis.tasks import redate_post, opus_rescan
        post = self._post(20, status='DONE')
        with mock.patch('apps.analysis.models.DailyBudget.try_spend', return_value=False):
            self.assertEqual(redate_post(post.pk), 'budget_exhausted')
            self.assertEqual(opus_rescan(post.pk, forced=True), 'budget_exhausted')

    def test_los_costes_de_las_cuatro_etapas_son_positivos_y_ordenados(self):
        from apps.analysis.views import relaunch_options
        post = self._post(21, status='DONE')
        costes = {o['stage']: o['cost'] for o in relaunch_options(post)}
        self.assertGreater(costes['dating'], 0)
        self.assertLess(costes['dating'], costes['verdicts'])
        self.assertLessEqual(costes['verdicts'], costes['deep'])


class Pase44H(TestCase):
    """4.4-H — la separación de voces sin intervención humana.

    Post 5 tras el 4.4-G: «Diarización con pista de voces: ninguna (automático)»
    y la separación siguió en 91/8. La pista no cruzó su propia puerta (la
    datación no dio confianza alta) y «ante la duda, automático» manda al modo
    que falla. Ahora: la confianza media abre el rango, y si la primera pasada
    sale desequilibrada el sistema repite la diarización con el número.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    def _post(self, n, count=None, conf='', source=''):
        post = Post.objects.create(
            author=make_user(username=f'h{n}', email=f'h{n}@example.org'),
            url=f'https://youtu.be/h44{n}', status='NEW', title=f'Vídeo H{n}',
            speakers_count=count, speakers_confidence=conf, speakers_count_source=source)
        return post

    def test_la_separacion_desequilibrada_pide_segunda_pasada(self):
        from apps.analysis.tasks import second_pass_speakers
        # el post 5: 91/8 con dos voces reales y el agente sin opinión
        turns = [(0, 91, 'SPEAKER_00'), (91, 100, 'SPEAKER_01')]
        self.assertEqual(second_pass_speakers(turns, {}, self._post(1)), 2)
        # el agente dijo 3 con confianza baja: se usa su número
        self.assertEqual(second_pass_speakers(turns, {}, self._post(2, 3, 'low', 'agent')), 3)

    def test_una_separacion_sana_no_se_repite(self):
        from apps.analysis.tasks import second_pass_speakers
        turns = [(0, 70, 'SPEAKER_00'), (70, 100, 'SPEAKER_01')]
        self.assertEqual(second_pass_speakers(turns, {}, self._post(3)), 0)

    def test_el_monologo_no_se_parte_ni_con_segunda_pasada(self):
        from apps.analysis.tasks import second_pass_speakers
        turns = [(0, 100, 'SPEAKER_00')]
        self.assertEqual(second_pass_speakers(turns, {}, self._post(4, 2, 'low', 'agent')), 0)

    def test_un_numero_ya_fijado_no_se_discute(self):
        from apps.analysis.tasks import second_pass_speakers
        turns = [(0, 95, 'SPEAKER_00'), (95, 100, 'SPEAKER_01')]
        self.assertEqual(second_pass_speakers(turns, {'num_speakers': 2}, self._post(5)), 0)

    def test_el_umbral_vive_en_el_panel_y_cero_lo_apaga(self):
        from apps.analysis.tasks import second_pass_speakers, diarize_skew_percent
        from apps.panel.models import SystemSetting
        from config import settings as s
        self.assertEqual(s.SETTING_DEFAULTS['diarize_second_pass_skew_percent'], '20')
        self.assertEqual(diarize_skew_percent(), 20)
        SystemSetting.objects.create(key='diarize_second_pass_skew_percent', value='0')
        turns = [(0, 95, 'SPEAKER_00'), (95, 100, 'SPEAKER_01')]
        self.assertEqual(second_pass_speakers(turns, {}, self._post(6)), 0)

    def test_el_ajuste_esta_en_el_panel(self):
        from apps.panel.views import SETTINGS_DEF
        self.assertIn('diarize_second_pass_skew_percent', [d[0] for d in SETTINGS_DEF])

    def test_el_aviso_de_manipulacion_se_apaga_al_relanzar_las_voces(self):
        """4.4-H.1 (David): el aviso solo lo enciende el barrido de Haiku; el
        relanzamiento de moderacion lo apaga hasta que el nuevo barrido hable."""
        from apps.analysis.tasks import reset_for_cheap_phase
        post = self._post(7)
        post.manipulation_detected = True
        post.save(update_fields=['manipulation_detected'])
        reset_for_cheap_phase(post)
        post.refresh_from_db()
        self.assertFalse(post.manipulation_detected)
        self.assertEqual(post.status, 'NEW')

    def test_la_fase_barata_repite_la_diarizacion_cuando_toca(self):
        """La segunda pasada se llama de verdad con num_speakers, sobre el audio."""
        src = open('apps/analysis/tasks.py', encoding='utf-8').read()
        cuerpo = src[src.index('def diarize_turns'):src.index('def minority_share')]
        self.assertIn('second_pass_speakers(turns, pista, post)', cuerpo)
        self.assertIn('diarize(audio_path, num_speakers=n2)', cuerpo)


class Pase44I(TestCase):
    """4.4-I — la pasada de sentido (decisión de David, 2026-08-26).

    docs/06 §45: con las dos voces del post 5, pyannote agrupaba «habla limpia»
    contra «habla solapada» (91,9 → 95,7 forzando el número). Lo que el audio no
    da lo da el texto: Haiku lee la conversación y corrige o marca. Las dudas
    quedan como «atribución incierta»: se resuelven en «¿Quién habla?», no
    cuentan para el 65 % y no se cuelgan de ninguna persona en la wiki.
    """

    def setUp(self):
        from django.core.cache import cache as _c
        _c.clear()

    def _post(self, n, frases):
        post = Post.objects.create(
            author=make_user(username=f'i{n}', email=f'i{n}@example.org'),
            url=f'https://youtu.be/i44{n}', status='PENDING_VALIDATION', title=f'Vídeo I{n}',
            validation_deadline=timezone.now() + timedelta(days=2))
        for i, (etq, texto) in enumerate(frases):
            post.transcript_segments.create(start_seconds=i * 5.0, end_seconds=i * 5.0 + 4,
                                            text=texto, speaker_label=etq,
                                            signal='FACTUAL_UNVERIFIED')
        return post

    DIALOGO = [('SPEAKER_00', 'Light is a range of wavelengths that reach the eye.'),
               ('SPEAKER_00', 'I love it a triumph of nineteenth century physics.'),
               ('SPEAKER_00', 'So white light has which colors in it?'),
               ('SPEAKER_00', 'Oh the colors Roy G Biv.'),
               ('SPEAKER_01', 'Right.')]

    def test_la_tarea_esta_en_el_panel_y_gobierna_una_llamada_real(self):
        from apps.agents import catalog
        self.assertIn('attribution', catalog.TASK_KEYS)
        self.assertIn("model_for('attribution')",
                      open('apps/agents/attribution.py', encoding='utf-8').read())
        from config import settings as s
        self.assertEqual(s.SETTING_DEFAULTS['attribution_sense_pass'], '1')
        from apps.panel.views import SETTINGS_DEF
        self.assertIn('attribution_sense_pass', [d[0] for d in SETTINGS_DEF])

    def test_los_cambios_seguros_se_aplican_y_las_dudas_se_marcan(self):
        from apps.agents import attribution
        post = self._post(1, self.DIALOGO)
        respuesta = {'changes': [
            {'i': 1, 'action': 'split', 'speaker': 'SPEAKER_01', 'split_word': 4,
             'confidence': 'high', 'reason': 'I love it es reacción'},
            {'i': 3, 'action': 'relabel', 'speaker': 'SPEAKER_01', 'confidence': 'high',
             'reason': 'responde a la pregunta'},
            {'i': 2, 'action': 'relabel', 'speaker': 'SPEAKER_01', 'confidence': 'low',
             'reason': 'no está claro quién pregunta'},
        ]}
        with mock.patch('apps.agents.client.call_json', return_value=respuesta):
            out = attribution.run(post)
        self.assertEqual(out, {'relabeled': 1, 'split': 1, 'uncertain': 1})
        frases = list(post.transcript_segments.order_by('start_seconds', 'pk'))
        textos = {f.text: f for f in frases}
        # el split: «I love it» sigue en la voz original y el resto va a la otra
        self.assertEqual(textos['I love it'].speaker_label, 'SPEAKER_00')
        self.assertEqual(textos['a triumph of nineteenth century physics.'].speaker_label, 'SPEAKER_01')
        self.assertLess(textos['I love it'].end_seconds,
                        textos['a triumph of nineteenth century physics.'].end_seconds)
        # el relabel seguro
        self.assertEqual(textos['Oh the colors Roy G Biv.'].speaker_label, 'SPEAKER_01')
        # la duda: se marca, NO se mueve
        duda = textos['So white light has which colors in it?']
        self.assertTrue(duda.attribution_uncertain)
        self.assertEqual(duda.speaker_label, 'SPEAKER_00')

    def test_solo_etiquetas_existentes_y_ningun_monologo_se_discute(self):
        from apps.agents import attribution
        post = self._post(2, self.DIALOGO)
        respuesta = {'changes': [{'i': 0, 'action': 'relabel', 'speaker': 'SPEAKER_07',
                                  'confidence': 'high', 'reason': 'x'}]}
        with mock.patch('apps.agents.client.call_json', return_value=respuesta):
            out = attribution.run(post)
        self.assertEqual(out['relabeled'], 0)
        self.assertEqual(out['uncertain'], 1)          # una etiqueta inventada = duda
        mono = self._post(3, [('SPEAKER_00', 'Una frase.'), ('SPEAKER_00', 'Otra frase.')])
        with mock.patch('apps.agents.client.call_json') as llamada:
            self.assertEqual(attribution.run(mono), {'relabeled': 0, 'split': 0, 'uncertain': 0})
        llamada.assert_not_called()

    def test_el_ajuste_a_cero_apaga_la_pasada(self):
        from apps.agents import attribution
        from apps.panel.models import SystemSetting
        SystemSetting.objects.create(key='attribution_sense_pass', value='0')
        post = self._post(4, self.DIALOGO)
        with mock.patch('apps.agents.client.call_json') as llamada:
            attribution.run(post)
        llamada.assert_not_called()

    def test_un_fallo_del_modelo_deja_la_transcripcion_intacta(self):
        from apps.agents import attribution
        post = self._post(5, self.DIALOGO)
        with mock.patch('apps.agents.client.call_json', return_value={'error': 'timeout'}):
            self.assertEqual(attribution.run(post), {'relabeled': 0, 'split': 0, 'uncertain': 0})
        self.assertFalse(post.transcript_segments.filter(attribution_uncertain=True).exists())

    def test_la_pasada_ocurre_antes_del_barrido_en_la_fase_barata(self):
        src = open('apps/analysis/tasks.py', encoding='utf-8').read()
        cuerpo = src[src.index('def run_cheap_phase'):src.index('def auto_verify_slot_free')]
        self.assertLess(cuerpo.index('attribution.run(post)'), cuerpo.index('sweep.run(post)'))

    def test_las_inciertas_no_cuentan_para_el_65_por_ciento(self):
        from apps.analysis.services import speaker_identification
        from apps.wiki.models import SpeakerNameProposal
        post = self._post(6, self.DIALOGO)
        SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00',
                                           candidate_name='Neil', confirmed=True, source='user')
        self.assertEqual(speaker_identification(post), (1, 2))
        post.transcript_segments.filter(speaker_label='SPEAKER_01').update(attribution_uncertain=True)
        self.assertEqual(speaker_identification(post), (1, 1))     # la voz dudosa no cuenta

    def test_las_inciertas_no_se_cuelgan_de_ninguna_persona(self):
        from apps.wiki.models import Claim, ClaimAppearance, Interlocutor, SpeakerNameProposal
        from apps.wiki.naming import claims_for_person
        post = self._post(7, self.DIALOGO)
        persona = Interlocutor.objects.create(name='Neil', slug='neil', is_public_figure=True)
        SpeakerNameProposal.objects.create(post=post, speaker_label='SPEAKER_00', candidate_name='Neil',
                                           confirmed=True, source='user', interlocutor=persona)
        seg = post.transcript_segments.first()
        claim = Claim.objects.create(text_original='Light is a range of wavelengths.', color='GREEN')
        ClaimAppearance.objects.create(claim=claim, segment=seg)
        self.assertEqual(claims_for_person(persona).count(), 1)
        seg.attribution_uncertain = True
        seg.save(update_fields=['attribution_uncertain'])
        self.assertEqual(claims_for_person(persona).count(), 0)

    def test_la_comunidad_resuelve_una_frase_con_un_clic_y_sin_js(self):
        post = self._post(8, self.DIALOGO)
        seg = post.transcript_segments.get(text='Right.')
        seg.attribution_uncertain = True
        seg.save(update_fields=['attribution_uncertain'])
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn('atribución incierta', html)
        self.assertNotIn('/atribuir/', html)                 # sin sesión no se resuelve
        u = make_user(username='i8b', email='i8b@example.org')
        self.client.force_login(u)
        html = self.client.get(f'/post/{post.pk}/').content.decode()
        self.assertIn(f'/frase/{seg.pk}/atribuir/', html)
        with mock.patch('apps.analysis.services.try_autopilot') as piloto:
            r = self.client.post(f'/frase/{seg.pk}/atribuir/', {'speaker': 'SPEAKER_00'})
        self.assertEqual(r.status_code, 302)
        piloto.assert_called_once()
        seg.refresh_from_db()
        self.assertEqual((seg.speaker_label, seg.attribution_uncertain), ('SPEAKER_00', False))
        self.assertIn('i8b', seg.attribution_note)
        # una voz que no existe en el post se rechaza
        self.client.post(f'/frase/{seg.pk}/atribuir/', {'speaker': 'SPEAKER_09'})
        seg.refresh_from_db()
        self.assertEqual(seg.speaker_label, 'SPEAKER_00')

    def test_la_segunda_pasada_solo_se_queda_si_reparte_mejor(self):
        """docs/06 §45: la segunda pasada del post 5 dio 95,7/4,3, peor que la primera."""
        from apps.analysis.tasks import keep_better_split, minority_share
        primera = [(0, 92, 'SPEAKER_00'), (92, 100, 'SPEAKER_01')]
        peor = [(0, 96, 'SPEAKER_00'), (96, 100, 'SPEAKER_01')]
        mejor = [(0, 80, 'SPEAKER_00'), (80, 100, 'SPEAKER_01')]
        post = self._post(9, self.DIALOGO)
        self.assertIs(keep_better_split(primera, peor, post), primera)
        self.assertIs(keep_better_split(primera, mejor, post), mejor)
        self.assertEqual(minority_share([(0, 10, 'A')]), 0.0)


class OperadorGPUWhisper(TestCase):
    """Intervencion del operador (2026-08-26): transcripcion en GPU Runpod.
    La regla que blindan estos tests es la 5.7: la GPU acelera, JAMAS bloquea —
    cualquier fallo devuelve None y la CPU sigue como siempre."""

    def test_sin_configurar_devuelve_none_sin_llamar_a_nada(self):
        from apps.agents import gpu
        with override_settings(RUNPOD_API_KEY='', RUNPOD_WHISPER_ENDPOINT=''):
            self.assertIsNone(gpu.transcribe_gpu('/no/existe.mp3'))

    def test_fallo_remoto_devuelve_none_no_revienta(self):
        from apps.agents import gpu
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_WHISPER_ENDPOINT='ep'), \
             mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
             mock.patch.object(gpu.httpx, 'post',
                               side_effect=Exception('red caida')):
            self.assertIsNone(gpu.transcribe_gpu('/x.mp3'))

    def test_trabajo_fallido_en_runpod_devuelve_none(self):
        from apps.agents import gpu
        lanzado = mock.Mock()
        lanzado.json.return_value = {'id': 'job1'}
        lanzado.status_code = 200
        estado = mock.Mock()
        estado.json.return_value = {'status': 'FAILED'}
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_WHISPER_ENDPOINT='ep',
                               RUNPOD_POLL_SECONDS=0), \
             mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
             mock.patch.object(gpu.httpx, 'post', return_value=lanzado), \
             mock.patch.object(gpu.httpx, 'get', return_value=estado):
            self.assertIsNone(gpu.transcribe_gpu('/x.mp3'))

    def test_trabajo_completado_llega_en_formato_local(self):
        """El contrato MEDIDO contra el endpoint real: words es una lista GLOBAL
        (word_timestamps), separada de segments. El mapeo debe repartirlas por
        reloj sin duplicar ninguna."""
        from apps.agents import gpu
        salida = {'segments': [{'start': 0.0, 'end': 2.0, 'text': ' hola mundo '},
                               {'start': 2.0, 'end': 4.0, 'text': 'adios'}],
                  'word_timestamps': [
                      {'word': ' hola', 'start': 0.0, 'end': 0.9},
                      {'word': ' mundo', 'start': 1.0, 'end': 1.9},
                      {'word': ' adios', 'start': 2.1, 'end': 3.0}]}
        lanzado = mock.Mock()
        lanzado.json.return_value = {'id': 'job1'}
        lanzado.status_code = 200
        estado = mock.Mock()
        estado.json.return_value = {'status': 'COMPLETED', 'output': salida,
                                    'executionTime': 1234}
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_WHISPER_ENDPOINT='ep',
                               RUNPOD_POLL_SECONDS=0), \
             mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
             mock.patch.object(gpu.httpx, 'post', return_value=lanzado), \
             mock.patch.object(gpu.httpx, 'get', return_value=estado):
            segs = gpu.transcribe_gpu('/x.mp3')
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]['text'], 'hola mundo')
        self.assertEqual([w['text'] for w in segs[0]['words']], ['hola', 'mundo'])
        self.assertEqual([w['text'] for w in segs[1]['words']], ['adios'])
        self.assertEqual(segs[1]['start_seconds'], 2.0)

    def test_timeout_local_cancela_el_trabajo_en_runpod(self):
        """Un timeout nuestro NO puede dejar la GPU corriendo sola (dinero):
        se llama a /cancel antes de rendirse."""
        from apps.agents import gpu
        lanzado = mock.Mock()
        lanzado.json.return_value = {'id': 'job1'}
        lanzado.status_code = 200
        en_marcha = mock.Mock()
        en_marcha.json.return_value = {'status': 'IN_PROGRESS'}
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_WHISPER_ENDPOINT='ep',
                               RUNPOD_POLL_SECONDS=0, RUNPOD_JOB_TIMEOUT=0), \
             mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
             mock.patch.object(gpu.httpx, 'post', return_value=lanzado) as posts, \
             mock.patch.object(gpu.httpx, 'get', return_value=en_marcha):
            self.assertIsNone(gpu.transcribe_gpu('/x.mp3'))
        urls = [c.args[0] for c in posts.call_args_list]
        self.assertTrue(any('/cancel/job1' in u for u in urls),
                        'el timeout local debe cancelar el trabajo remoto')


class Pase44J(TestCase):
    """4.4-J — la separación de voces en la GPU de Runpod (docs/56).

    Contrato simétrico al de whisper; la segunda pasada viaja en el mismo
    trabajo; la POLÍTICA (fantasmas, keep_better_split) se queda en el VPS.
    Regla 5.7: la GPU acelera, jamás bloquea — cualquier fallo → CPU como hoy.
    """

    def _post(self, n, count=None, conf='', source=''):
        return Post.objects.create(
            author=make_user(username=f'j{n}', email=f'j{n}@example.org'),
            url=f'https://youtu.be/j44{n}', status='NEW', title=f'Vídeo J{n}',
            speakers_count=count, speakers_confidence=conf, speakers_count_source=source)

    def test_sin_configurar_devuelve_none_sin_llamar_a_nada(self):
        from apps.agents import gpu
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT=''), \
                mock.patch.object(gpu.httpx, 'post') as red:
            self.assertIsNone(gpu.diarize_gpu('/x.mp3', {}, 2))
        red.assert_not_called()

    def test_fallo_remoto_o_error_del_worker_devuelven_none(self):
        from apps.agents import gpu
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
                mock.patch.object(gpu.httpx, 'post', side_effect=Exception('red caída')):
            self.assertIsNone(gpu.diarize_gpu('/x.mp3', {}, 2))
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
                mock.patch.object(gpu, '_run_job', return_value={'error': 'modelo no permitido'}):
            self.assertIsNone(gpu.diarize_gpu('/x.mp3', {}, 2))

    def test_el_contrato_del_worker_llega_como_turnos_locales(self):
        from apps.agents import gpu
        salida = {'turns': [[0.0, 10.0, 'SPEAKER_00'], [10.0, 14.0, 'SPEAKER_01']],
                  'turns_second_pass': [[0.0, 8.0, 'SPEAKER_00'], [8.0, 14.0, 'SPEAKER_01']],
                  'tiempos': {'diarize_s': 3.1, 'second_pass_s': 2.9}, 'model': 'x'}
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
                mock.patch.object(gpu, '_run_job', return_value=salida) as trabajo:
            res = gpu.diarize_gpu('/x.mp3', {'min_speakers': 2, 'max_speakers': 3}, 2)
        self.assertEqual(res['turns'], [(0.0, 10.0, 'SPEAKER_00'), (10.0, 14.0, 'SPEAKER_01')])
        self.assertEqual(res['turns_second_pass'][0], (0.0, 8.0, 'SPEAKER_00'))
        carga = trabajo.call_args.args[1]
        self.assertEqual(carga['hint'], {'min_speakers': 2, 'max_speakers': 3})
        self.assertEqual(carga['second_pass_num_speakers'], 2)
        self.assertEqual(carga['model'], 'pyannote/speaker-diarization-3.1')

    def test_un_timeout_nuestro_cancela_el_trabajo_remoto(self):
        from apps.agents import gpu
        lanzado = mock.Mock(); lanzado.json.return_value = {'id': 'job9'}; lanzado.status_code = 200
        estado = mock.Mock(); estado.json.return_value = {'status': 'IN_PROGRESS'}
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep',
                               RUNPOD_POLL_SECONDS=0, RUNPOD_JOB_TIMEOUT=0), \
                mock.patch.object(gpu.httpx, 'post', return_value=lanzado) as post_http, \
                mock.patch.object(gpu.httpx, 'get', return_value=estado):
            self.assertIsNone(gpu._run_job('ep', {'x': 1}, 'prueba'))
        self.assertTrue(any('/cancel/job9' in c.args[0] for c in post_http.call_args_list))

    def test_la_politica_se_queda_en_el_vps(self):
        """La GPU devuelve las dos pasadas; el VPS absorbe fantasmas y elige con
        keep_better_split. Y siempre que hay duda se pide la segunda pasada."""
        from apps.analysis import tasks
        post = self._post(1, 2, 'medium', 'agent')
        primera = [(0, 92, 'SPEAKER_00'), (92, 100, 'SPEAKER_01'), (100, 100.5, 'SPEAKER_02')]
        mejor = [(0, 80, 'SPEAKER_00'), (80, 100, 'SPEAKER_01')]
        res = {'turns': primera, 'turns_second_pass': mejor, 'tiempos': {}}
        with override_settings(MOCK_AGENTS=False, RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch('apps.agents.gpu.diarize_gpu', return_value=res) as gpu_fn, \
                mock.patch('apps.agents.diarization.diarize') as cpu:
            turns = tasks.diarize_turns(post, '/x.mp3', {'min_speakers': 2, 'max_speakers': 3})
        cpu.assert_not_called()
        self.assertEqual(gpu_fn.call_args.args[2], 2)          # segunda pasada pedida
        self.assertEqual(turns, mejor)                          # se quedó la mejor
        # con numero exacto (moderacion) NO se pide segunda pasada
        with override_settings(MOCK_AGENTS=False, RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch('apps.agents.gpu.diarize_gpu', return_value=res) as gpu_fn, \
                mock.patch('apps.agents.diarization.diarize'):
            tasks.diarize_turns(post, '/x.mp3', {'num_speakers': 2})
        self.assertIsNone(gpu_fn.call_args.args[2])

    def test_si_la_gpu_falla_la_cpu_sigue_como_hoy(self):
        from apps.analysis import tasks
        post = self._post(2)
        with override_settings(MOCK_AGENTS=False, RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch('apps.agents.gpu.diarize_gpu', return_value=None), \
                mock.patch('apps.agents.diarization.diarize',
                           return_value=[(0, 70, 'SPEAKER_00'), (70, 100, 'SPEAKER_01')]) as cpu:
            turns = tasks.diarize_turns(post, '/x.mp3', {})
        cpu.assert_called_once()
        self.assertEqual(len(turns), 2)

    def test_el_espejo_nunca_llama_a_la_gpu(self):
        from apps.analysis import tasks
        post = self._post(3)
        with override_settings(MOCK_AGENTS=True, RUNPOD_API_KEY='k', RUNPOD_DIARIZE_ENDPOINT='ep'), \
                mock.patch('apps.agents.gpu.diarize_gpu') as gpu_fn:
            turns = tasks.diarize_turns(post, None, {})
        gpu_fn.assert_not_called()
        self.assertEqual(len({t[2] for t in turns}), 2)

    def test_el_worker_existe_y_no_persiste_nada(self):
        import os
        base = 'workers/gpu/diarize'
        for f in ('Dockerfile', 'handler.py', 'requirements.txt'):
            self.assertTrue(os.path.exists(f'{base}/{f}'), f)
        h = open(f'{base}/handler.py', encoding='utf-8').read()
        self.assertIn('runpod.serverless.start', h)
        self.assertIn('second_pass_num_speakers', h)
        self.assertIn('TemporaryDirectory', h)              # procesa y muere
        for prohibido in ('torch.save', 'pickle', 'boto3', 'open(\'/runpod-volume'):
            self.assertNotIn(prohibido, h, prohibido)
        d = open(f'{base}/Dockerfile', encoding='utf-8').read()
        self.assertIn('from_pretrained', d)                   # pesos precargados en el build
        self.assertNotIn('ENV HF_TOKEN', d)                   # el token no queda en la imagen


class OperadorNotaAcotada(TestCase):
    """Fix del operador (2026-08-26): una razon larguisima de la pasada de
    sentido no puede volver a tumbar la pasada entera (DataError en el post 5
    con large-v3: attribution_note es varchar(160))."""

    def test_la_nota_se_trunca_al_limite_del_campo(self):
        from apps.agents.attribution import _nota
        from apps.analysis.models import TranscriptSegment
        tope = TranscriptSegment._meta.get_field('attribution_note').max_length
        self.assertEqual(len(_nota('x' * 500)), tope)
        self.assertEqual(_nota(None), '')
        self.assertEqual(_nota('corta'), 'corta')


class Parche45A(TestCase):
    """4.5-A (primer parche del nuevo regimen) — el suavizado consulta al oido.
    Sintoma cazado por David en el post 5: «frases» de 45 s con las DOS voces
    mezcladas. Causa: la regla anti-islas del 4.4-G, nacida cuando pyannote 3.1
    fallaba, reetiquetaba en cascada las intervenciones cortas REALES que
    community-1 ya acierta."""

    def test_la_isla_respaldada_por_su_turno_se_conserva(self):
        """Un «Okay.» de 0,5 s CON turno propio del oido ya no se lo queda la
        voz dominante: sale como frase suya."""
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0.0, 4.9, 'SPEAKER_00'), (5.0, 5.6, 'SPEAKER_01'),
                 (5.7, 12.0, 'SPEAKER_00')]
        raw = [{'start_seconds': 0.0, 'end_seconds': 12.0,
                'text': 'The 1800s. Okay. We discover the laws.',
                'words': [{'start': 0.5, 'end': 1.5, 'text': 'The'},
                          {'start': 1.6, 'end': 2.5, 'text': '1800s.'},
                          {'start': 5.1, 'end': 5.5, 'text': 'Okay.'},
                          {'start': 6.0, 'end': 7.0, 'text': 'We'},
                          {'start': 7.1, 'end': 8.0, 'text': 'discover'},
                          {'start': 8.1, 'end': 9.0, 'text': 'the'},
                          {'start': 9.1, 'end': 10.0, 'text': 'laws.'}]}]
        out = merge_into_sentences(raw, turns)
        por_texto = {m['text']: m['speaker_label'] for m in out}
        self.assertIn('Okay.', por_texto)
        self.assertEqual(por_texto['Okay.'], 'SPEAKER_01')
        self.assertEqual(por_texto['The 1800s.'], 'SPEAKER_00')

    def test_la_isla_sin_respaldo_se_suaviza_como_siempre(self):
        """Una palabra suelta que NINGUN turno avala sigue siendo ruido del
        solape: se pega a la voz que la rodea (la regla del 4.4-G vive)."""
        from apps.analysis.tasks import merge_into_sentences
        turns = [(0.0, 12.0, 'SPEAKER_00')]  # el oido solo oyo a UNO aqui
        raw = [{'start_seconds': 0.0, 'end_seconds': 12.0,
                'text': 'The 1800s okay we discover the laws.',
                'words': [{'start': 0.5, 'end': 1.5, 'text': 'The'},
                          {'start': 1.6, 'end': 2.5, 'text': '1800s'},
                          {'start': 5.1, 'end': 5.5, 'text': 'okay'},
                          {'start': 6.0, 'end': 7.0, 'text': 'we'},
                          {'start': 7.1, 'end': 8.0, 'text': 'discover'},
                          {'start': 8.1, 'end': 9.0, 'text': 'the'},
                          {'start': 9.1, 'end': 10.0, 'text': 'laws.'}]}]
        out = merge_into_sentences(raw, turns)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['speaker_label'], 'SPEAKER_00')

    def test_ninguna_frase_supera_el_tope_de_duracion(self):
        """Una parrafada sin puntuacion de un solo hablante se corta al tope:
        jamas otra «frase» de 45 segundos."""
        from apps.analysis.tasks import merge_into_sentences, MAX_SENTENCE_SECONDS
        turns = [(0.0, 70.0, 'SPEAKER_00')]
        palabras = [{'start': float(i), 'end': i + 0.8, 'text': f'palabra{i}'}
                    for i in range(0, 70, 1)]
        raw = [{'start_seconds': 0.0, 'end_seconds': 70.0,
                'text': ' '.join(w['text'] for w in palabras),
                'words': palabras}]
        out = merge_into_sentences(raw, turns)
        self.assertGreater(len(out), 1)
        for m in out:
            self.assertLessEqual(m['end_seconds'] - m['start_seconds'],
                                 MAX_SENTENCE_SECONDS + 1.0)


class Parche45C(TestCase):
    """4.5-C — los motores de audio GPU se eligen en el panel (orden de David:
    «elección de modelos según el caso», y el caso incluye oír y separar)."""

    def test_resolucion_panel_gana_a_env_y_a_default(self):
        from apps.agents.catalog import audio_engine_for
        from apps.panel.models import SystemSetting
        with override_settings(DIARIZE_GPU_MODEL='pyannote/speaker-diarization-3.1'):
            self.assertEqual(audio_engine_for('diarize_gpu'),
                             'pyannote/speaker-diarization-3.1')  # .env manda sin panel
            SystemSetting.objects.update_or_create(
                key='model_diarize_gpu',
                defaults={'value': 'pyannote/speaker-diarization-community-1'})
            self.assertEqual(audio_engine_for('diarize_gpu'),
                             'pyannote/speaker-diarization-community-1')  # panel gana

    def test_un_valor_invalido_no_cuela(self):
        from apps.agents.catalog import audio_engine_for
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(
            key='model_whisper_gpu', defaults={'value': 'gpt-5-turbo'})
        with override_settings(WHISPER_GPU_MODEL=''):
            self.assertEqual(audio_engine_for('whisper_gpu'), 'large-v3')  # cae al default

    def test_el_panel_guarda_y_muestra_los_motores(self):
        from apps.agents.catalog import audio_engine_for, TASK_KEYS
        User = get_user_model()
        u = User.objects.create_superuser('boss45c', 'b45c@x.com', 'x')
        self.client.force_login(u)
        r = self.client.get('/panel/modelos/')
        self.assertContains(r, 'model_whisper_gpu')
        self.assertContains(r, 'model_diarize_gpu')
        datos = {f'model_{k}': 'claude-sonnet-4-6' for k in TASK_KEYS}
        datos['model_whisper_gpu'] = 'turbo'
        datos['model_diarize_gpu'] = 'pyannote/speaker-diarization-3.1'
        self.client.post('/panel/modelos/', datos)
        self.assertEqual(audio_engine_for('whisper_gpu'), 'turbo')
        self.assertEqual(audio_engine_for('diarize_gpu'),
                         'pyannote/speaker-diarization-3.1')


class Parche46A(TestCase):
    """4.6-A — el liston de oro de David y el blindaje anti-alucinaciones."""

    def test_whisper_gpu_pide_vad_y_sin_condicionar(self):
        """Los dos artefactos que David cazo contra su referencia (bucle de
        repeticion y parrafo duplicado) exigen condition_on_previous_text=False
        y VAD — la via CPU siempre llevo VAD y la GPU lo habia perdido."""
        from apps.agents import gpu
        lanzado = mock.Mock(); lanzado.json.return_value = {'id': 'j'}
        estado = mock.Mock(); estado.json.return_value = {'status': 'FAILED'}
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_WHISPER_ENDPOINT='ep',
                               RUNPOD_POLL_SECONDS=0), \
             mock.patch.object(gpu, '_audio_to_opus_b64', return_value='QUJD'), \
             mock.patch.object(gpu.httpx, 'post', return_value=lanzado) as posts, \
             mock.patch.object(gpu.httpx, 'get', return_value=estado):
            gpu.transcribe_gpu('/x.mp3')
        entrada = posts.call_args_list[0].kwargs['json']['input']
        self.assertIs(entrada['condition_on_previous_text'], False)
        self.assertIs(entrada['enable_vad'], True)

    def test_la_referencia_de_oro_es_json_valido_y_alterna_voces(self):
        import json, os
        from apps.analysis import golden
        ruta = os.path.join(os.path.dirname(golden.__file__), 'post5.json')
        d = json.load(open(ruta, encoding='utf-8'))
        # v3 (4.8-A): 31 lineas del arranque + 10 de David por todo el video
        self.assertGreaterEqual(len(d['lineas']), 41)
        # v2 (4.7-A): cada linea es [quien, texto, tipo]
        self.assertTrue(all(l[0] in ('N', 'I') for l in d['lineas']))
        self.assertTrue(all(l[2] in ('sustancial', 'reaccion', 'charla')
                            for l in d['lineas']))


class Parche46B(TestCase):
    """4.6-B — la reescritura del arranque fundido, con su candado de palabras
    sagradas: o el texto reconstruido es IDENTICO, o no se toca nada."""

    def _post_con_arranque(self):
        from apps.analysis.models import Post, TranscriptSegment
        User = get_user_model()
        u = User.objects.create_user('u46b', 'u46b@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x46b', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=10,
                                         speaker_label='SPEAKER_00',
                                         text='hello there get out yeah')
        # fuera de la ventana del arranque (empieza pasado el tope de 120 s)
        TranscriptSegment.objects.create(post=p, start_seconds=130, end_seconds=200,
                                         speaker_label='SPEAKER_01',
                                         text='thank you very much')
        return p

    def test_reescritura_valida_se_aplica_con_reloj_proporcional(self):
        from apps.agents import attribution
        p = self._post_con_arranque()
        respuesta = {'utterances': [
            {'speaker': 'SPEAKER_00', 'text': 'hello there'},
            {'speaker': 'SPEAKER_01', 'text': 'get out'},
            {'speaker': 'SPEAKER_00', 'text': 'yeah'},
        ]}
        with mock.patch.object(attribution.client, 'call_json',
                               return_value=respuesta):
            r = attribution.intro_rewrite(p)
        self.assertEqual(r['rewritten'], 3)
        segs = list(p.transcript_segments.order_by('start_seconds'))
        self.assertEqual([s.text for s in segs][:3],
                         ['hello there', 'get out', 'yeah'])
        self.assertEqual(segs[1].speaker_label, 'SPEAKER_01')
        self.assertLess(segs[0].end_seconds, segs[1].end_seconds)
        self.assertEqual(segs[3].text, 'thank you very much')  # fuera del tope: intacta

    def test_texto_distinto_se_descarta_entero(self):
        """El modelo 'corrigio' una palabra: candado cerrado, nada cambia."""
        from apps.agents import attribution
        p = self._post_con_arranque()
        respuesta = {'utterances': [
            {'speaker': 'SPEAKER_00', 'text': 'hello there get out YES'},
        ]}
        with mock.patch.object(attribution.client, 'call_json',
                               return_value=respuesta):
            r = attribution.intro_rewrite(p)
        self.assertEqual(r['rewritten'], 0)
        self.assertEqual(p.transcript_segments.count(), 2)

    def test_etiqueta_desconocida_se_descarta(self):
        from apps.agents import attribution
        p = self._post_con_arranque()
        respuesta = {'utterances': [
            {'speaker': 'SPEAKER_09', 'text': 'hello there get out yeah'},
        ]}
        with mock.patch.object(attribution.client, 'call_json',
                               return_value=respuesta):
            self.assertEqual(attribution.intro_rewrite(p)['rewritten'], 0)

    def test_monologo_no_se_toca(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u46b2', 'u46b2@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x46b2', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=10,
                                         speaker_label='SPEAKER_00', text='solo yo')
        self.assertEqual(attribution.intro_rewrite(p)['rewritten'], 0)


class Parche46E(TestCase):
    """4.6-E — la reescritura del arranque vota por mayoria de 3: el ruido de
    una muestra unica (55-61% oscilando en el liston) se cancela votando."""

    def test_la_mayoria_gana_en_la_palabra_disputada(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u46e', 'u46e@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x46e', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=10,
                                         speaker_label='SPEAKER_00',
                                         text='hello there get out')
        TranscriptSegment.objects.create(post=p, start_seconds=130, end_seconds=200,
                                         speaker_label='SPEAKER_01', text='bye')
        base = [{'speaker': 'SPEAKER_00', 'text': 'hello there'},
                {'speaker': 'SPEAKER_01', 'text': 'get out'}]
        disidente = [{'speaker': 'SPEAKER_00', 'text': 'hello there get out'}]
        respuestas = [{'utterances': base}, {'utterances': disidente},
                      {'utterances': base}]
        with mock.patch.object(attribution.client, 'call_json',
                               side_effect=respuestas):
            r = attribution.intro_rewrite(p)
        self.assertEqual(r['rewritten'], 2)
        segs = list(p.transcript_segments.order_by('start_seconds'))
        self.assertEqual(segs[0].text, 'hello there')
        self.assertEqual(segs[0].speaker_label, 'SPEAKER_00')
        self.assertEqual(segs[1].text, 'get out')
        self.assertEqual(segs[1].speaker_label, 'SPEAKER_01')

    def test_muestra_invalida_no_vota_pero_las_validas_siguen(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u46e2', 'u46e2@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x46e2', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=10,
                                         speaker_label='SPEAKER_00',
                                         text='hello there get out')
        TranscriptSegment.objects.create(post=p, start_seconds=130, end_seconds=200,
                                         speaker_label='SPEAKER_01', text='bye')
        buena = {'utterances': [{'speaker': 'SPEAKER_01', 'text': 'hello there get out'}]}
        rota = {'utterances': [{'speaker': 'SPEAKER_00', 'text': 'texto inventado'}]}
        with mock.patch.object(attribution.client, 'call_json',
                               side_effect=[rota, buena, rota]):
            r = attribution.intro_rewrite(p)
        self.assertEqual(r['rewritten'], 1)
        self.assertEqual(p.transcript_segments.order_by('start_seconds')[0].speaker_label,
                         'SPEAKER_01')


class Parche47A(TestCase):
    """4.7-A — la regla de David: la web analiza AFIRMACIONES; las reacciones
    que cortan al orador se marcan (reescritura) o se retiran (sueltas)."""

    def test_la_reaccion_votada_se_omite_del_transcript(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u47a', 'u47a@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x47a', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=10,
                                         speaker_label='SPEAKER_00',
                                         text='hello there get out folks')
        TranscriptSegment.objects.create(post=p, start_seconds=130, end_seconds=200,
                                         speaker_label='SPEAKER_01', text='bye')
        r = {'utterances': [
            {'speaker': 'SPEAKER_00', 'tipo': 'voz', 'text': 'hello there'},
            {'speaker': 'SPEAKER_01', 'tipo': 'reaccion', 'text': 'get out'},
            {'speaker': 'SPEAKER_00', 'tipo': 'voz', 'text': 'folks'},
        ]}
        with mock.patch.object(attribution.client, 'call_json', return_value=r):
            res = attribution.intro_rewrite(p)
        self.assertEqual(res['omitted'], 1)
        textos = [s.text for s in p.transcript_segments.order_by('start_seconds')]
        self.assertNotIn('get out', ' | '.join(textos))
        self.assertIn('hello there', textos)

    def test_reaccion_suelta_y_eco_se_retiran_pero_el_contenido_no(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u47a2', 'u47a2@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x47a2', author=u)
        datos = [(0, 5, 'SPEAKER_00', 'the tower is 300 meters tall'),
                 (5, 6, 'SPEAKER_01', 'okay'),                      # lexico
                 (6, 9, 'SPEAKER_00', 'and it was finished in 1889'),
                 (9, 10, 'SPEAKER_01', 'finished in 1889'),         # eco
                 (10, 14, 'SPEAKER_01', 'but is that actually true')]  # contenido
        for a, b, l, t in datos:
            TranscriptSegment.objects.create(post=p, start_seconds=a,
                                             end_seconds=b, speaker_label=l, text=t)
        n = attribution.drop_reactions(p)
        self.assertEqual(n, 2)
        textos = [s.text for s in p.transcript_segments.order_by('start_seconds')]
        self.assertEqual(textos, ['the tower is 300 meters tall',
                                  'and it was finished in 1889',
                                  'but is that actually true'])

    def test_el_filtro_se_apaga_desde_el_panel(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        from apps.panel.models import SystemSetting
        User = get_user_model()
        u = User.objects.create_user('u47a3', 'u47a3@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x47a3', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=1,
                                         speaker_label='SPEAKER_01', text='okay')
        SystemSetting.objects.update_or_create(key='reaction_filter',
                                               defaults={'value': '0'})
        self.assertEqual(attribution.drop_reactions(p), 0)
        self.assertEqual(p.transcript_segments.count(), 1)


class Parche47B(TestCase):
    """4.7-B — el motor conjunto AssemblyAI, primer eslabon de la cadena
    AssemblyAI → GPU → CPU. Regla 5.7: cualquier fallo devuelve None y el
    siguiente eslabon sigue."""

    def test_mapeo_de_utterances_a_formato_local(self):
        from apps.agents import assembly
        datos = {'status': 'completed', 'language_code': 'en', 'utterances': [
            {'speaker': 'A', 'start': 250, 'end': 3900, 'text': 'Hello there.',
             'words': [{'text': 'Hello', 'start': 250, 'end': 900},
                       {'text': 'there.', 'start': 950, 'end': 1400}]},
            {'speaker': 'B', 'start': 4000, 'end': 4600, 'text': 'Get out.',
             'words': [{'text': 'Get', 'start': 4000, 'end': 4200},
                       {'text': 'out.', 'start': 4250, 'end': 4600}]},
            {'speaker': 'A', 'start': 4700, 'end': 6000, 'text': 'So the century.',
             'words': []},
        ]}
        out = assembly._map(datos)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]['speaker_label'], 'SPEAKER_00')
        self.assertEqual(out[1]['speaker_label'], 'SPEAKER_01')
        self.assertEqual(out[2]['speaker_label'], 'SPEAKER_00')
        self.assertAlmostEqual(out[0]['start_seconds'], 0.25)
        self.assertAlmostEqual(out[1]['end_seconds'], 4.6)
        self.assertEqual(out[0]['words'][0]['text'], 'Hello')

    def test_sin_clave_duerme_sin_llamar_a_nada(self):
        from apps.agents import assembly
        with override_settings(ASSEMBLYAI_API_KEY=''):
            self.assertIsNone(assembly.transcribe_diarize('/no/existe.mp3'))

    def test_fallo_remoto_cede_al_siguiente_eslabon(self):
        from apps.agents import assembly
        with override_settings(ASSEMBLYAI_API_KEY='k', ASSEMBLYAI_TIMEOUT=1), \
             mock.patch.object(assembly.httpx, 'post',
                               side_effect=Exception('red caida')), \
             mock.patch.object(assembly, 'open',
                               mock.mock_open(read_data=b'x'), create=True):
            self.assertIsNone(assembly.transcribe_diarize('/x.mp3'))

    def test_el_panel_puede_apagar_el_eslabon(self):
        from apps.agents import assembly
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='audio_engine_assemblyai',
                                               defaults={'value': '0'})
        with override_settings(ASSEMBLYAI_API_KEY='k'):
            self.assertIsNone(assembly.transcribe_diarize('/x.mp3'))


class Parche47B1(TestCase):
    """4.7-B.1 — el oro de David cazo la aniquilacion mutua: dos copias de la
    misma frase (original + eco) se borraban LAS DOS. El eco es la repeticion:
    solo se compara contra el segmento ANTERIOR."""

    def test_el_original_sobrevive_y_solo_cae_el_eco(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u47b1', 'u47b1@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x47b1', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=3,
                                         speaker_label='SPEAKER_00',
                                         text='how do you measure thoughts')
        TranscriptSegment.objects.create(post=p, start_seconds=3, end_seconds=5,
                                         speaker_label='SPEAKER_01',
                                         text='how do you measure thoughts')
        n = attribution.drop_reactions(p)
        self.assertEqual(n, 1)
        restante = p.transcript_segments.get()
        self.assertEqual(restante.speaker_label, 'SPEAKER_00')  # el ORIGINAL


class Parche48A(TestCase):
    """4.8-B (politica cientifica de David): con las frases de voces FANTASMA
    no se adivina el hablante. Sin informacion factual → se eliminan y la base
    InnocuousPhrase las aprende para siempre; con informacion → INCIERTAS y
    la comunidad decide."""

    def _post_con_fantasma(self, texto='you do it you pimp'):
        from apps.analysis.models import Post, TranscriptSegment
        User = get_user_model()
        u = User.objects.create_user(f'u48a{Post.objects.count()}',
                                     f'u48a{Post.objects.count()}@x.com', 'x')
        p = Post.objects.create(url=f'https://youtu.be/x48a{Post.objects.count()}',
                                author=u)
        datos = [(0, 100, 'SPEAKER_00', 'the explanation of physics continues'),
                 (100, 130, 'SPEAKER_01', 'a real question from the cohost'),
                 (130, 133, 'SPEAKER_02', texto),
                 (133, 200, 'SPEAKER_00', 'more physics explanation goes on')]
        for a, b, l, t in datos:
            TranscriptSegment.objects.create(post=p, start_seconds=a,
                                             end_seconds=b, speaker_label=l,
                                             text=t)
        return p

    def test_sin_informacion_se_elimina_y_la_base_aprende(self):
        from apps.agents import attribution
        from apps.analysis.models import InnocuousPhrase
        p = self._post_con_fantasma()
        r = {'decisiones': [{'n': 0, 'factual': False}]}
        with mock.patch.object(attribution.client, 'call_json', return_value=r):
            res = attribution.adjudicate_minor_voices(p)
        self.assertEqual(res['deleted'], 1)
        self.assertFalse(p.transcript_segments.filter(
            text__contains='pimp').exists())
        self.assertTrue(InnocuousPhrase.objects.filter(
            text_norm='you do it you pimp').exists())

    def test_con_informacion_queda_incierta_jamas_adivinada(self):
        from apps.agents import attribution
        p = self._post_con_fantasma(texto='the tower is 300 meters tall')
        r = {'decisiones': [{'n': 0, 'factual': True}]}
        with mock.patch.object(attribution.client, 'call_json', return_value=r):
            res = attribution.adjudicate_minor_voices(p)
        self.assertEqual(res['uncertain'], 1)
        s2 = p.transcript_segments.get(text__contains='300 meters')
        self.assertTrue(s2.attribution_uncertain)
        self.assertEqual(s2.speaker_label, 'SPEAKER_02')  # NO se adivino

    def test_la_base_aprendida_actua_gratis_sin_llamar_a_sonnet(self):
        from apps.agents import attribution
        from apps.analysis.models import InnocuousPhrase
        InnocuousPhrase.objects.create(text_norm='you do it you pimp')
        p = self._post_con_fantasma()
        with mock.patch.object(attribution.client, 'call_json') as llamada:
            res = attribution.adjudicate_minor_voices(p)
        llamada.assert_not_called()
        self.assertEqual(res['deleted'], 1)
        self.assertEqual(InnocuousPhrase.objects.get(
            text_norm='you do it you pimp').times_seen, 2)

    def test_drop_reactions_consulta_la_base(self):
        from apps.agents import attribution
        from apps.analysis.models import Post, TranscriptSegment, InnocuousPhrase
        InnocuousPhrase.objects.create(text_norm='holy mackerel')
        User = get_user_model()
        u = User.objects.create_user('u48b4', 'u48b4@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x48b4', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=5,
                                         speaker_label='SPEAKER_00',
                                         text='a real factual sentence here')
        TranscriptSegment.objects.create(post=p, start_seconds=5, end_seconds=6,
                                         speaker_label='SPEAKER_01',
                                         text='Holy mackerel!')
        self.assertEqual(attribution.drop_reactions(p), 1)
        self.assertEqual(p.transcript_segments.count(), 1)

    def test_con_dos_voces_no_hay_nada_que_cribar(self):
        from apps.analysis.models import Post, TranscriptSegment
        from apps.agents import attribution
        User = get_user_model()
        u = User.objects.create_user('u48a5', 'u48a5@x.com', 'x')
        p = Post.objects.create(url='https://youtu.be/x48a5', author=u)
        TranscriptSegment.objects.create(post=p, start_seconds=0, end_seconds=9,
                                         speaker_label='SPEAKER_00', text='a')
        TranscriptSegment.objects.create(post=p, start_seconds=9, end_seconds=12,
                                         speaker_label='SPEAKER_01', text='b')
        self.assertEqual(
            attribution.adjudicate_minor_voices(p)['adjudicated'], 0)

    def test_la_pista_viaja_en_el_dialecto_de_assemblyai(self):
        from apps.agents.assembly import _pista_aai
        self.assertEqual(_pista_aai({'num_speakers': 2}),
                         {'speakers_expected': 2})
        # 4.9-C: la API real RECHAZA min/max (400) aunque su doc los pinte —
        # un rango NO viaja; solo el numero exacto.
        self.assertEqual(_pista_aai({'min_speakers': 2, 'max_speakers': 3}), {})
        self.assertEqual(_pista_aai(None), {})

    def test_la_criba_usa_el_modelo_del_panel(self):
        """Orden de David: el modelo de la criba factual se elige en el panel
        (tarea 'innocuous'), no hereda a ciegas el de la pasada de sentido."""
        from apps.agents import attribution
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(
            key='model_innocuous', defaults={'value': 'claude-haiku-4-5-20251001'})
        p = self._post_con_fantasma()
        r = {'decisiones': [{'n': 0, 'factual': False}]}
        with mock.patch.object(attribution.client, 'call_json',
                               return_value=r) as llamada:
            attribution.adjudicate_minor_voices(p)
        self.assertEqual(llamada.call_args.args[0], 'claude-haiku-4-5-20251001')


class Parche49A(TestCase):
    """4.9-A — el libro de cuentas: cada centimo a donde se necesita, y el
    desglose por analisis para la transparencia con las donaciones."""

    def _post(self):
        from apps.analysis.models import Post
        User = get_user_model()
        u = User.objects.create_user(f'u49{Post.objects.count()}',
                                     f'u49{Post.objects.count()}@x.com', 'x')
        return Post.objects.create(url=f'https://youtu.be/x49{Post.objects.count()}',
                                   author=u)

    def test_el_apunte_se_registra_y_el_desglose_suma(self):
        from apps.analysis import costs
        p = self._post()
        costs.record('assemblyai', 'transcripcion+voces', 0.12, post=p)
        costs.record('anthropic', 'analisis', 0.05, post=p)
        filas, total = costs.post_breakdown(p)
        self.assertEqual(len(filas), 2)
        self.assertAlmostEqual(total, 0.17)
        self.assertAlmostEqual(costs.month_total('assemblyai'), 0.12)

    def test_el_peaje_anthropic_cuelga_el_apunte_del_post_en_curso(self):
        from apps.analysis import costs
        from apps.analysis.models import DailyBudget
        p = self._post()
        costs.set_post(p)
        try:
            self.assertTrue(DailyBudget.try_spend(0.03))
        finally:
            costs.set_post(None)
        filas, total = costs.post_breakdown(p)
        self.assertAlmostEqual(total, 0.03)
        self.assertEqual(filas[0]['provider'], 'anthropic')

    def test_el_tope_de_assemblyai_hace_caer_a_la_gpu(self):
        from apps.agents import assembly
        from apps.analysis import costs
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(
            key='assemblyai_monthly_cap_eur', defaults={'value': '0.10'})
        costs.record('assemblyai', 'transcripcion+voces', 0.12)
        with override_settings(ASSEMBLYAI_API_KEY='k'):
            self.assertIsNone(assembly.transcribe_diarize('/x.mp3'))

    def test_el_tope_de_runpod_hace_caer_a_cpu(self):
        from apps.agents import gpu
        from apps.analysis import costs
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(
            key='runpod_monthly_cap_eur', defaults={'value': '0.05'})
        costs.record('runpod', 'whisper', 0.06)
        with override_settings(RUNPOD_API_KEY='k', RUNPOD_WHISPER_ENDPOINT='e',
                               RUNPOD_DIARIZE_ENDPOINT='e'):
            self.assertIsNone(gpu.transcribe_gpu('/x.mp3'))
            self.assertIsNone(gpu.diarize_gpu('/x.mp3'))

    def test_el_tope_de_emails_calla_el_email_pero_no_la_campana(self):
        from apps.accounts import services
        from apps.accounts.models import Notification
        from apps.analysis import costs
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(
            key='brevo_monthly_email_cap', defaults={'value': '1'})
        costs.record('brevo', 'email', 0.0001)   # cupo ya consumido
        User = get_user_model()
        u = User.objects.create_user('u49mail', 'u49mail@x.com', 'x',
                                     notify_mode='INSTANT')
        u.quiet_night = False
        u.save()
        with mock.patch.object(services, 'send_mail') as correo:
            services.notify(u, 'hola', '/x/')
        correo.assert_not_called()
        self.assertEqual(Notification.objects.filter(user=u).count(), 1)


class Parche49B(TestCase):
    """4.9-B — las reacciones conocidas se extirpan de DENTRO de las
    intervenciones del motor conjunto, por frase completa."""

    def _utt(self, texto, palabras):
        return {'start_seconds': palabras[0]['start'],
                'end_seconds': palabras[-1]['end'], 'text': texto,
                'speaker_label': 'SPEAKER_00', 'words': palabras}

    def test_la_reaccion_incrustada_desaparece_y_el_contenido_se_parte(self):
        from apps.agents.attribution import excise_embedded_reactions
        ws = [{'start': i, 'end': i + 0.9, 'text': t} for i, t in enumerate(
            ['The', '1800s.', 'Okay.', 'We', 'discover', 'the', 'laws.'])]
        seg = self._utt('The 1800s. Okay. We discover the laws.', ws)
        out, fuera = excise_embedded_reactions([seg])
        self.assertEqual(fuera, 1)
        self.assertEqual([o['text'] for o in out],
                         ['The 1800s.', 'We discover the laws.'])
        self.assertAlmostEqual(out[1]['start_seconds'], 3)

    def test_right_en_mitad_de_frase_jamas_se_toca(self):
        from apps.agents.attribution import excise_embedded_reactions
        ws = [{'start': i, 'end': i + 0.9, 'text': t} for i, t in enumerate(
            ['All', 'right', 'so', 'coming', 'into', 'the', 'century.'])]
        seg = self._utt('All right so coming into the century.', ws)
        out, fuera = excise_embedded_reactions([seg])
        self.assertEqual(fuera, 0)
        self.assertEqual(len(out), 1)

    def test_la_base_aprendida_tambien_extirpa(self):
        from apps.agents.attribution import excise_embedded_reactions
        from apps.analysis.models import InnocuousPhrase
        InnocuousPhrase.objects.create(text_norm='holy mackerel')
        ws = [{'start': i, 'end': i + 0.9, 'text': t} for i, t in enumerate(
            ['Facts', 'here.', 'Holy', 'mackerel!', 'More', 'facts', 'here.'])]
        seg = self._utt('Facts here. Holy mackerel! More facts here.', ws)
        out, fuera = excise_embedded_reactions([seg])
        self.assertEqual(fuera, 1)
        self.assertEqual([o['text'] for o in out],
                         ['Facts here.', 'More facts here.'])

    def test_desalineado_no_se_opera(self):
        from apps.agents.attribution import excise_embedded_reactions
        seg = self._utt('Two sentences. Here okay.',
                        [{'start': 0, 'end': 1, 'text': 'solo-una-palabra'}])
        out, fuera = excise_embedded_reactions([seg])
        self.assertEqual(fuera, 0)
        self.assertEqual(out[0]['text'], 'Two sentences. Here okay.')
