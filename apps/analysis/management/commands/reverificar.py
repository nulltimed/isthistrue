"""4.4-B: vuelve a verificar posts ya analizados, conservando los hablantes.

    python manage.py reverificar --post 4
    python manage.py reverificar --todos --confirmar

Sin --confirmar solo enseña lo que haría y cuánto costaría: reverificar cuesta
dinero real y pasa por el fusible del presupuesto como cualquier otro análisis.
"""
from django.core.management.base import BaseCommand

from apps.analysis.models import Post
from apps.analysis.services import cost_full_eur
from apps.analysis.tasks import reverify_post
from apps.wiki.models import ClaimAppearance


class Command(BaseCommand):
    help = 'Reverifica posts conservando transcripción, diarización e identificaciones.'

    def add_arguments(self, parser):
        parser.add_argument('--post', type=int, help='pk de un post concreto')
        parser.add_argument('--todos', action='store_true', help='todos los analizados')
        parser.add_argument('--confirmar', action='store_true', help='hazlo de verdad')

    def handle(self, *args, **op):
        if op.get('post'):
            posts = Post.objects.filter(pk=op['post'])
        elif op.get('todos'):
            posts = Post.objects.filter(status__in=['DONE', 'OFFTOPIC_SIGNALED'])
        else:
            self.stderr.write('Indica --post N o --todos')
            return
        total = 0.0
        for p in posts:
            n = ClaimAppearance.objects.filter(segment__post=p).count()
            coste = cost_full_eur(p)
            total += coste
            self.stdout.write(f'post {p.pk} · {p.transcript_segments.count()} frases · '
                              f'{n} veredictos actuales · coste estimado {coste:.2f} EUR')
            if op.get('confirmar'):
                reverify_post.delay(p.pk)
        self.stdout.write(self.style.WARNING(f'TOTAL estimado: {total:.2f} EUR'))
        if not op.get('confirmar'):
            self.stdout.write('Simulación. Añade --confirmar para lanzarlo de verdad.')
