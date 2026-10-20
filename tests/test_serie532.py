"""Serie 5.32 (orden de David, 2026-10-20): EL VIDEO COMO FUENTE — si una frase
alude a algo del propio video, la vista mira ese momento y el video cuenta como
fuente (solo si la vista aporto); con lo visto se busca fuera el hecho de fondo."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post

User = get_user_model()


def make_user(**kw):
    defaults = dict(username='u532', email='u532@example.org', password='x')
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def post_abascal(n=1):
    """El caso real del post 4: Diaz enseña una foto en el 2:37; Abascal la
    discute en el 2:56."""
    p = Post.objects.create(author=make_user(username=f'a532_{n}', email=f'a532_{n}@example.org'),
                            url=f'https://youtu.be/d532{n}', platform='youtube', title='Debate 23J')
    filas = [(157, 'SPEAKER_00', 'Se estaban riendo en un minuto de silencio, una mujer asesinada.'),
             (161, 'SPEAKER_00', '¿Sabe por qué nos matan a las mujeres en nuestro país?'),
             (166, 'SPEAKER_00', 'Y ustedes, negando la violencia sobre las mujeres, provocan exactamente esto.'),
             (171, 'SPEAKER_00', 'Usted, haciendo este discurso hoy, está provocando exactamente esto.'),
             (176, 'SPEAKER_02', 'Usted trae aquí una foto y la manipula sin ninguna duda diciendo que esas dos personas se ríen de una mujer asesinada.'),
             (183, 'SPEAKER_00', 'Era el minuto de silencio, señor Abascal.')]
    for s, spk, t in filas:
        p.transcript_segments.create(start_seconds=s, end_seconds=s + 4, text=t, speaker_label=spk,
                                     signal='FACTUAL_UNVERIFIED' if s == 176 else '')
    return p


class Parche532_Deteccion(TestCase):
    def test_detecta_referencias_al_propio_video_y_no_dispara_con_frases_normales(self):
        from apps.agents import selfref
        r = selfref.detect('Usted trae aquí una foto y la manipula sin ninguna duda.')
        self.assertEqual(r['objeto'], 'foto')
        self.assertEqual(selfref.detect('Como ven en este gráfico, el paro bajó.')['objeto'], 'gráfico')
        self.assertIsNotNone(selfref.detect('Lo que acaba de decir es falso.'))
        self.assertIsNone(selfref.detect('El paro bajó un 3 % en 2023.'))
        self.assertIsNone(selfref.detect('La foto de mi abuela está en el salón.'))

    def test_los_momentos_apuntan_al_arranque_del_turno_del_otro(self):
        from apps.agents import selfref
        p = post_abascal(2)
        segs = list(p.transcript_segments.order_by('start_seconds', 'pk'))
        i = next(k for k, s in enumerate(segs) if int(s.start_seconds) == 176)
        # el turno de Diaz (157-171) muestreado: arranque, mitad y final
        self.assertEqual(selfref.momentos(segs, i, 'foto'), [157, 166])


class Parche532_ElVideoComoFuente(TestCase):
    def _run(self, respuesta_modelo, vista):
        from apps.agents import verdict as va
        p = post_abascal(3)
        payloads = []

        def falso(model, system, payload, **kw):
            payloads.append(payload)
            return (dict(respuesta_modelo), model)
        with mock.patch.object(va.client, 'call_search_json', side_effect=falso), \
                mock.patch('apps.agents.vision.mirar', side_effect=vista) as ojo, \
                mock.patch('apps.agents.vision.registrar') as reg, \
                mock.patch('apps.wiki.services._titulo_ia', return_value='t'):
            va.run(p)
        return p, payloads, ojo, reg

    def test_la_vista_va_al_momento_de_la_foto_y_el_video_entra_como_fuente(self):
        from apps.wiki.models import Claim
        def vista(post, frase, segundo):
            if int(segundo) == 157:
                return {'veredicto_visual': 'sostiene', 'modelo': 'qwen3-vl-plus',
                        'detalle': 'Una persona levanta una fotografía impresa con dos hombres sonriendo.'}
            return {'veredicto_visual': 'no_aporta', 'modelo': 'qwen3-vl-plus', 'detalle': 'Plano del orador.'}
        p, payloads, ojo, reg = self._run(
            {'color': 'RED', 'what_is_claimed': 'x', 'what_evidence_says': 'y', 'sources': []}, vista)
        segundos = sorted(int(c.args[2]) for c in ojo.call_args_list)
        self.assertEqual(segundos, [157, 166, 176])
        self.assertIn('REFERENCIA AL PROPIO VÍDEO', payloads[0])
        self.assertIn('minuto 02:37', payloads[0])
        self.assertIn('levanta una fotografía', payloads[0])
        self.assertIn('ES fuente válida', payloads[0])
        c = Claim.objects.get()
        self.assertEqual(c.color, 'RED')               # el modelo olvido citar el video: se añade
        self.assertTrue(c.sources.filter(url__contains='?t=157').exists())
        self.assertTrue(c.sources_ok)
        self.assertEqual(reg.call_args.args[1]['segundo'], 157)   # el fotograma de la foto, a la wiki

    def test_si_la_vista_no_ve_nada_el_video_no_vale_como_fuente(self):
        from apps.wiki.models import Claim
        def vista(post, frase, segundo):
            return {'veredicto_visual': 'no_aporta', 'modelo': 'm', 'detalle': 'nada'}
        p, payloads, ojo, reg = self._run(
            {'color': 'GREEN', 'what_is_claimed': 'x',
             'sources': [{'url': 'https://esestocierto.com/post/debate-23j/?t=157', 'title': 'El propio vídeo'}]}, vista)
        self.assertIn('NO vio nada concluyente', payloads[0])
        c = Claim.objects.get()
        self.assertEqual(c.color, 'UNDECIDED', 'el video citado sin que la vista viera nada se retira')
        self.assertFalse(c.sources.exists())

    def test_el_interruptor_del_panel_lo_apaga(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='video_as_source', defaults={'value': '0'})
        def vista(post, frase, segundo):
            return {'veredicto_visual': 'no_aporta', 'modelo': 'm', 'detalle': 'nada'}
        p, payloads, ojo, reg = self._run({'color': 'GREY', 'what_is_claimed': 'x', 'sources': []}, vista)
        self.assertNotIn('REFERENCIA AL PROPIO VÍDEO', payloads[0])
        self.assertEqual([int(c.args[2]) for c in ojo.call_args_list], [176])

    def test_el_clarificador_tambien_mira_el_momento_referido(self):
        from apps.agents import clarify
        from apps.wiki.models import Claim, ClaimAppearance
        p = post_abascal(4)
        seg = p.transcript_segments.get(start_seconds=176)
        c = Claim.objects.create(text_original=seg.text, color='UNDECIDED', kind='FACTUAL')
        ClaimAppearance.objects.create(claim=c, segment=seg, quote=seg.text)
        payloads = []
        def falso(model, system, payload, **kw):
            payloads.append(payload)
            return ({'color': 'AMBER', 'what_is_claimed': 'x', 'what_evidence_says': 'y', 'sources': []}, model)
        with mock.patch.object(clarify.client, 'call_search_json', side_effect=falso), \
                mock.patch('apps.agents.vision.mirar', return_value={
                    'veredicto_visual': 'sostiene', 'modelo': 'm', 'detalle': 'foto con dos hombres'}), \
                mock.patch('apps.agents.vision.registrar'):
            self.assertEqual(clarify.clarify_claim(c), 'AMBER')
        self.assertIn('REFERENCIA AL PROPIO VÍDEO', payloads[0])
        c.refresh_from_db()
        self.assertEqual(c.color, 'AMBER')
        self.assertTrue(c.sources.filter(url__contains='?t=157').exists())

    def test_el_ajuste_esta_en_el_panel_de_analisis(self):
        self.client.force_login(make_user(username='sup532', email='sup532@example.org',
                                          is_staff=True, is_superuser=True))
        html = self.client.get('/panel/analisis/').content.decode()
        self.assertIn('name="video_as_source"', html)
