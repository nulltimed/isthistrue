"""Pase 4.2 F1: rellena titulo y duracion de los posts YA existentes (los de la
siembra nacieron sin titulo porque los metadatos de yt-dlp se descartaban).
Solo metadatos: NO descarga multimedia, no gasta deposito.
    docker compose exec worker python manage.py backfill_titles
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Rellena post.title y duration_seconds de los posts sin título (solo metadatos).'

    def handle(self, *args, **opts):
        import yt_dlp
        from apps.analysis.models import Post
        pending = Post.objects.filter(title='')
        self.stdout.write(f'{pending.count()} post(s) sin título.')
        ydl = yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True})
        for post in pending:
            try:
                info = ydl.extract_info(post.url, download=False) or {}
            except Exception as exc:
                self.stderr.write(f'  post {post.pk}: {exc!r}')
                continue
            if info.get('title'):
                post.title = str(info['title'])[:300]
                if info.get('duration') and not post.duration_seconds:
                    post.duration_seconds = int(info['duration'])
                post.save(update_fields=['title', 'duration_seconds'])
                self.stdout.write(f'  ✓ post {post.pk}: {post.title[:60]}')
        self.stdout.write(self.style.SUCCESS('Hecho.'))
