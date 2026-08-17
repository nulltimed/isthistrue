"""Siembra los umbrales en la base de datos tomandolos del .env.

4.3-A.7: la lista ya NO vive aqui duplicada (habia una clave repetida y se
desincronizaba con settings.py). La fuente unica es settings.SETTING_DEFAULTS,
que lee cada umbral del .env con su nombre en MAYUSCULAS.

  seed_settings           -> create-if-missing (no pisa lo que un mod ya guardo)
  seed_settings --force   -> pisa CON lo que diga el .env (usalo cuando cambies
                             un umbral en el .env y quieras que mande de verdad)
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.panel.models import SystemSetting


class Command(BaseCommand):
    help = 'Siembra los umbrales del panel desde settings.SETTING_DEFAULTS (.env).'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='Sobrescribe los valores ya guardados con los del .env.')

    def handle(self, *args, **options):
        creados = pisados = 0
        for k, v in settings.SETTING_DEFAULTS.items():
            if options['force']:
                _obj, creado = SystemSetting.objects.update_or_create(
                    key=k, defaults={'value': v})
                creados += 1 if creado else 0
                pisados += 0 if creado else 1
            else:
                _obj, creado = SystemSetting.objects.get_or_create(
                    key=k, defaults={'value': v})
                creados += 1 if creado else 0
        self.stdout.write(self.style.SUCCESS(
            f'Umbrales sembrados: {creados} nuevos, {pisados} sobrescritos.'))
