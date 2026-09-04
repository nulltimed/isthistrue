"""5.1-C0: fusionar los claims DUPLICADOS que dejo el dedupe roto (docs/68).

Criterio (cientifico y automatico): entre copias del MISMO texto gana el
veredicto CONSOLIDADO mas reciente — la evidencia mas nueva manda. Todo lo
demas se absorbe (apariciones, historial, seguidores, reportes) y los slugs
absorbidos quedan como redireccion 301 (ClaimSlugHistory: ningun enlace se
rompe). Por defecto ENSAYO (solo cuenta); --aplicar ejecuta.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.wiki.models import Claim, ClaimFollow, ClaimSlugHistory


def _norma(texto):
    return re.sub(r'\s+', ' ', (texto or '').strip().lower())


class Command(BaseCommand):
    help = 'Fusiona claims con texto identico (ensayo por defecto; --aplicar ejecuta).'

    def add_arguments(self, parser):
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opts):
        grupos = {}
        for c in Claim.objects.all().order_by('pk'):
            grupos.setdefault(_norma(c.text_original), []).append(c)
        dups = {k: v for k, v in grupos.items() if len(v) > 1}
        self.stdout.write(f'grupos duplicados: {len(dups)} '
                          f'({sum(len(v) for v in dups.values())} claims)')
        if not opts['aplicar']:
            for k, v in list(dups.items())[:10]:
                self.stdout.write(f'  «{k[:70]}» x{len(v)}: '
                                  + ', '.join(f'{c.pk}/{c.color}' for c in v))
            self.stdout.write('ENSAYO — nada tocado. Ejecuta con --aplicar.')
            return
        fusionados = 0
        for copias in dups.values():
            consolidadas = [c for c in copias if c.consolidated]
            candidatas = consolidadas or copias
            superviviente = max(candidatas, key=lambda c: c.updated_at)
            with transaction.atomic():
                for otra in copias:
                    if otra.pk == superviviente.pk:
                        continue
                    otra.appearances.update(claim=superviviente)
                    otra.versions.update(claim=superviviente)
                    otra.reports.update(claim=superviviente)
                    for f in otra.followers.all():
                        ClaimFollow.objects.get_or_create(claim=superviviente,
                                                          user=f.user)
                    otra.old_slugs.update(claim=superviviente)
                    if otra.slug:
                        ClaimSlugHistory.objects.get_or_create(
                            old_slug=otra.slug,
                            defaults={'claim': superviviente})
                    otra.delete()
                    fusionados += 1
        self.stdout.write(f'fusionados (absorbidos): {fusionados}')
