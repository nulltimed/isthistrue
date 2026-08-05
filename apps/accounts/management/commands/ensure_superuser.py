"""Crea/actualiza el superusuario 'd' desde el .env (ADMIN_EMAIL, ADMIN_PASSWORD).
Se ejecuta en cada despliegue: nunca mas contraseñas pasadas por chat."""
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.accounts.models import User


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
            self.stdout.write(self.style.WARNING('ADMIN_EMAIL/ADMIN_PASSWORD vacios en .env: nada que hacer.'))
            return
        u, created = User.objects.get_or_create(username='d', defaults={
            'email': settings.ADMIN_EMAIL, 'is_staff': True, 'is_superuser': True,
            'level': 'MOD', 'email_verified': True})
        u.email = settings.ADMIN_EMAIL
        u.is_staff = u.is_superuser = u.email_verified = True
        u.set_password(settings.ADMIN_PASSWORD)
        u.save()
        self.stdout.write(self.style.SUCCESS(f"Superusuario 'd' {'creado' if created else 'actualizado'} desde .env."))
