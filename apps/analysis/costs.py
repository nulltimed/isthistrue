"""4.9-A · EL LIBRO DE CUENTAS (orden de David, 2026-08-30).

«La funcionalidad de la web depende de que cada centimo vaya a donde se
necesita» + «quiero saber cuanto cuesta cada analisis con todas sus partes,
para ser transparente con las donaciones».

Cada gasto real (Anthropic, AssemblyAI, Runpod, Brevo) deja un apunte aqui,
ligado al post cuando lo hay. De este libro salen: el desglose por analisis,
los totales mensuales por proveedor del panel, y los TOPES que cortan el
grifo de cada servicio por separado.
"""
import threading
from decimal import Decimal

from django.utils import timezone

_local = threading.local()


def set_post(post):
    """El post en curso del worker: los apuntes de Anthropic se cuelgan de el."""
    _local.post = post


def current_post():
    return getattr(_local, 'post', None)


def record(provider, concept, eur, post=None):
    """Un apunte. Jamas rompe el analisis por un fallo contable (regla 5.7)."""
    from .models import CostEntry, Post
    try:
        if eur is None or float(eur) <= 0:
            return
        candidato = post or current_post()
        # el post del hilo puede ser un fantasma (test/rollback/borrado): si ya
        # no existe, el apunte va sin post — jamas una violacion de FK dentro
        # de la transaccion del peaje.
        if candidato is not None and not Post.objects.filter(
                pk=candidato.pk).exists():
            candidato = None
        CostEntry.objects.create(post=candidato,
                                 provider=provider, concept=concept,
                                 eur=Decimal(str(round(float(eur), 4))))
    except Exception:
        import logging
        logging.getLogger('analysis.costs').warning(
            'apunte contable perdido: %s/%s %s', provider, concept, eur)


def month_total(provider):
    from django.db.models import Sum
    from .models import CostEntry
    hoy = timezone.localdate()
    total = CostEntry.objects.filter(
        provider=provider, created_at__year=hoy.year,
        created_at__month=hoy.month).aggregate(s=Sum('eur'))['s']
    return float(total or 0)


def month_count(provider):
    from .models import CostEntry
    hoy = timezone.localdate()
    return CostEntry.objects.filter(
        provider=provider, created_at__year=hoy.year,
        created_at__month=hoy.month).count()


def post_breakdown(post):
    """[(proveedor, concepto, eur)] + total — el desglose del analisis."""
    from django.db.models import Sum
    from .models import CostEntry
    filas = list(CostEntry.objects.filter(post=post).values(
        'provider', 'concept').annotate(eur=Sum('eur')).order_by('provider'))
    total = float(sum(f['eur'] for f in filas))
    return filas, round(total, 4)
