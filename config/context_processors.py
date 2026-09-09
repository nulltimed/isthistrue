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


def pendientes_aprobacion(request):
    """5.23-E: cuantos posts esperan aprobacion — solo para el staff (campana
    de la cabecera y pestaña del panel)."""
    try:
        u = request.user
        if u.is_authenticated and (u.is_staff or u.level == 'MOD'):
            from apps.analysis.models import Post
            return {'pendientes_aprobacion':
                    Post.objects.filter(status='PENDING_APPROVAL').count()}
    except Exception:
        pass
    return {'pendientes_aprobacion': 0}


def logo_variant(request):
    """4.2 C6 decia: el logo sigue al dominio. 5.25-C (orden de David, 2026-09-09):
    el proyecto se llama esestocierto y el logo es UNO en todos los hosts (los
    historicos ya redirigen a esestocierto.com)."""
    return {'logo_variant': 'escierto'}


def quota_banner(request):
    try:
        from apps.analysis.models import DailyBudget, MonthlyCap
        today = DailyBudget.objects.filter(date=timezone.localdate()).first()
        ym = timezone.localdate().strftime('%Y-%m')
        month = MonthlyCap.objects.filter(year_month=ym).first()
        from apps.panel.services import live_monthly_cap, live_daily_budget
        from apps.panel.models import SystemSetting
        cap, donated, base = live_monthly_cap()
        # 5.5-B (reporte de David): «costear el proyecto» ES el presupuesto
        # base de su panel — el «Faltan X €» lo sigue a el, no a una meta
        # aparte que se desincronizaba.
        goal = base
        # 5.10-D (orden de David): lo que se ENSEÑA es el gasto REAL del libro
        # (CostEntry, actualizado con cada apunte de cada análisis). DailyBudget
        # y MonthlyCap siguen siendo los fusibles que cortan — pero sus reservas
        # estimadas ya no se muestran como si fueran gasto.
        from apps.analysis.costs import day_total, month_total_all
        return {'quota_banner': {
            'daily_spent': day_total(),
            'daily_budget': live_daily_budget(),
            'monthly_spent': month_total_all(),
            'monthly_cap': cap,
            'donated': donated,
            'goal_missing': max(0, goal - donated),
            # Enlace de donacion clasico: fallback SIN JavaScript del banner (4.1 B3)
            # 5.15: el SDK usa el client-id REST de David cuando existe —
            # asi la verificacion de pedidos y el boton hablan de la MISMA app.
            'paypal_client_id': (settings.PAYPAL_CLIENT_ID or
                                 'BAADhc-JgAzqfnYzcr9AzUGFz8yS0Of2HIilTwEDeLK_'
                                 'Jeo6KIMBt4RPRHP1S74tonAsGWc60dbRe79t1M'),
            'paypal_url': (SystemSetting.objects.filter(key='paypal_url')
                           .values_list('value', flat=True).first() or ''),
        }}
    except Exception:
        return {'quota_banner': None}
