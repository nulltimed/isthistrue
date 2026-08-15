"""Tests del pase 4.1: gate de diarizacion (B1) y cantidad valida de donacion (B3)."""
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.panel.models import Donation


class GateDiarizacion(TestCase):
    """B1: la omision de diarizacion JAMAS es silenciosa (regla 5.7)."""

    @override_settings(MOCK_AGENTS=False, HF_TOKEN='')
    def test_sin_token_avisa_y_devuelve_vacio(self):
        from apps.agents import diarization
        with self.assertLogs('agents.diarization', level='WARNING') as logs:
            self.assertEqual(diarization.diarize('/tmp/nada.wav'), [])
        self.assertTrue(any('HF_TOKEN ausente' in m for m in logs.output))

    @override_settings(MOCK_AGENTS=False, HF_TOKEN='hf_falso')
    def test_fallo_de_pyannote_avisa_con_causa(self):
        from apps.agents import diarization
        diarization._pipeline = None
        fake = mock.MagicMock()
        fake.Pipeline.from_pretrained.side_effect = AttributeError(
            "module 'torchaudio' has no attribute 'AudioMetaData'")
        with mock.patch.dict('sys.modules', {'pyannote.audio': fake, 'pyannote': mock.MagicMock(audio=fake)}):
            with self.assertLogs('agents.diarization', level='WARNING') as logs:
                self.assertEqual(diarization.diarize('/tmp/nada.wav'), [])
        self.assertTrue(any('AudioMetaData' in m for m in logs.output))
        diarization._pipeline = None

    @override_settings(MOCK_AGENTS=False, HF_TOKEN='hf_falso')
    def test_con_token_y_pyannote_sano_diariza(self):
        from apps.agents import diarization
        diarization._pipeline = None
        turn = mock.MagicMock(start=0.0, end=3.5)
        result = mock.MagicMock()
        result.itertracks.return_value = [(turn, None, '00'), (turn, None, '01')]
        fake = mock.MagicMock()
        fake.Pipeline.from_pretrained.return_value = mock.MagicMock(return_value=result)
        with mock.patch.dict('sys.modules', {'pyannote.audio': fake, 'pyannote': mock.MagicMock(audio=fake)}):
            turns = diarization.diarize('/tmp/nada.wav')
        self.assertEqual([t[2] for t in turns], ['SPEAKER_00', 'SPEAKER_01'])
        diarization._pipeline = None


class DonacionCantidadValida(TestCase):
    """B3: el registro manual del panel exige una cantidad positiva."""

    def setUp(self):
        self.staff = User.objects.create_user(username='staff41', password='x',
                                              birth_date=date(1990, 1, 1))
        self.staff.is_staff = True
        self.staff.email_verified = True
        self.staff.save()
        self.client.force_login(self.staff)

    def test_rechaza_cero_negativo_y_basura(self):
        for mala in ('0', '-5', 'abc', ''):
            self.client.post('/panel/donaciones/', {'amount': mala, 'method': 'PAYPAL'})
        self.assertEqual(Donation.objects.count(), 0)

    def test_acepta_cantidad_valida_con_coma(self):
        self.client.post('/panel/donaciones/', {'amount': '7,50', 'method': 'PAYPAL'})
        self.assertEqual(Donation.objects.count(), 1)
        self.assertEqual(float(Donation.objects.get().amount_eur), 7.5)
