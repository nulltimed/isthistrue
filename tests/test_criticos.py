"""
El robot de la ITV (quiz 5A): comprueba los circuitos vitales con un comando.
Ejecutar: python manage.py test tests --settings=tests.settings_test
"""
from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import AnalysisCredit, RedeemCode, User
from apps.analysis.models import DailyBudget, MonthlyCap, Post, ValidationVote
from apps.analysis.services import cast_vote, open_validation_window
from apps.panel.models import SystemSetting


def make_user(name, **kw):
    return User.objects.create_user(username=name, password='x',
                                    birth_date=date(1990, 1, 1), **kw)


class FrenosPresupuesto(TestCase):
    # Los limites se derivan del presupuesto VIVO: el test no vuelve a romperse
    # cuando David cambie las cifras (2/60 -> 3/100 en Fase 3.3).
    def test_candado_diario_no_gasta_de_mas(self):
        from apps.panel.services import live_daily_budget
        limite = live_daily_budget()
        self.assertTrue(DailyBudget.try_spend(limite - 0.5))
        self.assertFalse(DailyBudget.try_spend(1.00))  # rebasaria el techo diario vivo

    def test_corte_mensual(self):
        from apps.panel.services import live_monthly_cap
        cap, _, _ = live_monthly_cap()
        ym = timezone.localdate().strftime('%Y-%m')
        MonthlyCap.objects.create(year_month=ym, spent_eur=Decimal(str(cap)) - Decimal('0.01'))
        self.assertFalse(DailyBudget.try_spend(0.50))


class CuposUsuario(TestCase):
    def test_cupo_diario_nivel_nuevo(self):
        u = make_user('nuevo1')
        for _ in range(10):
            AnalysisCredit.objects.create(user=u)
        self.assertFalse(u.can_spend_credit())


class Votaciones(TestCase):
    def setUp(self):
        SystemSetting.objects.create(key='votes_to_validate', value='5')
        SystemSetting.objects.create(key='startup_mode_min_users', value='0')  # sin modo arranque
        self.author = make_user('autor')
        self.post = Post.objects.create(author=self.author, url='https://x/1', platform='youtube')
        open_validation_window(self.post)

    def test_quinto_voto_lanza_fase_cara(self):
        for i in range(5):
            voter = make_user(f'v{i}', karma=100)  # Contribuidor por karma
            cast_vote(self.post, voter, 'VALIDATE')
        self.post.refresh_from_db()
        self.assertIn(self.post.status, ('FULL_QUEUED', 'FULL_RUNNING', 'DONE'))

    def test_nivel_nuevo_no_vota(self):
        novato = make_user('sinKarma')
        ok, _ = cast_vote(self.post, novato, 'VALIDATE')
        self.assertFalse(ok)

    def test_modo_arranque_un_voto_de_mod(self):
        SystemSetting.objects.filter(key='startup_mode_min_users').update(value='50')
        mod = make_user('mod1', level='MOD')
        cast_vote(self.post, mod, 'VALIDATE')
        self.post.refresh_from_db()
        self.assertIn(self.post.status, ('FULL_QUEUED', 'FULL_RUNNING', 'DONE'))


class Codigos(TestCase):
    def test_canje_y_revocacion_silenciosa(self):
        u = make_user('canjeador')
        code = RedeemCode.objects.create(grants_level='CONTRIB')
        self.assertTrue(code.redeem(u))
        self.assertEqual(u.effective_level(), 'CONTRIB')
        self.assertFalse(code.redeem(u))  # un solo uso
        code.revoke()
        u.refresh_from_db()
        self.assertEqual(u.effective_level(), 'NEW')

    def test_karma_consolida_frente_a_revocacion(self):
        u = make_user('meritocrata', karma=100)
        code = RedeemCode.objects.create(grants_level='CONTRIB')
        code.redeem(u)
        code.revoke()
        u.refresh_from_db()
        self.assertEqual(u.effective_level(), 'CONTRIB')  # el karma real manda


class Relegacion(TestCase):
    def test_validacion_caducada_se_marca_pero_no_se_relega(self):
        # 4.2 A2 (decision de David): NINGUN post se relega solo. La caducidad
        # marca VALIDATION_EXPIRED + sugerencia; relegar es accion de moderador.
        from apps.analysis.tasks import relegate_expired_validations
        author = make_user('autor2')
        p = Post.objects.create(author=author, url='https://x/2', platform='youtube',
                                status='PENDING_VALIDATION',
                                validation_deadline=timezone.now() - timezone.timedelta(hours=1))
        relegate_expired_validations()
        p.refresh_from_db()
        self.assertEqual(p.category, 'MAIN')  # sigue en Principal
        self.assertEqual(p.status, 'VALIDATION_EXPIRED')
        self.assertTrue(p.offtopic_suggested)


class Edad(TestCase):
    def test_menor_de_14_rechazado(self):
        from apps.accounts.forms import RegisterForm
        hoy = date.today()
        form = RegisterForm(data={'username': 'peque', 'email': 'p@x.com',
                                  'birth_date': date(hoy.year - 12, 1, 1),
                                  'password1': 'ContraseñaLarga77', 'password2': 'ContraseñaLarga77'})
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)
