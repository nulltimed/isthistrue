"""Wiki de claims (wikitrue). Solo se crean paginas desde el flujo completo del
foro principal — NUNCA desde Off-Topic (decision de David, sobrepone al README v1)."""
from django.conf import settings
from django.db import models

try:
    from pgvector.django import VectorField
    HAS_PGVECTOR = True
except ImportError:  # desarrollo sin pgvector instalado
    HAS_PGVECTOR = False

COLORS = [('GREEN', '🟢 Verificado'), ('AMBER', '🟡 Engañoso o sin contexto'),
          ('RED', '🔴 Falso'), ('GREY', '⚪ No verificable')]


class Claim(models.Model):
    text_original = models.TextField()
    language = models.CharField(max_length=8, default='es')
    text_pivot_en = models.TextField(blank=True)  # pivote EN para deduplicacion
    slug = models.SlugField(max_length=140, unique=True, null=True, blank=True)  # 9B: /claim/la-tierra-es-plana/
    if HAS_PGVECTOR:
        embedding = VectorField(dimensions=384, null=True)  # MiniLM multilingue local
    color = models.CharField(max_length=6, choices=COLORS, default='GREY')
    consolidated = models.BooleanField(default=False)
    what_is_claimed = models.TextField(blank=True)
    what_evidence_says = models.TextField(blank=True)
    the_difference = models.TextField(blank=True)
    sensitive = models.CharField(max_length=10, blank=True, default='')
    # 4.2 C1: False = el veredicto se emitio con las busquedas de fuentes CAIDAS
    # (el 403 masivo de SearXNG del 2026-08-15). Reanalizable con
    # `manage.py reverdict_missing_sources`.
    sources_ok = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ClaimVersion(models.Model):
    """Historial completo en cada re-verificacion (transparencia total)."""
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='versions')
    color = models.CharField(max_length=6, choices=COLORS)
    body_snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class Source(models.Model):
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='sources')
    url = models.URLField(max_length=600)
    title = models.CharField(max_length=300, blank=True)


class ClaimAppearance(models.Model):
    """Cada aparicion: video + timestamp + cita literal + embed al segundo exacto."""
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='appearances')
    segment = models.ForeignKey('analysis.TranscriptSegment', on_delete=models.CASCADE,
                                related_name='claims')
    quote = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Report(models.Model):
    REASONS = [('TRANSCRIPT', 'Transcripción errónea'), ('BROKEN_SOURCE', 'Fuente rota'),
               ('DISPUTED', 'Veredicto discutible'), ('CONTEXT', 'Falta contexto'),
               ('AUTHOR', 'Soy el autor')]  # cola prioritaria, SLA publico 7 dias
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.CharField(max_length=14, choices=REASONS)
    body = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class ClaimSlugHistory(models.Model):
    """Redireccion 301 permanente al renombrar (candado del nombrado participativo)."""
    old_slug = models.SlugField(max_length=140, unique=True)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='old_slugs')


class Interlocutor(models.Model):
    """Persona hablante. SOLO figuras publicas tienen pagina (candado congelado).
    Particulares: JAMAS pagina, JAMAS nombre en URL. Sin huellas de voz nunca
    (solo con visto bueno ESCRITO del abogado de David, y no esta construido)."""
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=170, unique=True)
    # 4.3-C: raiz comun del nombre ('pedro-sanchez'). El slug unico puede llevar
    # sufijo ('pedro-sanchez-2'); el base_slug NO, y por eso es la clave de la
    # desambiguacion: /persona/pedro-sanchez/ con dos fichas detras enseña las dos
    # (decision de David: "aparecerán todos los personajes posibles indexados").
    base_slug = models.SlugField(max_length=170, blank=True, default='', db_index=True)
    is_public_figure = models.BooleanField(null=True)  # agente clasifica, David revisa
    # Identidad UNIVOCA (2026-08-17): el QID de Wikidata distingue homonimos
    # ('Q3128751') — dos personas con el mismo nombre son dos fichas distintas.
    wikidata_id = models.CharField(max_length=16, blank=True, default='', db_index=True)
    photo_url = models.URLField(max_length=400, blank=True, default='')  # Commons, licencia libre
    description = models.CharField(max_length=120, blank=True, default='')  # 'politico español'
    created_at = models.DateTimeField(auto_now_add=True)


class InterlocutorSlugHistory(models.Model):
    old_slug = models.SlugField(max_length=170, unique=True)
    interlocutor = models.ForeignKey(Interlocutor, on_delete=models.CASCADE, related_name='old_slugs')


class SpeakerNameProposal(models.Model):
    """Nombrado participativo (diseño de David): el sistema propone candidatos por
    hablante diarizado; votan los usuarios; el voto de moderador pesa mas
    (SystemSetting mod_vote_weight, por defecto 5) y desempata. Activo con la
    diarizacion del Hito 2B; el modelo nace ya para no romper la BD despues."""
    post = models.ForeignKey('analysis.Post', on_delete=models.CASCADE, related_name='name_proposals')
    speaker_label = models.CharField(max_length=20)  # 'SPEAKER_1'
    candidate_name = models.CharField(max_length=160)
    interlocutor = models.ForeignKey(Interlocutor, null=True, blank=True, on_delete=models.SET_NULL)
    photo_url = models.URLField(max_length=400, blank=True, default='')  # Wikidata/Commons (licencia libre)
    source = models.CharField(max_length=10, blank=True, default='')      # context|ocr|user
    # QID elegido en el autocompletado: convierte "un nombre escrito" en
    # "una persona identificada". Vacio = propuesta de texto libre (se acepta).
    wikidata_id = models.CharField(max_length=16, blank=True, default='')
    description = models.CharField(max_length=120, blank=True, default='')
    confirmed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('post', 'speaker_label', 'candidate_name')


class SpeakerNameVote(models.Model):
    proposal = models.ForeignKey(SpeakerNameProposal, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('proposal', 'user')

    def weight(self):
        from apps.panel.models import SystemSetting
        if self.user.effective_level() == 'MOD' or self.user.is_superuser:
            return SystemSetting.get_int('mod_vote_weight', 5)
        return 1


class ClaimFollow(models.Model):
    """Seguir claims (2B): la campana avisa de cambios de color y nuevas apariciones."""
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='followers')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('claim', 'user')
