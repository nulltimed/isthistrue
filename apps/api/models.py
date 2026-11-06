"""SERIE 6.2 (ordenes de David, 2026-11-06): la API publica de lectura.

«una API que organizaciones, periodicos, etc (siempre excluyendo formaciones
politicas y otros organismos que entren en conflicto con la esencia de la web)
puedan usar para extraer todo tipo de informacion de la web» · «el analisis de
quien solicita la clave sera asistido por IA [...] siendo la decision siempre
comprobada por un superusuario si el solicitante no acepta la denegacion».

Flujo de la clave: solicitud publica (datos minimos) -> agente de escrutinio
(busca quien es el solicitante y aplica las exclusiones) -> APROBADA (clave por
email) o DENEGADA con motivos -> el denegado puede RECLAMAR con su enlace y la
solicitud pasa a la bandeja de los superusuarios, que tienen la ultima palabra.
Los datos de la wiki son CC-BY-SA: el nivel gratuito exige atribucion.
"""
import secrets

from django.db import models


class ApiKey(models.Model):
    STATUSES = [('PENDING', 'Pendiente de escrutinio'),
                ('APPROVED', 'Aprobada'),
                ('DENIED', 'Denegada'),
                ('APPEALED', 'Reclamada — en la bandeja'),
                ('REVOKED', 'Revocada')]
    TIERS = [('FREE', 'Gratuita (con atribución)'), ('PRO', 'Profesional')]
    KINDS = [('ORG', 'Persona jurídica'), ('PERSON', 'Persona física')]

    # La solicitud: lo minimo imprescindible para saber quien pide.
    kind = models.CharField(max_length=8, choices=KINDS, default='ORG')
    entity_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    website = models.URLField(blank=True, default='')
    purpose = models.TextField(max_length=1000)
    # El escrutinio del agente: veredicto integro y citable.
    ai_verdict = models.JSONField(default=dict, blank=True)
    # La reclamacion (enlace con secreto propio: el solicitante no tiene cuenta).
    appeal_token = models.CharField(max_length=64, default=secrets.token_urlsafe)
    appeal_text = models.TextField(blank=True, default='')
    resolved_by = models.ForeignKey('accounts.User', null=True, blank=True,
                                    on_delete=models.SET_NULL)
    # La clave en si.
    status = models.CharField(max_length=10, choices=STATUSES, default='PENDING')
    tier = models.CharField(max_length=5, choices=TIERS, default='FREE')
    key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def approve(self):
        from django.utils import timezone
        self.status = 'APPROVED'
        self.key = self.key or f'istt_{secrets.token_hex(20)}'
        self.decided_at = timezone.now()
        self.save()
        return self.key

    def daily_limit(self):
        from apps.panel.models import SystemSetting
        clave = 'api_pro_daily' if self.tier == 'PRO' else 'api_free_daily'
        return SystemSetting.get_int(clave, 10000 if self.tier == 'PRO' else 500)


class ApiUsage(models.Model):
    """Contador diario por clave (en base de datos: sobrevive reinicios)."""
    api_key = models.ForeignKey(ApiKey, on_delete=models.CASCADE, related_name='usage')
    date = models.DateField(db_index=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('api_key', 'date')]
