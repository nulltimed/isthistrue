"""Crea los foros Principal y Off-Topic de machina (ejecutar tras migrate)."""
from django.core.management.base import BaseCommand
from apps.forum.machina_glue import get_or_create_forums


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        main, off = get_or_create_forums()
        self.stdout.write(self.style.SUCCESS(f'Foros listos: {main.name}, {off.name}. '
            'Configura permisos por defecto en /admin/ (Forum permissions) — paso del checklist.'))
