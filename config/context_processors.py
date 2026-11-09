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
        cap, donated, base = live_monthly_cap()
        # (5.5-B historico: el «Faltan X €» seguia al presupuesto base.
        #  6.1: ese mensaje desaparece con las donaciones — Lectura A.)
        # 5.10-D (orden de David): lo que se ENSEÑA es el gasto REAL del libro
        # (CostEntry, actualizado con cada apunte de cada análisis). DailyBudget
        # y MonthlyCap siguen siendo los fusibles que cortan — pero sus reservas
        # estimadas ya no se muestran como si fueran gasto.
        from apps.analysis.costs import day_total, month_total_all
        # 6.20-b (David: «sigue apareciendo el techo de gasto»): con los
        # limites apagados, los techos no existen — el banner enseña solo el
        # gasto real, sin el «/X €» que ya no corta nada.
        from apps.panel.services import budget_limits_enabled
        return {'quota_banner': {
            'limites': budget_limits_enabled(),
            'daily_spent': day_total(),
            'daily_budget': live_daily_budget(),
            'monthly_spent': month_total_all(),
            'monthly_cap': cap,
            # 6.1 (orden de David, 2026-11-06, Lectura A): donaciones RETIRADAS.
            # El banner queda como transparencia pura: fuera goal_missing y
            # los datos de PayPal (el IPN legado no los necesita aqui).
            'donated': donated,
        }}
    except Exception:
        return {'quota_banner': None}


def web_privada(request):
    """5.31: la pagina de entrada avisa de que la web esta privada."""
    try:
        from config.middleware import PrivateSiteMiddleware
        return {'web_privada': PrivateSiteMiddleware.activa()}
    except Exception:
        return {'web_privada': False}



def tour_guiado(request):
    """6.7 (orden de David, 2026-11-09): recorrido guiado por la web para el
    usuario invitado (su socio) — se activa en su siguiente login y se apaga
    solo al terminarlo o saltarlo. El email vive en Panel → `tour_email`."""
    try:
        u = getattr(request, 'user', None)
        if not (u and u.is_authenticated):
            return {}
        from apps.panel.models import SystemSetting
        email = (SystemSetting.get_str('tour_email', '') or '').strip().lower()
        if not email or (u.email or '').lower() != email:
            return {}
        if (getattr(u, 'notify_prefs', None) or {}).get('tour_done'):
            return {}
        from apps.analysis.views import _bulo_destacado
        bulo = _bulo_destacado()
        return {'tour_activo': True,
                'tour_ficha_url': f'/wiki/claim/{bulo.slug}/' if bulo else '/wiki/'}
    except Exception:
        return {}
