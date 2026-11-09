"""Serie 6.23-c (correccion de David, 2026-11-09, 21:30, literal: «No, quiero
simplemente que en análisis profundo se verifiquen todas y cada una de las
afirmaciones/frases del interlocutor. Nada más. Nada de hacerlo de noche ni
nada»).

La tarea nocturna de reintento de grises (6.23) se RETIRO el mismo dia de
nacer. Lo que David pide ya lo hace el sistema de fabrica, y este candado lo
vigila: verdict.run — que es lo que ejecuta tanto el trabajo 2 como el
reanalisis profundo (opus_rescan) — construye un claim por CADA frase con
señal (factual, opinion o contradiccion), sin topes ni muestreos.
"""
import inspect

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.analysis.models import Post, TranscriptSegment

User = get_user_model()


class CoberturaTotalDelAnalisis(TestCase):
    def test_cada_frase_con_senal_entra_al_verificador(self):
        u = User.objects.create_user(username='u623', email='u623@example.org',
                                     password='x')
        post = Post.objects.create(author=u, url='https://youtu.be/s623c')
        for i, senal in enumerate(('FACTUAL_UNVERIFIED', 'OPINION',
                                   'CONTRADICTS_MODEL', '')):
            TranscriptSegment.objects.create(post=post, start_seconds=i * 5,
                                             end_seconds=i * 5 + 5,
                                             text=f'frase {i}', signal=senal)
        from apps.agents.verdict import _claims_from_segments
        claims = _claims_from_segments(post)
        # TODAS las frases con señal — y solo ellas (la vacia es silencio/ruido)
        self.assertEqual(len(claims), 3)
        self.assertEqual({c['kind'] for c in claims}, {'FACTUAL', 'OPINION'})

    def test_el_profundo_usa_el_verificador_completo(self):
        """opus_rescan (reanalisis profundo) pasa por verdict.run — el mismo
        camino que verifica frase a frase — jamas por un atajo muestreado."""
        from apps.analysis import tasks
        src = inspect.getsource(tasks.opus_rescan)
        self.assertIn('verdict_agent.run(post', src)

    def test_no_hay_tarea_nocturna_de_grises(self):
        """Literal de David: «Nada de hacerlo de noche ni nada»."""
        from config.celery import app
        tareas = [e['task'] for e in app.conf.beat_schedule.values()]
        self.assertNotIn('apps.analysis.tasks.reclarify_grey_claims', tareas)
        from apps.analysis import tasks
        self.assertFalse(hasattr(tasks, 'reclarify_grey_claims'))
