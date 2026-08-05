"""Cupos publicos ligados a donaciones (decision congelada): visibles en foro Y wiki."""
from django.conf import settings
from django.utils import timezone


def quota_banner(request):
    try:
        from apps.analysis.models import DailyBudget, MonthlyCap
        today = DailyBudget.objects.filter(date=timezone.localdate()).first()
        ym = timezone.localdate().strftime('%Y-%m')
        month = MonthlyCap.objects.filter(year_month=ym).first()
        from apps.panel.services import live_monthly_cap, live_daily_budget
        from apps.panel.models import SystemSetting
        cap, donated, base = live_monthly_cap()
        goal = SystemSetting.get_int('donation_goal_eur', 60)
        return {'quota_banner': {
            'daily_spent': float(today.spent_eur) if today else 0.0,
            'daily_budget': live_daily_budget(),
            'monthly_spent': float(month.spent_eur) if month else 0.0,
            'monthly_cap': cap,
            'donated': donated,
            'goal_missing': max(0, goal - donated),
        }}
    except Exception:
        return {'quota_banner': None}
