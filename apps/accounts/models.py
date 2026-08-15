"""
Cuentas: niveles, karma, cupos, sliders de contenido y codigos canjeables.
Decisiones congeladas: README v2 §7 y §10.
"""
import secrets
from datetime import date
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

LEVELS = [('NEW', 'Nuevo'), ('CONTRIB', 'Contribuidor'), ('VERIF', 'Verificador'),
          ('VET', 'Veterano'), ('MOD', 'Moderador')]
KARMA_THRESHOLDS = {'NEW': 0, 'CONTRIB': 50, 'VERIF': 250, 'VET': 1000}
DAILY_QUOTA = {'NEW': 10, 'CONTRIB': 50, 'VERIF': 100, 'VET': 500, 'MOD': 500}
LEVEL_ORDER = ['NEW', 'CONTRIB', 'VERIF', 'VET', 'MOD']


class User(AbstractUser):
    karma = models.IntegerField(default=0)
    level = models.CharField(max_length=8, choices=LEVELS, default='NEW')
    # Nivel regalado por codigo canjeable (privilegios sin karma; revocable):
    granted_level = models.CharField(max_length=8, choices=LEVELS, blank=True, default='')
    birth_date = models.DateField(null=True, blank=True)
    # Sliders del panel de cuenta (compartido foro+wiki):
    hide_adult = models.BooleanField(default=True)
    hide_opinions = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    # Avatares (quiz 5B): subida libre + chequeo de vision con Haiku; mod puede retirar
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    avatar_approved = models.BooleanField(default=True)
    # Notificaciones (Brevo, decision congelada; jamas el Postfix personal)
    NOTIFY_MODES = [('WEB', 'Solo campana'), ('INSTANT', 'Email inmediato'),
                    ('DAILY', 'Resumen diario')]
    notify_mode = models.CharField(max_length=8, choices=NOTIFY_MODES, default='WEB')
    # Espejo de pruebas: invitado por David desde el panel
    staging_invited = models.BooleanField(default=False)
    allow_friend_requests = models.BooleanField(default=True)  # desactivable (candado)
    # 4.2 H8: buzon de mensajes privados. CERRADO por defecto (factura vista: canal
    # invisible a la moderacion comunitaria); mods/superusuario siempre pueden escribir.
    accept_private_messages = models.BooleanField(default=False)

    @property
    def age(self):
        if not self.birth_date:
            return None
        today = date.today()
        return today.year - self.birth_date.year - (
            (today.month, today.day) < (self.birth_date.month, self.birth_date.day))

    @property
    def is_adult(self):
        return self.age is not None and self.age >= 18

    def effective_level(self):
        """Nivel real por karma vs. nivel regalado: gana el mas alto."""
        if self.level == 'MOD':
            return 'MOD'
        earned = 'NEW'
        for lvl in ['VET', 'VERIF', 'CONTRIB']:
            if self.karma >= KARMA_THRESHOLDS[lvl]:
                earned = lvl
                break
        if self.granted_level and LEVEL_ORDER.index(self.granted_level) > LEVEL_ORDER.index(earned):
            return self.granted_level
        return earned

    def is_contrib_plus(self):
        return LEVEL_ORDER.index(self.effective_level()) >= LEVEL_ORDER.index('CONTRIB')

    def daily_quota(self):
        return DAILY_QUOTA[self.effective_level()]

    def credits_used_today(self):
        today = timezone.localdate()
        return self.credits.filter(created_at__date=today).count()

    def can_spend_credit(self):
        return self.credits_used_today() < self.daily_quota()


class AnalysisCredit(models.Model):
    """1 credito = 1 tramo de 20 min analizado. Se consume SIN devolucion."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credits')
    post = models.ForeignKey('analysis.Post', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ReputationEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reputation_events')
    delta = models.IntegerField()
    reason = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)


# --- Codigos canjeables (README v2 §7) ---
CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'  # sin 0/O ni 1/l/I

def _make_code():
    def block():
        return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(4))
    return f'ISTT-{block()}-{block()}'


class RedeemCode(models.Model):
    GRANTABLE = [('CONTRIB', 'Contribuidor'), ('VERIF', 'Verificador'), ('VET', 'Veterano')]
    # Moderador NUNCA por codigo (solo manual desde el panel).
    code = models.CharField(max_length=16, unique=True, default=_make_code)
    grants_level = models.CharField(max_length=8, choices=GRANTABLE)
    batch = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    redeemed_by = models.ForeignKey(User, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='redeemed_codes')
    redeemed_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)  # revocacion SILENCIOSA

    def redeem(self, user):
        if self.redeemed_by or self.revoked:
            return False
        self.redeemed_by = user
        self.redeemed_at = timezone.now()
        self.save(update_fields=['redeemed_by', 'redeemed_at'])
        if LEVEL_ORDER.index(self.grants_level) > LEVEL_ORDER.index(user.granted_level or 'NEW'):
            user.granted_level = self.grants_level
            user.save(update_fields=['granted_level'])
        return True

    def revoke(self):
        """Silencioso: sin email. El usuario vuelve al nivel por karma real."""
        self.revoked = True
        self.save(update_fields=['revoked'])
        u = self.redeemed_by
        if u and u.granted_level == self.grants_level:
            u.granted_level = ''
            u.save(update_fields=['granted_level'])


class Notification(models.Model):
    """La campana. El email (segun notify_mode) sale por Brevo desde services.notify()."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    text = models.CharField(max_length=300)
    url = models.CharField(max_length=300, blank=True, default='')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class PrivateMessage(models.Model):
    """4.2 H8: MP simple con texto enriquecido (Markdown, HTML escapado).
    Salvaguardas: buzon opt-in, bloqueos mandan, boton Reportar eleva a mods."""
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pm_sent')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pm_received')
    body = models.TextField(max_length=8000)
    read = models.BooleanField(default=False)
    reported = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class StagingInvite(models.Model):
    """Invitacion al espejo enviada por email desde el panel (decision de David)."""
    email = models.EmailField()
    token = models.CharField(max_length=40, unique=True)
    can_admin = models.BooleanField(default=False)  # permisos seleccionables en ajustes
    accepted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class Friendship(models.Model):
    """Amistad (2B) con candados congelados: SIN mensajeria (da visibilidad, no chat)."""
    STATUSES = [('PENDING', 'Pendiente'), ('ACCEPTED', 'Aceptada'), ('DECLINED', 'Rechazada')]
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_sent')
    addressee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_received')
    status = models.CharField(max_length=10, choices=STATUSES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('requester', 'addressee')


class UserBlock(models.Model):
    """Bloqueo de usuario (candado): corta solicitudes y visibilidad mutua."""
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocks')
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('blocker', 'blocked')
