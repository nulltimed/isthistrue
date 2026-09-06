"""5.4-B: poner titulo IA a los claims historicos que no lo tienen."""
from django.core.management.base import BaseCommand

from apps.wiki.models import Claim
from apps.wiki.services import _titulo_ia


class Command(BaseCommand):
    help = 'Genera el titulo corto (modelo deep) de los claims sin titulo.'

    def handle(self, *args, **opts):
        pendientes = Claim.objects.filter(title='')
        total, hechos = pendientes.count(), 0
        for c in pendientes.iterator():
            post = None
            a = c.appearances.select_related('segment__post').first()
            if a:
                post = a.segment.post
            if post is None:
                continue
            c.title = _titulo_ia(post, c, {})
            c.save(update_fields=['title'])
            hechos += 1
            if hechos % 25 == 0:
                self.stdout.write(f'  {hechos}/{total}...')
        self.stdout.write(f'titulados: {hechos}/{total}')
