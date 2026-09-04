"""5.1-B.2: rellenar los embeddings que el deduplicador calculo y tiro.

GRATIS: usa el modelo local (sentence-transformers) sobre el pivote EN si
existe o el texto original si no — sin ninguna llamada de API. La malla de
«Afirmaciones relacionadas» se enciende con esto.
"""
from django.core.management.base import BaseCommand

from apps.wiki.models import Claim
from apps.wiki.services import _embed


class Command(BaseCommand):
    help = 'Rellena Claim.embedding donde falte (modelo local, gratis).'

    def handle(self, *args, **opts):
        pendientes = Claim.objects.filter(embedding__isnull=True)
        total, hechos = pendientes.count(), 0
        for claim in pendientes.iterator():
            emb = _embed(claim.text_pivot_en or claim.text_original)
            if emb is None:
                self.stdout.write(f'  sin modelo — abandono en {hechos}/{total}')
                return
            Claim.objects.filter(pk=claim.pk).update(embedding=emb)
            hechos += 1
        self.stdout.write(f'embeddings rellenados: {hechos}/{total}')
