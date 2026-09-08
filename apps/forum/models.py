from django.conf import settings
from django.db import models


class ModerationCase(models.Model):
    """Expediente de la cascada Haiku->Sonnet. El moderador siempre puede revertir."""
    KINDS = [('NOVICE_DECIDED', 'Novato: agente decidió'), ('WARNING', 'Advertencia 48 h')]
    machina_post_id = models.IntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=16, choices=KINDS)
    agent_action = models.CharField(max_length=10, blank=True)
    agent_reason = models.CharField(max_length=300, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    outcome = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)


class TopicRead(models.Model):
    """4.3-A J4: hasta donde leyo cada usuario en cada hilo — alimenta el separador
    «nuevos desde tu ultima visita» y el boton de saltar al ultimo no leido."""
    topic_id = models.IntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_post_id = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('topic_id', 'user')


class MessageSensitive(models.Model):
    """4.2 H1: mensaje difuminado PARA TODOS ("puede ser sensible; clic para verlo").
    Origen: moderador/superusuario a mano, expediente Haiku, o umbral de reportes."""
    machina_post_id = models.IntegerField(unique=True)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL)
    auto = models.BooleanField(default=False)  # True = Haiku o umbral de reportes
    created_at = models.DateTimeField(auto_now_add=True)


class MessageReport(models.Model):
    """4.2 H1: la "puntuacion" comunitaria — reportes de inadecuado. Al superar el
    umbral (SystemSetting message_sensitive_reports, 5) el mensaje se difumina solo."""
    machina_post_id = models.IntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('machina_post_id', 'user')


class HiddenMessage(models.Model):
    """4.2 H2: difuminado PERSONAL — cada usuario esconde para si lo que quiera."""
    machina_post_id = models.IntegerField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('machina_post_id', 'user')


class Vote(models.Model):
    """Voto de post. 5.23-C (ENMIENDA de David al README, 2026-09-08: «los
    votos positivos y negativos se ven en numero»): value = +1 / -1. Los
    listados «mas votados», Trending y el reescaneo de Opus siguen contando
    SOLO los positivos (esa decision no se reabre). Cada voto suma o resta
    karma al autor del post."""
    post = models.ForeignKey('analysis.Post', on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    value = models.SmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')


class MessageVote(models.Model):
    """5.23-C (orden de David): ▲/▼ en cada comentario del hilo. +1/-1 al karma
    del autor. El comentario se DIFUMINA a partir de -karma_fade_threshold y se
    PLIEGA a partir de -karma_fold_threshold (ambos en el panel)."""
    machina_post_id = models.IntegerField(db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    value = models.SmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('machina_post_id', 'user')
