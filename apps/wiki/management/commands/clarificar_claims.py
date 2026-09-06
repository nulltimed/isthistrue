"""5.6-A: clarificar a mano las afirmaciones sin resolver (UNDECIDED).

    manage.py clarificar_claims [--post N] [--limit N] [--dry]

Cada claim pasa por el fusible del presupuesto diario. El gasto real queda
apuntado en el libro como siempre (5.3-D).
"""
from django.core.management.base import BaseCommand

from apps.wiki.models import Claim


class Command(BaseCommand):
    help = 'Segunda pasada de última instancia sobre los claims UNDECIDED'

    def add_arguments(self, parser):
        parser.add_argument('--post', type=int, default=None)
        parser.add_argument('--limit', type=int, default=50)
        parser.add_argument('--dry', action='store_true',
                            help='solo listar, sin llamar al modelo')

    def handle(self, *args, **opts):
        from apps.agents import clarify
        from apps.analysis.models import DailyBudget
        qs = Claim.objects.filter(color='UNDECIDED')
        if opts['post']:
            qs = qs.filter(appearances__segment__post_id=opts['post'])
        qs = qs.distinct().order_by('pk')[:opts['limit']]
        total = resueltos = 0
        for c in qs:
            total += 1
            if opts['dry']:
                self.stdout.write(f'  #{c.pk} «{c.text_original[:80]}»')
                continue
            if not DailyBudget.try_spend(clarify.COST_PER_CLAIM_EUR):
                self.stdout.write(self.style.WARNING('Presupuesto agotado: paro.'))
                break
            # 5.7 (leccion de la primera tanda real): una excepcion en UN claim
            # mataba la tanda ENTERA en silencio (17 sin tocar). Blindaje por
            # claim, como en run_pending.
            try:
                color = clarify.clarify_claim(c)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'  #{c.pk} ERROR {exc!r}'))
                self.stdout.flush()
                continue
            marca = {'GREEN': '🟢', 'AMBER': '🟡', 'RED': '🔴',
                     'GREY': '💭', 'UNDECIDED': '🔍'}.get(color, '·')
            self.stdout.write(f'  #{c.pk} → {color or "sin cambio"} {marca} '
                              f'«{c.text_original[:70]}»')
            if color not in (None, 'UNDECIDED'):
                resueltos += 1
        self.stdout.write(self.style.SUCCESS(
            f'{resueltos} de {total} clarificados.'))
