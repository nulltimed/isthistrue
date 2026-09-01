"""Cupos publicos ligados a donaciones (decision congelada): visibles en foro Y wiki."""
from django.conf import settings
from django.utils import timezone


def unread_notifications(request):
    """4.2 D2: numerito rojo de la campana de la cabecera."""
    try:
        if request.user.is_authenticated:
            return {'unread_notifications':
                    request.user.notifications.filter(read=False).count()}
    except Exception:
        pass
    return {'unread_notifications': 0}


def logo_variant(request):
    """4.2 C6 (decision de David): el LOGO sigue al DOMINIO; el idioma de la
    interfaz sigue mandandolo el selector ES-EN. wikitrue y cualquier otro host
    -> isthistrue (documentado en README de operador)."""
    host = request.get_host().split(':')[0].lower()
    # 5.0-A (dominio nuevo de David): esestocierto.com es la casa — marca en
    # espanol; los hosts historicos conservan su variante para las redirecciones.
    es = host.startswith('escierto') or 'esestocierto' in host
    return {'logo_variant': 'escierto' if es else 'isthistrue'}


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
            # Enlace de donacion clasico: fallback SIN JavaScript del banner (4.1 B3)
            'paypal_url': (SystemSetting.objects.filter(key='paypal_url')
                           .values_list('value', flat=True).first() or ''),
        }}
    except Exception:
        return {'quota_banner': None}
