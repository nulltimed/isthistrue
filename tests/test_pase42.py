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
