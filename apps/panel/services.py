"""Presupuesto VIVO (Fase 3): techo mensual = base + donaciones del mes, con techo
duro absoluto (la consola de Anthropic es el 2o airbag y solo David la sube a mano)."""
import calendar
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
from .models import Donation, SystemSetting


def live_monthly_cap():
    base = SystemSetting.get_int('budget_base_eur', int(settings.MONTHLY_CAP_EUR))
    hard = SystemSetting.get_int('budget_hard_ceiling_eur', 200)
    today = timezone.localdate()
    donated = sum(float(d.amount_eur) for d in Donation.objects.filter(
        created_at__year=today.year, created_at__month=today.month))
    return min(base + donated, hard), donated, base


def live_daily_budget():
    cap, _, _ = live_monthly_cap()
    days = calendar.monthrange(timezone.localdate().year, timezone.localdate().month)[1]
    return round(cap / days, 2)


def alert_admin(subject, body):
    """Alertas criticas por email (Telegram descartado para siempre). Anti-spam: 1 cada 6 h por asunto."""
    from django.utils.text import slugify
    key = 'alert-' + slugify(subject)[:40]
    if cache.get(key):
        return
    cache.set(key, 1, 6 * 3600)
    send_mail(f'[isthistrue ALERTA] {subject}', body,
              settings.DEFAULT_FROM_EMAIL, [settings.ADMIN_ALERT_EMAIL], fail_silently=True)
