"""6.5: backfill del rastreo de origen, como comando de verdad.

Hasta ahora el barrido de claims antiguos era un one-liner dictado por chat;
esto lo fija en el repo con los mismos candados que el rastreo automatico
(fusible de presupuesto por claim, solo ROJOS y AMBAR). Con --reintentar
recoge tambien los FAILED — pensado para despues del arreglo del JSON
truncado (6.5): la tanda del 2026-11-08 dejo ~16 claims en FAILED que ahora
si deberian salir.

    manage.py rastrear_origen                  # pendientes ('' = nunca intentados)
    manage.py rastrear_origen --reintentar     # tambien los FAILED
    manage.py rastrear_origen --limite 10      # tope de la tanda (25 de fabrica)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Rastrea el origen de los claims ROJOS/AMBAR sin cadena (fusible de presupuesto).'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=25,
                            help='Maximo de claims en esta tanda (25).')
        parser.add_argument('--reintentar', action='store_true',
                            help='Incluir los que fallaron (origin_status=FAILED).')

    def handle(self, *args, **opts):
        from apps.agents import origin
        from apps.analysis.models import DailyBudget
        from apps.wiki.models import Claim
        estados = ['', 'FAILED'] if opts['reintentar'] else ['']
        claims = (Claim.objects.filter(color__in=('RED', 'AMBER'),
                                       origin_status__in=estados,
                                       appearances__isnull=False)
                  .distinct().order_by('pk')[:opts['limite']])
        hechos, fallos = 0, 0
        for c in claims:
            if not DailyBudget.try_spend(origin.COST_PER_CLAIM_EUR):
                self.stdout.write(self.style.WARNING(
                    'Sin presupuesto hoy: la tanda para aqui. Vuelve a lanzarlo manana.'))
                break
            try:
                if origin.trace_claim(c):
                    hechos += 1
                else:
                    fallos += 1
            except Exception as exc:  # fail-soft: un claim roto no tumba la tanda
                fallos += 1
                self.stderr.write(f'Claim {c.pk}: {exc!r}')
        self.stdout.write(self.style.SUCCESS(
            f'cadenas nuevas publicadas: {hechos} · fallos: {fallos}'))
