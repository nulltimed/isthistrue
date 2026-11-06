"""Serie 6.3 (ordenes de David, 2026-11-06): registro en dos carriles, badge
embebible, dossieres B2B y la eleccion Gratuita/Pro.

Literales: «ok a la propuesta de dos carriles» · el escrutinio del registro con
reclamacion a la bandeja de superusuarios · badge «tiene que ser sencillo para
el webmaster» · dossier B2B «interactivo alojado en la web, accesible
unicamente por el peticionista, con estilo profesional».
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()

DATOS = {'username': 'nuevo63', 'email': 'nuevo63@example.org',
         'password1': 'Entrelazado#2026', 'password2': 'Entrelazado#2026',
         'birth_date': '1990-05-05'}


def _registro(client, **extra):
    datos = dict(DATOS)
    datos.update(extra)
    return client.post('/accounts/register/', datos, follow=True)


class RegistroDosCarriles(TestCase):
    def test_persona_fisica_entra_sin_escrutinio(self):
        _registro(self.client, kind='PERSON')
        u = User.objects.get(username='nuevo63')
        self.assertTrue(u.is_active)
        self.assertEqual(u.signup_vetting.status, 'OK')
        self.assertEqual(u.signup_vetting.verdict, {})   # nadie la investigo

    def test_correo_desechable_se_deniega_y_puede_reclamar(self):
        r = _registro(self.client, kind='PERSON',
                      email='bot63@mailinator.com', username='bot63')
        u = User.objects.get(username='bot63')
        self.assertFalse(u.is_active)
        v = u.signup_vetting
        self.assertEqual(v.status, 'DENIED')
        self.assertIn('Reclamar el registro', r.content.decode())
        self.client.post(f'/accounts/escrutinio/{v.pk}/{v.appeal_token}/',
                         {'appeal_text': 'uso mailinator por privacidad'})
        v.refresh_from_db()
        self.assertEqual(v.status, 'APPEALED')

    def test_persona_juridica_pasa_el_escrutinio_mock_y_se_activa(self):
        # Con CELERY_TASK_ALWAYS_EAGER el escrutinio corre EN EL ACTO y el MOCK
        # aprueba: tras el POST la cuenta ya esta activa con su veredicto.
        _registro(self.client, kind='ORG', org_name='Diario del Test',
                  org_website='https://diario.test', username='diario63',
                  email='org63@example.org')
        u = User.objects.get(username='diario63')
        v = u.signup_vetting
        self.assertTrue(u.is_active)
        self.assertEqual(v.status, 'OK')
        self.assertEqual(v.verdict['category'], 'medio')

    def test_juridica_denegada_queda_inactiva_con_reclamacion(self):
        from unittest import mock
        deniega = {'approve': False, 'category': 'partido_politico',
                   'confidence': 'alta', 'reasons': ['Formación política.'],
                   'sources': []}
        with mock.patch('apps.api.vetting.vet', return_value=deniega):
            _registro(self.client, kind='ORG', org_name='Partido X',
                      username='partido63', email='px63@example.org')
        u = User.objects.get(username='partido63')
        v = u.signup_vetting
        self.assertFalse(u.is_active)
        self.assertEqual(v.status, 'DENIED')
        self.assertIn('Formación política.', v.verdict['reasons'])

    def test_juridica_sin_nombre_no_pasa_el_formulario(self):
        _registro(self.client, kind='ORG', org_name='', username='sinnombre63',
                  email='sn63@example.org')
        self.assertFalse(User.objects.filter(username='sinnombre63').exists())

    def test_la_bandeja_del_panel_activa_al_reclamante(self):
        from apps.accounts.models import SignupVetting
        u = User.objects.create_user(username='apelante63', email='a63@example.org',
                                     password='x', is_active=False)
        v = SignupVetting.objects.create(user=u, kind='ORG', org_name='Reclamante SL',
                                         status='APPEALED',
                                         appeal_text='somos legítimos')
        d = User.objects.create_superuser(username='d63', email='d63@example.org',
                                          password='x')
        self.client.force_login(d)
        self.client.post('/panel/api/', {'reg_id': v.pk, 'reg_accion': 'aprobar'})
        u.refresh_from_db()
        v.refresh_from_db()
        self.assertTrue(u.is_active)
        self.assertEqual(v.status, 'OK')
        self.assertEqual(v.resolved_by, d)

    def test_el_registro_ofrece_gratuita_y_pro_proximamente(self):
        html = self.client.get('/accounts/register/').content.decode()
        self.assertIn('Gratuita', html)
        self.assertIn('Próximamente', html)   # Pro apagada hasta la SL


class BadgeEmbebible(TestCase):
    def _claim(self):
        from apps.wiki.models import Claim
        return Claim.objects.create(text_original='el badge funciona',
                                    slug='badge-63', color='GREEN',
                                    consolidated=True)

    def test_el_iframe_sirve_sin_candado_de_marcos(self):
        c = self._claim()
        r = self.client.get(f'/wiki/claim/{c.slug}/embed/')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get('X-Frame-Options'))   # embebible
        html = r.content.decode()
        self.assertIn('el badge funciona', html)
        self.assertIn('esestocierto?', html)

    def test_la_ficha_ofrece_el_codigo_para_pegar(self):
        c = self._claim()
        html = self.client.get(f'/wiki/claim/{c.slug}/').content.decode()
        self.assertIn('Insertar en tu web', html)
        self.assertIn(f'/wiki/claim/{c.slug}/embed/', html)


class DossierB2B(TestCase):
    def _dossier(self):
        from apps.panel.models import Dossier
        from apps.analysis.models import Post
        u = User.objects.create_user(username='autor63', email='au63@example.org',
                                     password='x')
        p = Post.objects.create(author=u, url='https://youtu.be/d63', title='Para dossier',
                                status='DONE')
        d = Dossier.objects.create(client_name='Cliente SA', client_email='c@sa.test')
        d.posts.add(p)
        return d

    def test_el_cliente_entra_con_su_enlace_aunque_la_web_este_privada(self):
        from apps.panel.models import SystemSetting
        SystemSetting.objects.update_or_create(key='site_private', defaults={'value': '1'})
        d = self._dossier()
        r = self.client.get(f'/dossier/{d.pk}/{d.token}/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Cliente SA', html)
        self.assertIn('Dossier de verificación', html)
        self.assertIn('Para dossier', html)
        self.assertEqual(r['X-Robots-Tag'], 'noindex, nofollow')

    def test_token_malo_o_revocado_404(self):
        d = self._dossier()
        self.assertEqual(self.client.get(f'/dossier/{d.pk}/token-malo/').status_code, 404)
        d.revoked = True
        d.save(update_fields=['revoked'])
        self.assertEqual(self.client.get(f'/dossier/{d.pk}/{d.token}/').status_code, 404)

    def test_el_panel_crea_y_revoca(self):
        from apps.panel.models import Dossier
        from apps.analysis.models import Post
        u = User.objects.create_user(username='autor63b', email='ab63@example.org',
                                     password='x')
        p = Post.objects.create(author=u, url='https://youtu.be/d63b', title='X',
                                status='DONE')
        d_admin = User.objects.create_superuser(username='d63b', email='db63@example.org',
                                                password='x')
        self.client.force_login(d_admin)
        self.client.post('/panel/api/', {'dossier_accion': 'crear',
                                         'client_name': 'Periodico Z',
                                         'client_email': 'z@p.test',
                                         'posts_csv': f'{p.pk}',
                                         'intro': 'encargo de prueba'})
        d = Dossier.objects.get(client_name='Periodico Z')
        self.assertEqual(list(d.posts.all()), [p])
        self.client.post('/panel/api/', {'dossier_accion': 'revocar',
                                         'dossier_id': d.pk})
        d.refresh_from_db()
        self.assertTrue(d.revoked)


class ClavesSL(TestCase):
    def test_los_huecos_de_la_sl_esperan_vacios(self):
        import importlib
        d = importlib.import_module('config.settings').SETTING_DEFAULTS
        for k in ('sl_legal_name', 'sl_cif', 'sl_address', 'sl_registry'):
            self.assertEqual(d[k], '')
        self.assertEqual(d['pro_price_eur'], '4')
