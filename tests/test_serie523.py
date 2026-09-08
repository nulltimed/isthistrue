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
