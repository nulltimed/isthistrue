"""Serie 6.2 (ordenes de David, 2026-11-06): la API de lectura con clave.

«crea ya la API con todas las opciones imaginables» · «el analisis de quien
solicita la clave sera asistido por IA [...] la decision siempre comprobada por
un superusuario si el solicitante no acepta la decision de denegacion» ·
exclusiones: formaciones politicas y organismos en conflicto con la esencia.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


def _clave(**kw):
    from apps.api.models import ApiKey
    defaults = dict(entity_name='Diario Test', contact_email='api@diario.test',
                    purpose='integración de veredictos en nuestra redacción')
    defaults.update(kw)
    sol = ApiKey.objects.create(**defaults)
    sol.approve()
    return sol


class Autenticacion(TestCase):
    def test_sin_clave_401_con_clave_mala_403(self):
        self.assertEqual(self.client.get('/api/v1/stats/').status_code, 401)
        r = self.client.get('/api/v1/stats/', HTTP_X_API_KEY='istt_falsa')
        self.assertEqual(r.status_code, 403)

    def test_el_cupo_diario_corta_con_429(self):
        from apps.api.models import ApiUsage
        from datetime import date
        sol = _clave()
        cab = {'HTTP_X_API_KEY': sol.key}
        self.assertEqual(self.client.get('/api/v1/stats/', **cab).status_code, 200)
        ApiUsage.objects.filter(api_key=sol).update(count=sol.daily_limit())
        self.assertEqual(self.client.get('/api/v1/stats/', **cab).status_code, 429)

    def test_revocada_no_entra(self):
        sol = _clave()
        sol.status = 'REVOKED'
        sol.save(update_fields=['status'])
        r = self.client.get('/api/v1/stats/', HTTP_X_API_KEY=sol.key)
        self.assertEqual(r.status_code, 403)


class Endpoints(TestCase):
    def setUp(self):
        self.sol = _clave()
        self.cab = {'HTTP_X_API_KEY': self.sol.key}

    def test_claim_completo_lleva_origen_y_fuentes(self):
        from apps.wiki.models import Claim, Source
        c = Claim.objects.create(text_original='prueba api', slug='prueba-api',
                                 color='RED', origin_status='DONE',
                                 origin_chain=[{'kind': 'press', 'date': '2020',
                                                'title': 't', 'url': 'https://e.org',
                                                'note': '', 'twisted': True}])
        Source.objects.create(claim=c, url='https://fuente.org', title='La fuente')
        data = self.client.get('/api/v1/claims/prueba-api/', **self.cab).json()['data']
        self.assertEqual(data['origin_chain'][0]['twisted'], True)
        self.assertEqual(data['sources'][0]['url'], 'https://fuente.org')

    def test_los_filtros_filtran(self):
        from apps.wiki.models import Claim
        Claim.objects.create(text_original='rojo uno', slug='rojo-uno', color='RED')
        Claim.objects.create(text_original='verde uno', slug='verde-uno', color='GREEN')
        data = self.client.get('/api/v1/claims/?color=red', **self.cab).json()
        self.assertEqual(data['meta']['total'], 1)
        data = self.client.get('/api/v1/claims/?q=verde', **self.cab).json()
        self.assertEqual(data['meta']['total'], 1)

    def test_stats_devuelve_agregados(self):
        data = self.client.get('/api/v1/stats/', **self.cab).json()['data']
        for clave in ('claims_total', 'claims_por_color', 'analisis_publicados',
                      'claims_con_origen', 'claims_por_semana'):
            self.assertIn(clave, data)


class EscrutinioYReclamacion(TestCase):
    def test_solicitud_aprobada_por_el_agente_mock(self):
        from apps.api.models import ApiKey
        from apps.api.tasks import vet_api_key
        r = self.client.post('/api/', {'kind': 'ORG', 'entity_name': 'Diario Mock',
                                       'contact_email': 'd@mock.test', 'website': '',
                                       'purpose': 'queremos integrar los veredictos en la redacción'},
                             follow=True)
        self.assertEqual(r.status_code, 200)
        sol = ApiKey.objects.get(entity_name='Diario Mock')
        vet_api_key(sol.pk)   # el MOCK aprueba
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'APPROVED')
        self.assertTrue(sol.key.startswith('istt_'))
        self.assertEqual(sol.ai_verdict['category'], 'medio')

    def test_el_cebo_antispam_descarta_robots(self):
        from apps.api.models import ApiKey
        self.client.post('/api/', {'kind': 'ORG', 'entity_name': 'Bot SA',
                                   'contact_email': 'b@bot.test', 'web2': 'http://spam',
                                   'purpose': 'x' * 30})
        self.assertFalse(ApiKey.objects.exists())

    def test_la_reclamacion_entra_en_la_bandeja_y_el_superusuario_decide(self):
        from apps.api.models import ApiKey
        sol = ApiKey.objects.create(entity_name='Denegada SL', contact_email='x@d.test',
                                    purpose='un uso cualquiera de los datos',
                                    status='DENIED',
                                    ai_verdict={'reasons': ['parece lobby']})
        r = self.client.post(f'/api/reclamar/{sol.pk}/{sol.appeal_token}/',
                             {'appeal_text': 'somos una consultora independiente'},
                             follow=True)
        self.assertEqual(r.status_code, 200)
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'APPEALED')
        # token malo: 404
        self.assertEqual(self.client.get(f'/api/reclamar/{sol.pk}/token-malo/').status_code, 404)
        # y el superusuario la aprueba desde el panel
        d = User.objects.create_superuser(username='d61', email='d61@example.org',
                                          password='x')
        self.client.force_login(d)
        self.client.post('/panel/api/', {'id': sol.pk, 'accion': 'aprobar'})
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'APPROVED')
        self.assertEqual(sol.resolved_by, d)

    def test_la_web_privada_no_tapa_la_api(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='site_private',
                                               defaults={'value': '1'})
        # la documentacion carga y el endpoint pide clave (401), no el modal
        self.assertEqual(self.client.get('/api/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/claims/').status_code, 401)
