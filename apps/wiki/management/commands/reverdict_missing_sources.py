"""Pase 4.2 C1: re-encola el analisis completo de los posts cuyos claims se
veredictaron SIN FUENTES (sources_ok=False; 403 masivo de SearXNG 2026-08-15).
Pasa por try_spend como todo: coste real ~0,07 EUR/post. Lo dispara David:
    docker compose exec web python manage.py reverdict_missing_sources
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Re-analiza los posts con claims veredictados sin fuentes (sources_ok=False).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo listar, sin encolar nada.')

    def handle(self, *args, **opts):
        from apps.wiki.models import Claim
        from apps.analysis.models import Post
        from apps.analysis.tasks import launch_full_analysis
        post_ids = set(Claim.objects.filter(sources_ok=False)
                       .values_list('appearances__segment__post_id', flat=True))
        post_ids.discard(None)
        posts = Post.objects.filter(pk__in=post_ids)
        self.stdout.write(f'{posts.count()} post(s) con claims sin fuentes: '
                          f'{sorted(post_ids)}')
        if opts['dry_run']:
            return
        for post in posts:
            launch_full_analysis(post)
            self.stdout.write(f'  → re-encolado post {post.pk} ({post.title or post.url})')
        self.stdout.write(self.style.SUCCESS('Hecho. El presupuesto manda: si el '
                          'deposito diario se agota, la cola espera a mañana.'))
