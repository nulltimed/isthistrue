"""Cupos publicos ligados a donaciones (decision congelada): visibles en foro Y wiki."""
from django.conf import settings
from django.utils import timezone


def quota_banner(request):
    try:
        from apps.analysis.models import DailyBudget, MonthlyCap
        today = DailyBudget.objects.filter(date=timezone.localdate()).first()
        ym = timezone.localdate().strftime('%Y-%m')
        month = MonthlyCap.objects.filter(year_month=ym).first()
        return {'quota_banner': {
            'daily_spent': float(today.spent_eur) if today else 0.0,
            'daily_budget': settings.DAILY_BUDGET_EUR,
            'monthly_spent': float(month.spent_eur) if month else 0.0,
            'monthly_cap': settings.MONTHLY_CAP_EUR,
        }}
    except Exception:
        return {'quota_banner': None}
