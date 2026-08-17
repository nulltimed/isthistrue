"""Panel del superusuario 'd': settings vivos, auditoria, donaciones, codigos."""
from django.conf import settings
from django.db import models


class SystemSetting(models.Model):
    """Umbrales tocables desde el panel sin tocar codigo (README v2 §12).
    Claves usadas: opinion_ratio_percent(70), minutes_per_factual_claim(5),
    votes_to_validate(5), votes_to_rescue(10), validation_window_days(3),
    startup_mode_min_users(50), donation_goal_eur, lang_es(1), lang_en(1)."""
    key = models.CharField(max_length=60, unique=True)
    value = models.CharField(max_length=200)

    @classmethod
    def get_int(cls, key, default=None):
        """Orden de mando (4.3-A.7): fila del panel > valor del .env > default del
        codigo. Asi un umbral que nunca se sembro respeta el .env en vez de un
        numero escondido en el codigo."""
        row = cls.objects.filter(key=key).first()
        if row is not None:
            try:
                return int(row.value)
            except (TypeError, ValueError):
                pass
        try:
            return int(getattr(settings, 'SETTING_DEFAULTS', {})[key])
        except (KeyError, TypeError, ValueError):
            pass
        return default


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=120)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Donation(models.Model):
    METHODS = [('PAYPAL', 'PayPal'), ('BIZUM', 'Bizum'), ('OTHER', 'Otro')]
    amount_eur = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=8, choices=METHODS)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BackupRun(models.Model):
    KINDS = [('DAILY', 'Diaria'), ('WEEKLY', 'Semanal'), ('MILESTONE', 'Hito'),
             ('MANUAL', 'Manual'), ('PANIC', 'Pánico')]
    kind = models.CharField(max_length=10, choices=KINDS)
    ok = models.BooleanField(default=False)
    log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CodeBatch(models.Model):
    """Lote de codigos canjeables. >10.000 => generacion en segundo plano."""
    level = models.CharField(max_length=8)
    count = models.IntegerField()
    status = models.CharField(max_length=10, default='PENDING')  # PENDING|READY|FAILED
    file = models.FileField(upload_to='code_batches/', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


class ContentComplaint(models.Model):
    """Reclamacion DSA con acuse de recibo y registro (ademas de "soy el autor")."""
    REASONS = [('DEFAMATION', 'Considero que me difama'), ('ERROR', 'Error factual'),
               ('COPYRIGHT', 'Propiedad intelectual'), ('PRIVACY', 'Privacidad'),
               ('OTHER', 'Otro')]
    email = models.EmailField(blank=True)
    content_url = models.CharField(max_length=400)
    reason = models.CharField(max_length=12, choices=REASONS, default='OTHER')
    body = models.TextField()
    status = models.CharField(max_length=12, default='OPEN')  # OPEN|RESOLVED|REJECTED
    created_at = models.DateTimeField(auto_now_add=True)
