"""Tests de la Fase 3 (deuda señalada por el operador): presupuesto vivo, API,
verificacion de email, login email-o-nick, anti-spam de alertas."""
from datetime import date
from django.test import TestCase, override_settings
from apps.accounts.models import User
from apps.accounts.verification import send_verification_email, verify_token
from apps.panel.models import Donation, SystemSetting
from apps.panel.services import live_monthly_cap, live_daily_budget, alert_admin
from apps.wiki.models import Claim


def make_user(name, **kw):
    return User.objects.create_user(username=name, password='x', email=f'{name}@x.com',
                                    birth_date=date(1990, 1, 1), **kw)


class PresupuestoVivo(TestCase):
    def setUp(self):
        SystemSetting.objects.create(key='budget_base_eur', value='60')
        SystemSetting.objects.create(key='budget_hard_ceiling_eur', value='200')

    def test_donacion_engorda_el_deposito(self):
        cap0, _, _ = live_monthly_cap()
        Donation.objects.create(amount_eur=25, method='PAYPAL')
        cap1, donated, _ = live_monthly_cap()
        self.assertEqual(cap1, cap0 + 25)
        self.assertEqual(donated, 25)

    def test_techo_duro_no_se_supera(self):
        Donation.objects.create(amount_eur=500, method='PAYPAL')
        cap, _, _ = live_monthly_cap()
        self.assertEqual(cap, 200)  # ni las donaciones rompen el 2o airbag

    def test_diario_es_techo_entre_dias(self):
        self.assertGreater(live_daily_budget(), 0)
        self.assertLessEqual(live_daily_budget() * 31, 200 + 7)  # margen redondeo


class ApiPublica(TestCase):
    def test_lista_y_detalle(self):
        Claim.objects.create(text_original='La Tierra es esferica', slug='la-tierra-es-esferica',
                             consolidated=True, color='GREEN')
        Claim.objects.create(text_original='borrador', slug='borrador', consolidated=False)
        r = self.client.get('/api/v1/claims/')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['total'], 1)  # solo consolidated
        self.assertIn('CC-BY-SA', data['license'])
        r2 = self.client.get('/api/v1/claims/la-tierra-es-esferica/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(self.client.get('/api/v1/claims/no-existe/').status_code, 404)


class VerificacionEmail(TestCase):
    def test_token_valido_e_invalido(self):
        u = make_user('verificable')
        from django.core import signing
        token = signing.dumps({'uid': u.pk}, salt='email-verify')
        self.assertEqual(verify_token(token), u)
        self.assertIsNone(verify_token(token + 'manipulado'))

    def test_login_bloqueado_sin_verificar(self):
        u = make_user('sinverif')
        r = self.client.post('/accounts/login/', {'username': 'sinverif', 'password': 'x'})
        self.assertEqual(r.status_code, 200)  # se queda en el formulario
        u.email_verified = True
        u.save()
        r = self.client.post('/accounts/login/', {'username': 'sinverif', 'password': 'x'})
        self.assertEqual(r.status_code, 302)  # ahora entra


class LoginEmailONick(TestCase):
    def test_ambos_funcionan(self):
        u = make_user('dualentrada')
        u.email_verified = True
        u.save()
        self.assertEqual(self.client.post('/accounts/login/',
            {'username': 'dualentrada@x.com', 'password': 'x'}).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.post('/accounts/login/',
            {'username': 'dualentrada', 'password': 'x'}).status_code, 302)


class AlertasAntiSpam(TestCase):
    def test_segunda_alerta_en_6h_no_envia(self):
        from django.core import mail
        alert_admin('Presupuesto diario agotado', 'x')
        alert_admin('Presupuesto diario agotado', 'x')
        self.assertEqual(len(mail.outbox), 1)


class OpusRescan(TestCase):
    def test_umbral_40_con_suelo_y_una_sola_vez(self):
        from apps.analysis.models import Post
        from apps.analysis.services import should_opus_rescan
        from apps.forum.models import Vote
        SystemSetting.objects.get_or_create(key='opus_rescan_min_votes', defaults={'value': '10'})
        SystemSetting.objects.get_or_create(key='opus_rescan_percent', defaults={'value': '40'})
        author = make_user('autor3')
        author.email_verified = True
        author.save()
        post = Post.objects.create(author=author, url='https://x/opus', platform='youtube',
                                   status='DONE')
        voters = []
        for i in range(12):
            u = make_user(f'op{i}')
            u.email_verified = True
            u.save()
            voters.append(u)
        # 5 votos: por debajo del suelo de 10 aunque supere el 40% -> NO
        for u in voters[:5]:
            Vote.objects.create(post=post, user=u)
        self.assertFalse(should_opus_rescan(post))
        # 10 votos sobre 13 usuarios (77%) -> SI
        for u in voters[5:10]:
            Vote.objects.create(post=post, user=u)
        self.assertTrue(should_opus_rescan(post))
        # ya reescaneado -> nunca mas
        post.opus_rescanned = True
        post.save()
        self.assertFalse(should_opus_rescan(post))


class ReescaneoOpus(TestCase):
    def test_no_dispara_sin_masa_critica(self):
        from apps.analysis.models import Post
        from apps.analysis.tasks import maybe_trigger_opus_rescan
        SystemSetting.objects.get_or_create(key='opus_rescan_min_users', defaults={'value': '50'})
        u = make_user('votante1')
        p = Post.objects.create(author=u, url='https://x/opus', platform='youtube', status='DONE')
        self.assertFalse(maybe_trigger_opus_rescan(p))  # 1 usuario < 50: candado

    def test_una_sola_vez(self):
        from apps.analysis.models import Post
        from apps.analysis.tasks import opus_rescan
        u = make_user('votante2')
        p = Post.objects.create(author=u, url='https://x/opus2', platform='youtube',
                                status='DONE', opus_rescanned=True)
        self.assertEqual(opus_rescan(p.pk), 'skip')
