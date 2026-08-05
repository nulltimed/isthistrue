"""
Nucleo del flujo Hito 2A: posts, validacion comunitaria, candados de presupuesto.
README v2 §4-§5.
"""
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

CATEGORIES = [('MAIN', 'Foro principal'), ('OFFTOPIC', 'Off-Topic')]
STATUSES = [
    ('NEW', 'Nuevo'),
    ('CHEAP_RUNNING', 'Fase barata en curso'),
    ('PENDING_VALIDATION', 'Pendiente de validación (5 votos / 3 días)'),
    ('FULL_QUEUED', 'Análisis completo en cola'),
    ('FULL_RUNNING', 'Análisis completo en curso'),
    ('DONE', 'Analizado'),
    ('OFFTOPIC_SIGNALED', 'Off-Topic con señales'),
    ('OFFTOPIC_RAW', 'Off-Topic sin analizar (voluntario)'),
    ('HELD_FOR_REVIEW', 'Retenido (anti-acoso)'),
    ('FAILED', 'Error'),
]


class Channel(models.Model):
    platform = models.CharField(max_length=20)
    external_id = models.CharField(max_length=200)
    name = models.CharField(max_length=200, blank=True)
    is_public_figure = models.BooleanField(null=True)  # clasificado por agente, revisable por David
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('platform', 'external_id')

    def meets_threshold(self):
        """Umbral 5/10/5 para ficha de canal (README v2 §9). Particulares: NUNCA."""
        if self.is_public_figure is False:
            return False
        posts = self.posts.filter(status='DONE')
        if posts.count() < 5:
            return False
        requesters = set()
        for p in posts:
            requesters.update(p.requests.values_list('user_id', flat=True))
        if len(requesters) < 10:
            return False
        videos_with_bad = posts.filter(
            transcript_segments__claims__color__in=['RED', 'AMBER'],
            transcript_segments__claims__consolidated=True).distinct().count()
        return videos_with_bad >= 5


class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    channel = models.ForeignKey(Channel, null=True, blank=True, on_delete=models.SET_NULL, related_name='posts')
    url = models.URLField(max_length=500)
    platform = models.CharField(max_length=20, default='unknown')
    external_id = models.CharField(max_length=200, blank=True)
    title = models.CharField(max_length=300, blank=True)
    duration_seconds = models.IntegerField(default=0)
    category = models.CharField(max_length=10, choices=CATEGORIES, default='MAIN')
    status = models.CharField(max_length=24, choices=STATUSES, default='NEW')
    voluntary_offtopic = models.BooleanField(default=False)  # coste CERO hasta 10 votos
    is_adult = models.BooleanField(default=False)            # marcado por autor/agente/moderador
    adult_flag_source = models.CharField(max_length=10, blank=True, default='')  # author|agent|mod
    manipulation_detected = models.BooleanField(default=False)
    relegation_reason = models.CharField(max_length=200, blank=True, default='')
    validation_deadline = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def distinct_validation_votes(self, kind):
        return self.validation_votes.filter(kind=kind).values('user').distinct().count()


class AnalysisRequest(models.Model):
    """Quien pulsa 'Analizar'. Cache: se sirve gratis pero CUENTA como solicitante."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    served_from_cache = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ValidationVote(models.Model):
    """VALIDATE: 5 distintos Contribuidor+ en 3 dias -> fase cara.
       RESCUE: 10 distintos Contribuidor+ en Off-Topic -> pipeline completo + ascenso."""
    KINDS = [('VALIDATE', 'Es factual'), ('RESCUE', 'Rescatar de Off-Topic')]
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='validation_votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=KINDS)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user', 'kind')


class TranscriptSegment(models.Model):
    """Transcripcion sincronizada: SIEMPRE y en todos lados, timestamps clicables."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='transcript_segments')
    start_seconds = models.FloatField()
    end_seconds = models.FloatField()
    text = models.TextField()
    # Señal barata anclada al segmento (Off-Topic y fase previa):
    SIGNALS = [('', '—'), ('FACTUAL_UNVERIFIED', 'Afirmación factual (no verificada)'),
               ('OPINION', 'Opinión'),
               ('CONTRADICTS_MODEL', '⚠️ Contradice conocimiento general del modelo, sin verificar')]
    signal = models.CharField(max_length=24, choices=SIGNALS, blank=True, default='')
    speaker_label = models.CharField(max_length=20, blank=True, default='')  # 'SPEAKER_1' (diarizacion 2B)

    class Meta:
        ordering = ['start_seconds']


class DailyBudget(models.Model):
    """El deposito de la gasolinera: se rellena cada dia, si se vacia se espera a mañana."""
    date = models.DateField(unique=True)
    spent_eur = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    @classmethod
    def try_spend(cls, amount_eur):
        from django.conf import settings as s
        with transaction.atomic():
            row, _ = cls.objects.select_for_update().get_or_create(date=timezone.localdate())
            if float(row.spent_eur) + amount_eur > s.DAILY_BUDGET_EUR:
                return False
            if not MonthlyCap.try_spend(amount_eur):
                return False
            row.spent_eur = models.F('spent_eur') + amount_eur
            row.save(update_fields=['spent_eur'])
            return True


class MonthlyCap(models.Model):
    """Corte duro mensual a 200 EUR: cola congelada hasta el dia 1."""
    year_month = models.CharField(max_length=7, unique=True)  # '2026-07'
    spent_eur = models.DecimalField(max_digits=9, decimal_places=4, default=0)

    @classmethod
    def try_spend(cls, amount_eur):
        from django.conf import settings as s
        ym = timezone.localdate().strftime('%Y-%m')
        row, _ = cls.objects.select_for_update().get_or_create(year_month=ym)
        if float(row.spent_eur) + amount_eur > s.MONTHLY_CAP_EUR:
            return False
        row.spent_eur = models.F('spent_eur') + amount_eur
        row.save(update_fields=['spent_eur'])
        return True
