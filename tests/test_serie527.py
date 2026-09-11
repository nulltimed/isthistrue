"""Serie 5.27 (ordenes de David, 2026-09-11): la UNICA puerta al trabajo 2 son
los votos + los hablantes identificados (sin piloto automatico), sin reloj de
validacion, boton con contador, el bibliotecario comprueba el subforo, una
sola rueda para el reanalisis profundo y la pestaña «Analisis» del panel."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post, ValidationVote

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u527', email='u527@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


class _Base(TestCase):
    def setUp(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='startup_mode_min_users', defaults={'value': '0'})
        SystemSetting.objects.update_or_create(key='votes_to_validate', defaults={'value': '2'})

    def _post(self, n=0, etiquetas=('SPEAKER_00', 'SPEAKER_01'), **kw):
        post = Post.objects.create(
            author=make_user(username=f'a527_{n}', email=f'a527_{n}@example.org'),
            url=f'https://youtu.be/s527{n}', status='PENDING_VALIDATION',
            title=f'Vídeo {n}', topic='economia', **kw)
        for i, etq in enumerate(etiquetas):
            post.transcript_segments.create(start_seconds=i * 5.0, end_seconds=i * 5.0 + 4,
                                            text=f'Frase de {etq}', speaker_label=etq)
        return post

    def _nombrar(self, post, etiqueta, nombre):
        from apps.wiki.models import SpeakerNameProposal
        return SpeakerNameProposal.objects.create(post=post, speaker_label=etiqueta,
                                                  candidate_name=nombre, confirmed=True,
                                                  source='user')

    _seq = 0

    def _votar(self, post, n=1, mod=False):
        for _ in range(n):
            _Base._seq += 1
            u = make_user(username=f'v527_{_Base._seq}', email=f'v527_{_Base._seq}@example.org',
                          karma=100, is_staff=mod, is_superuser=mod)
            ValidationVote.objects.create(post=post, kind='VALIDATE', user=u)


class Parche527A_PuertaUnica(_Base):
    def test_la_fase_barata_ya_no_lanza_nada_sola(self):
        src = open('apps/analysis/tasks.py', encoding='utf-8').read()
        cuerpo = src[src.index('def run_cheap_phase'):src.index('def _date_and_hint')]
        for prohibido in ('try_autopilot', 'try_launch_full(', 'launch_full_analysis('):
            self.assertNotIn(prohibido, cuerpo, prohibido)
        self.assertFalse(hasattr(__import__('apps.analysis.tasks', fromlist=['x']),
                                 'auto_verify_slot_free'))

    def test_hacen_falta_votos_y_hablantes(self):
        from apps.analysis.services import try_launch_full
        post = self._post(1)
        with mock.patch('apps.analysis.tasks.launch_full_analysis') as lanzar:
            self._nombrar(post, 'SPEAKER_00', 'Ana'); self._nombrar(post, 'SPEAKER_01', 'Bea')
            self.assertFalse(try_launch_full(post), 'sin votos no arranca')
            self._votar(post, 1)
            self.assertFalse(try_launch_full(post), 'con 1 de 2 votos no arranca')
            self._votar(post, 1)
            self.assertTrue(try_launch_full(post))
            lanzar.assert_called_once()
        post.refresh_from_db()
        self.assertEqual(post.status, 'FULL_QUEUED')

    def test_el_voto_de_moderacion_vale_por_todos_solo_en_modo_arranque(self):
        from apps.analysis.services import votes_needed, try_launch_full
        from apps.panel.models import SystemSetting
        post = self._post(2)
        self._nombrar(post, 'SPEAKER_00', 'Ana'); self._nombrar(post, 'SPEAKER_01', 'Bea')
        self._votar(post, 1, mod=True)
        self.assertEqual(votes_needed(post), 2)          # sin modo arranque: la rueda manda
        self.assertFalse(try_launch_full(post))
        SystemSetting.objects.update_or_create(key='startup_mode_min_users', defaults={'value': '1000'})
        self.assertEqual(votes_needed(post), 1)
        with mock.patch('apps.analysis.tasks.launch_full_analysis'):
            self.assertTrue(try_launch_full(post))

    def test_cast_vote_guarda_y_cuenta(self):
        from apps.analysis.services import cast_vote
        post = self._post(3)
        v = make_user(username='cv1', email='cv1@example.org', karma=100)
        ok, msg = cast_vote(post, v, 'VALIDATE')
        self.assertTrue(ok)
        self.assertIn('1 de 2', msg)
        self._nombrar(post, 'SPEAKER_00', 'Ana'); self._nombrar(post, 'SPEAKER_01', 'Bea')
        v2 = make_user(username='cv2', email='cv2@example.org', karma=100)
        with mock.patch('apps.analysis.tasks.launch_full_analysis') as lanzar:
            ok, msg = cast_vote(post, v2, 'VALIDATE')
        self.assertTrue(ok)
        self.assertIn('lanzado', msg)
        lanzar.assert_called_once()

    def test_el_66_por_ciento_es_el_de_fabrica(self):
        from django.conf import settings
        from apps.analysis.services import min_identified_percent
        self.assertEqual(settings.SETTING_DEFAULTS['min_identified_speakers_percent'], '66')
        self.assertEqual(min_identified_percent(), 66)


class Parche527B_SinReloj(TestCase):
    def test_pendiente_sin_fecha_limite_y_sin_tarea_en_el_beat(self):
        from apps.analysis.services import open_validation_window
        from config.celery import app
        u = make_user()
        post = Post.objects.create(author=u, url='https://youtu.be/r527')
        open_validation_window(post)
        post.refresh_from_db()
        self.assertEqual(post.status, 'PENDING_VALIDATION')
        self.assertIsNone(post.validation_deadline)
        self.assertNotIn('relegar-validaciones-caducadas', app.conf.beat_schedule)

    def test_los_ajustes_retirados_no_estan_en_el_panel(self):
        from django.conf import settings
        from apps.panel.views import SETTINGS_DEF
        claves = {k for k, *_ in SETTINGS_DEF}
        for muerta in ('validation_window_days', 'auto_verify_daily_cap', 'deep_scan_votes'):
            self.assertNotIn(muerta, claves, muerta)
            self.assertNotIn(muerta, settings.SETTING_DEFAULTS, muerta)
        self.assertIn('segment_opus_downvotes', claves)
        self.assertIn('opus_rescan_percent', claves)


class Parche527C_BotonConContador(_Base):
    def test_el_boton_y_el_contador_se_ven(self):
        post = self._post(4)
        self._votar(post, 1)
        self.client.force_login(make_user(username='lector', email='lector@example.org'))
        html = self.client.get(f'/post/{post.pk}/', follow=True).content.decode()
        self.assertIn('Pedir el análisis con fuentes', html)
        self.assertIn('van 1 de 2 votos', html)
        self.assertNotIn('Es factual', html)
        self.assertNotIn('antes de', html.split('Pendiente del análisis')[1][:300])


class Parche527D_Bibliotecario(_Base):
    def _cats(self):
        from apps.analysis.models import Category
        raiz = Category.root()
        for slug, nombre in (('economia', 'Economía'), ('salud', 'Salud')):
            Category.objects.get_or_create(slug=slug, defaults={'name': nombre, 'parent': raiz})

    def test_sugiere_otro_subforo_y_no_mueve(self):
        from apps.agents import librarian
        self._cats()
        post = self._post(5)
        sweep = {'claims': [{'text': 'La vacuna reduce ingresos un 80 %.', 'kind': 'FACTUAL'}]}
        with mock.patch('apps.agents.client.call_json',
                        return_value={'encaja': False, 'slug': 'salud', 'motivo': 'Habla de vacunas'}):
            self.assertEqual(librarian.check_category(post, sweep), 'salud')
        post.refresh_from_db()
        self.assertEqual((post.topic, post.suggested_topic), ('economia', 'salud'))
        self.assertIn('vacunas', post.suggested_topic_note)

    def test_si_encaja_o_el_slug_no_existe_no_sugiere(self):
        from apps.agents import librarian
        self._cats()
        post = self._post(6)
        with mock.patch('apps.agents.client.call_json', return_value={'encaja': True}):
            self.assertEqual(librarian.check_category(post, {'claims': []}), '')
        with mock.patch('apps.agents.client.call_json',
                        return_value={'encaja': False, 'slug': 'inventada', 'motivo': 'x'}):
            self.assertEqual(librarian.check_category(post, {'claims': []}), '')
        post.refresh_from_db()
        self.assertEqual(post.suggested_topic, '')

    def test_moderacion_ve_la_sugerencia_y_mover_o_descartar_la_cierra(self):
        self._cats()
        post = self._post(7, suggested_topic='salud', suggested_topic_note='Habla de vacunas')
        mod = make_user(username='m527', email='m527@example.org', is_staff=True, is_superuser=True)
        self.client.force_login(mod)
        html = self.client.get(f'/post/{post.pk}/', follow=True).content.decode()
        self.assertIn('encaja mejor en', html)
        self.assertIn('Mover ahí', html)
        self.assertIn('Mover al subforo sugerido', html)
        self.client.post(f'/post/{post.pk}/sugerencia/descartar/')
        post.refresh_from_db()
        self.assertEqual(post.suggested_topic, '')
        post.suggested_topic = 'salud'; post.save(update_fields=['suggested_topic'])
        self.client.post(f'/post/{post.pk}/mover/', {'topic': 'salud'})
        post.refresh_from_db()
        self.assertEqual((post.topic, post.suggested_topic), ('salud', ''))

    def test_la_rueda_del_clasificador_se_fue_y_el_bibliotecario_esta_en_la_fase_barata(self):
        from apps.agents.catalog import TASK_KEYS, FALLBACK_DEFAULTS
        self.assertNotIn('classify', TASK_KEYS)
        self.assertNotIn('classify', FALLBACK_DEFAULTS)
        self.assertIn('categories', TASK_KEYS)
        src = open('apps/analysis/tasks.py', encoding='utf-8').read()
        cuerpo = src[src.index('def run_cheap_phase'):src.index('def _date_and_hint')]
        self.assertIn('librarian.check_category(post, result)', cuerpo)


class Parche527F_PanelAnalisis(TestCase):
    def setUp(self):
        self.client.force_login(make_user(username='sup527', email='sup527@example.org',
                                          is_staff=True, is_superuser=True))

    def test_la_pestaña_agrupa_el_proceso_y_guarda(self):
        from apps.panel.models import SystemSetting
        html = self.client.get('/panel/analisis/').content.decode()
        for t in ('Trabajo 1', 'La sala de espera', 'Trabajo 2', 'Reanálisis profundo',
                  'name="votes_to_validate"', 'name="min_identified_speakers_percent"',
                  'name="web_searches_per_claim"', 'name="segment_opus_downvotes"'):
            self.assertIn(t, html, t)
        r = self.client.post('/panel/analisis/', {'votes_to_validate': '7'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SystemSetting.get_int('votes_to_validate', 5), 7)

    def test_ajustes_ya_no_repite_los_del_analisis(self):
        html = self.client.get('/panel/settings/').content.decode()
        self.assertNotIn('name="votes_to_validate"', html)
        self.assertNotIn('name="web_searches_per_claim"', html)
        self.assertIn('name="budget_base_eur"', html)
        self.assertIn('/panel/analisis/', html)
