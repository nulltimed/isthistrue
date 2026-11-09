"""Serie 6.22 (ordenes de David, 2026-11-09, 21:11): el barrido UNA VEZ de los
atrasados — «todo de golpe» — con la puerta 5.27-A INTACTA para lo nuevo
(literal: «ni una ni otra, tal y como está»).

Lanza el trabajo 2 (veredictos con fuentes) de los posts parados en
PENDING_VALIDATION SALTANDOSE LOS VOTOS, porque con la web privada casi nadie
vota y el atraso no se vaciaria nunca. La puerta de IDENTIFICACION (65 % de
voces) se respeta por defecto — «la identificacion no se compra, es calidad» —
y solo se salta con --sin-voces, bajo responsabilidad de quien lo teclea.

Uso:
  manage.py verificar_atrasados               # respeta el 65 % de voces
  manage.py verificar_atrasados --sin-voces   # salta tambien esa puerta
  manage.py verificar_atrasados --limite 5    # acota la tanda
Cada lanzamiento gasta dinero real (~3,83 EUR/hora de video).
"""
from django.core.management.base import BaseCommand

from apps.analysis.models import Post
from apps.analysis.services import identification_gate
from apps.analysis.tasks import launch_full_analysis


class Command(BaseCommand):
    help = 'Lanza la verificación con fuentes de los posts atrasados (sin esperar votos).'

    def add_arguments(self, parser):
        parser.add_argument('--sin-voces', action='store_true',
                            help='salta también la puerta del 65 %% de hablantes identificados')
        parser.add_argument('--limite', type=int, default=0,
                            help='máximo de posts a lanzar en esta tanda (0 = todos)')

    def handle(self, *args, **opts):
        lanzados, retenidos = [], []
        pendientes = Post.objects.filter(status='PENDING_VALIDATION',
                                         censored=False).order_by('pk')
        for post in pendientes:
            if opts['limite'] and len(lanzados) >= opts['limite']:
                break
            if not opts['sin_voces']:
                abierta, motivo = identification_gate(post)
                if not abierta:
                    retenidos.append((post.pk, motivo))
                    continue
            post.status = 'FULL_QUEUED'
            post.save(update_fields=['status'])
            launch_full_analysis(post)
            lanzados.append(post.pk)
        self.stdout.write(f'Lanzados: {len(lanzados)} {lanzados}')
        for pk, motivo in retenidos:
            self.stdout.write(f'Retenido {pk}: {motivo} (ponle nombres o usa --sin-voces)')
        if not lanzados and not retenidos:
            self.stdout.write('No hay posts atrasados en espera de votos.')
