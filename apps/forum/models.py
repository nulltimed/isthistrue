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


class Vote(models.Model):
    """Voto positivo de post (contador SOLO positivo, decision congelada)."""
    post = models.ForeignKey('analysis.Post', on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')
