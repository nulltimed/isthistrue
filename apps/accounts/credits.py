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


@transaction.atomic
def spend(user, n, reason, post=None, claim=None, note='', fund=True):
    """Gasto atomico. Con fund=True (todo lo que autoriza analisis) crea el
    apunte de financiacion que sube el tope mensual."""
    assert n > 0
    w = CreditWallet.objects.select_for_update().get_or_create(user=user)[0]
    if w.balance < n:
        raise InsufficientCredits(n, w.balance)
    w.balance -= n
    w.save(update_fields=['balance'])
    CreditLedger.objects.create(user=user, delta=-n, reason=reason,
                                post=post, claim=claim, note=note)
    if fund:
        from apps.panel.models import Donation
        Donation.objects.create(method='CREDIT', amount_eur=n, verified=True,
                                post=post, note=f'créditos de {user.username}'[:200])
    return w.balance
