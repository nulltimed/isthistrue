"""
Nucleo del flujo Hito 2A: posts, validacion comunitaria, candados de presupuesto.
README v2 §4-§5.
"""
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

CATEGORIES = [('MAIN', 'Foro principal'), ('OFFTOPIC', 'Off-Topic')]
TOPICS = [('politica', 'Política'), ('salud', 'Salud'), ('ciencia', 'Ciencia'),
          ('economia', 'Economía'), ('sucesos', 'Sucesos'), ('internacional', 'Internacional'),
          ('tecnologia', 'Tecnología'), ('medioambiente', 'Medioambiente'), ('deporte', 'Deporte'),
          ('cultura', 'Cultura'), ('sociedad', 'Sociedad'), ('otros', 'Otros')]
STATUSES = [
    ('NEW', 'Nuevo'),
    ('CHEAP_RUNNING', 'Fase barata en curso'),
    ('PENDING_VALIDATION', 'Pendiente de validación (5 votos / 3 días)'),
    ('FULL_QUEUED', 'Análisis completo en cola'),
    # 4.3-F (decision de David): un video que se lleva mas de media asignacion
    # diaria NO se analiza al momento — espera a que haya deposito, o a que
    # alguien lo apadrine con una donacion. Nunca se rechaza.
    ('AWAITING_BUDGET', 'En cola por presupuesto (esperando depósito o apadrinamiento)'),
    ('FULL_RUNNING', 'Análisis completo en curso'),
    ('DONE', 'Analizado'),
    ('OFFTOPIC_SIGNALED', 'Off-Topic con señales'),
    ('VALIDATION_EXPIRED', 'Validación expirada (a criterio de moderación)'),
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
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='analysis_posts')
    channel = models.ForeignKey(Channel, null=True, blank=True, on_delete=models.SET_NULL, related_name='posts')
    url = models.URLField(max_length=500)
    platform = models.CharField(max_length=20, default='unknown')
    external_id = models.CharField(max_length=200, blank=True)
    title = models.CharField(max_length=300, blank=True)
    # 5.0-C (decision de David): URL legible /post/nombre-del-video-legible/<pk>/.
    # Se genera UNA vez del primer titulo real y ya no cambia (las URLs compartidas
    # no se rompen); el pk final desambigua titulos repetidos. Sin titulo aun, la
    # URL numerica sigue siendo la canonica.
    slug = models.SlugField(max_length=80, blank=True, default='')
    duration_seconds = models.IntegerField(default=0)
    category = models.CharField(max_length=10, choices=CATEGORIES, default='MAIN')
    status = models.CharField(max_length=24, choices=STATUSES, default='NEW')
    voluntary_offtopic = models.BooleanField(default=False)  # coste CERO hasta 10 votos
    is_adult = models.BooleanField(default=False)            # marcado por autor/agente/moderador
    adult_flag_source = models.CharField(max_length=10, blank=True, default='')  # author|agent|mod
    manipulation_detected = models.BooleanField(default=False)
    relegation_reason = models.CharField(max_length=200, blank=True, default='')
    # 4.2 A2 (decision de David): NINGUN post va solo a Off-Topic. El clasificador
    # solo SUGIERE; relegar es accion manual de moderador.
    offtopic_suggested = models.BooleanField(default=False)
    # 4.2 A5: texto "Opina" del autor -> primer mensaje del hilo del foro.
    author_opinion = models.TextField(blank=True, default='')
    topic = models.CharField(max_length=16, choices=TOPICS, default='otros')
    tags = models.CharField(max_length=200, blank=True, default='')  # libres, separadas por comas
    # 4.4-B (decision de David): la fecha en que OCURRIO lo que se ve, que no es
    # la de subida. Sin ella, "mas trabajadores que nunca" no se puede contrastar:
    # no se sabe contra que tabla mirar. La deduce un agente barato con las pistas
    # del titulo y de toda la transcripcion; moderacion puede corregirla.
    event_date = models.DateField(null=True, blank=True)
    event_date_note = models.CharField(max_length=250, blank=True, default='')
    EVENT_DATE_SOURCES = [('', '—'), ('agent', 'Estimada por el sistema'),
                          ('mod', 'Corregida por moderación')]
    event_date_source = models.CharField(max_length=8, choices=EVENT_DATE_SOURCES,
                                         blank=True, default='')
    # 4.4-G (A.1 reformulado por David): cuantas voces hay, como PISTA para la
    # diarizacion. La deduce el agente de datacion en el mismo viaje (coste cero)
    # y moderacion puede corregirla desde la llave inglesa. No se pregunta jamas
    # al usuario corriente.
    speakers_count = models.PositiveSmallIntegerField(null=True, blank=True)
    speakers_confidence = models.CharField(max_length=8, blank=True, default='')
    SPEAKERS_SOURCES = [('', '—'), ('agent', 'Estimado por el sistema'),
                        ('mod', 'Corregido por moderación')]
    speakers_count_source = models.CharField(max_length=8, choices=SPEAKERS_SOURCES,
                                             blank=True, default='')
    validation_deadline = models.DateTimeField(null=True, blank=True)
    opus_rescanned = models.BooleanField(default=False)  # candado: UNA vez por post
    # 4.2 D4: aviso de Trending enviado (se rearma al salir del umbral).
    trending_notified = models.BooleanField(default=False)
    # 4.3-D: cronometro del analisis (peticion del operador, docs/33 C2). Van aqui
    # y no en AnalysisRequest porque el analisis ocurre UNA vez por post, mientras
    # que solicitantes puede haber muchos: N relojes para un solo cronometraje.
    cheap_started_at = models.DateTimeField(null=True, blank=True)
    # 4.10-A: el trabajo remoto de AssemblyAI en vuelo (webhook). Vacio = ninguno.
    aai_job_id = models.CharField(max_length=64, blank=True, default='')
    cheap_finished_at = models.DateTimeField(null=True, blank=True)
    full_started_at = models.DateTimeField(null=True, blank=True)
    full_finished_at = models.DateTimeField(null=True, blank=True)
    transcribe_seconds = models.FloatField(default=0.0)   # faster-whisper
    diarize_seconds = models.FloatField(default=0.0)      # pyannote
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.title and not self.slug:
            from django.utils.text import slugify
            s = slugify(self.title)[:80].rstrip('-')
            if s:
                self.slug = s
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        if self.slug:
            return reverse('post_detail_slug', kwargs={'slug': self.slug, 'pk': self.pk})
        return reverse('post_detail', kwargs={'pk': self.pk})

    def analysis_times(self):
        """Resumen legible para el informe del operador."""
        def dur(a, b):
            return round((b - a).total_seconds(), 1) if (a and b) else None
        return {'minutos_video': round((self.duration_seconds or 0) / 60.0, 1),
                'transcribir_s': round(self.transcribe_seconds, 1),
                'diarizar_s': round(self.diarize_seconds, 1),
                'fase_barata_s': dur(self.cheap_started_at, self.cheap_finished_at),
                'fase_completa_s': dur(self.full_started_at, self.full_finished_at)}

    def trending_votes(self):
        """Votos dentro de la ventana viva (SystemSetting trending_window_days)."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.panel.models import SystemSetting
        days = SystemSetting.get_int('trending_window_days', 7)
        return self.votes.filter(created_at__gte=timezone.now() - timedelta(days=days)).count()

    def is_trending(self):
        """4.2 D4: Trending mientras los votos de la ventana alcanzan el umbral
        (SystemSetting trending_votes_threshold; los dos ajustables desde BD/panel)."""
        from apps.panel.models import SystemSetting
        return self.trending_votes() >= SystemSetting.get_int('trending_votes_threshold', 5)

    def distinct_validation_votes(self, kind):
        return self.validation_votes.filter(kind=kind).values('user').distinct().count()


class PostSubscription(models.Model):
    """4.2 D3: campanita del post. El usuario elige a QUE se suscribe."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='subscriptions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='post_subscriptions')
    on_analysis = models.BooleanField(default=True)   # cambios en el analisis (fases)
    on_messages = models.BooleanField(default=False)  # nuevos mensajes del hilo
    on_trending = models.BooleanField(default=False)  # el post entra en Trending
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')


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


class CostEntry(models.Model):
    """4.9-A: un apunte del libro de cuentas — cada gasto real, con su post
    cuando lo hay. De aqui salen el desglose por analisis (transparencia con
    las donaciones) y los topes mensuales por proveedor."""
    post = models.ForeignKey('Post', null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='costs')
    provider = models.CharField(max_length=20)   # anthropic|assemblyai|runpod|brevo
    concept = models.CharField(max_length=40)
    eur = models.DecimalField(max_digits=8, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class InnocuousPhrase(models.Model):
    """4.8-B (politica de David, 2026-08-30): frases sin informacion factual
    que un separador atribuyo a una voz fantasma. Sonnet decide UNA sola cosa
    (¿contiene informacion verificable?); si no, la frase se elimina del
    transcript y se guarda aqui NORMALIZADA. La base CRECE con cada video y
    los siguientes la consultan antes que a nadie: cero coste, cero adivinanza."""
    text_norm = models.CharField(max_length=200, unique=True)
    times_seen = models.PositiveIntegerField(default=1)
    first_post = models.ForeignKey('Post', null=True, blank=True,
                                   on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)


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
    opus_rescanned = models.BooleanField(default=False)  # 4.2 H5: UNA vez por oracion
    # 4.4-I (David): la pasada de sentido puede no estar segura de quien dijo
    # una frase. Marcada asi, la frase aparece en «¿Quien habla?» para que la
    # comunidad la resuelva, NO cuenta para la puerta del 65 % y NO se cuelga
    # de ninguna persona en la wiki hasta que alguien la resuelva.
    attribution_uncertain = models.BooleanField(default=False)
    attribution_note = models.CharField(max_length=160, blank=True, default='')

    class Meta:
        ordering = ['start_seconds']


class SegmentVote(models.Model):
    """4.2 H5 (decision de David): tras los veredictos, cada ORACION se puede votar
    arriba o abajo. Umbral de abajos (SystemSetting segment_opus_downvotes, 5,
    editable por mods/superusuario) -> esa oracion se re-analiza con Opus."""
    segment = models.ForeignKey(TranscriptSegment, on_delete=models.CASCADE,
                                related_name='sentence_votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    value = models.SmallIntegerField()  # +1 / -1
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('segment', 'user')


class DailyBudget(models.Model):
    """El deposito de la gasolinera: se rellena cada dia, si se vacia se espera a mañana."""
    date = models.DateField(unique=True)
    spent_eur = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    @classmethod
    def try_spend(cls, amount_eur):
        from apps.panel.services import live_daily_budget, alert_admin
        with transaction.atomic():
            row, _ = cls.objects.select_for_update().get_or_create(date=timezone.localdate())
            if float(row.spent_eur) + amount_eur > live_daily_budget():
                alert_admin('Presupuesto diario agotado',
                            f'Gasto de hoy: {row.spent_eur} EUR. La cola espera a mañana.')
                return False
            if not MonthlyCap.try_spend(amount_eur):
                return False
            row.spent_eur = models.F('spent_eur') + amount_eur
            row.save(update_fields=['spent_eur'])
            # 4.9-A: el mismo peaje deja apunte en el libro, colgado del post
            # en curso del worker (transparencia de donaciones).
            from apps.analysis import costs
            costs.record('anthropic', 'analisis', amount_eur)
            return True


class MonthlyCap(models.Model):
    """Corte duro mensual a 200 EUR: cola congelada hasta el dia 1."""
    year_month = models.CharField(max_length=7, unique=True)  # '2026-07'
    spent_eur = models.DecimalField(max_digits=9, decimal_places=4, default=0)

    @classmethod
    def try_spend(cls, amount_eur):
        from apps.panel.services import live_monthly_cap, alert_admin
        ym = timezone.localdate().strftime('%Y-%m')
        row, _ = cls.objects.select_for_update().get_or_create(year_month=ym)
        cap, _, _ = live_monthly_cap()
        if float(row.spent_eur) + amount_eur > cap:
            alert_admin('CORTE MENSUAL alcanzado',
                        f'Gasto del mes: {row.spent_eur} EUR (techo vivo {cap}). Cola congelada hasta el dia 1.')
            return False
        row.spent_eur = models.F('spent_eur') + amount_eur
        row.save(update_fields=['spent_eur'])
        return True
