"""6.1: servicios del monedero de creditos (atomicos, con libro).

Regla de oro: el gasto de creditos sobre un post genera ADEMAS un apunte de
financiacion (panel.Donation con method='CREDIT', verified=True): es lo que
sube live_monthly_cap y deja que el fusible del presupuesto autorice el
analisis — la misma mecanica probada del apadrinamiento, sin tocarla. El
techo duro (budget_hard_ceiling_eur) sigue mandando: ni los creditos lo pasan.
"""
from django.db import transaction

from .models import CreditLedger, CreditWallet


class InsufficientCredits(Exception):
    def __init__(self, needed, balance):
        self.needed, self.balance = needed, balance
        super().__init__(f'hacen falta {needed} y hay {balance}')


def wallet(user):
    return CreditWallet.objects.get_or_create(user=user)[0]


@transaction.atomic
def grant(user, n, reason='PACK', note=''):
    """Alta de creditos (pack comprado o ajuste del superusuario)."""
    assert n > 0
    w = CreditWallet.objects.select_for_update().get_or_create(user=user)[0]
    w.balance += n
    w.save(update_fields=['balance'])
    CreditLedger.objects.create(user=user, delta=n, reason=reason, note=note)
    return w.balance


def _respaldado(user):
    """6.6: ¿hay DINERO detras de los creditos de este usuario? Solo entonces
    su gasto sube el tope mensual. Quien jamas compro un pack tiene puro
    regalo (bienvenida, ajuste) y gastarlo NO crea apunte de financiacion:
    el credito de bienvenida sale del presupuesto base, nunca lo infla.
    El puente CREDIT→live_monthly_cap del 4.3-F sigue intacto para el gasto
    respaldado."""
    return CreditLedger.objects.filter(user=user, reason='PACK',
                                       delta__gt=0).exists()


@transaction.atomic
def spend(user, n, reason, post=None, claim=None, note='', fund=True):
    """Gasto atomico. Con fund=True (todo lo que autoriza analisis) crea el
    apunte de financiacion que sube el tope mensual — si el saldo esta
    respaldado por una compra real (6.6)."""
    assert n > 0
    w = CreditWallet.objects.select_for_update().get_or_create(user=user)[0]
    if w.balance < n:
        raise InsufficientCredits(n, w.balance)
    w.balance -= n
    w.save(update_fields=['balance'])
    CreditLedger.objects.create(user=user, delta=-n, reason=reason,
                                post=post, claim=claim, note=note)
    if fund and _respaldado(user):
        from apps.panel.models import Donation
        Donation.objects.create(method='CREDIT', amount_eur=n, verified=True,
                                post=post, note=f'créditos de {user.username}'[:200])
    return w.balance


def welcome_grant(user):
    """6.6: el credito de bienvenida — primer contacto con el producto de pago
    (regla de David 2026-11-09: revenue en cada cambio). Apagado de fabrica
    (`welcome_credits`=0); con tope diario anti-granja (`welcome_daily_max`).
    Devuelve los creditos dados (0 si no toca)."""
    from django.utils import timezone
    from apps.panel.models import SystemSetting
    n = SystemSetting.get_int('welcome_credits', 0)
    if n <= 0 or not user.is_active:
        return 0
    hoy = timezone.localdate()
    tope = SystemSetting.get_int('welcome_daily_max', 20)
    dados = CreditLedger.objects.filter(reason='WELCOME',
                                        created_at__date=hoy).count()
    if dados >= tope:
        return 0
    grant(user, n, reason='WELCOME', note='crédito de bienvenida')
    return n
