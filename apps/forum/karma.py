"""5.23-C (orden de David, 2026-09-08): el KARMA se estrena.

Hasta hoy `User.karma` decidia los niveles pero NINGUNA linea del codigo lo
movia: solo ascendia quien canjeaba un codigo. Ahora cada ▲ suma 1 y cada ▼
resta 1 al autor del post o del comentario votado. Reglas:
- un voto por persona y objeto; repetir el mismo voto lo retira; el contrario
  lo cambia (misma semantica que los votos por frase del 4.2 H5);
- nadie vota lo suyo (ni se le pintan las flechas);
- la flecha abajo la tiene CUALQUIER usuario (decision de David);
- el comentario se difumina desde -karma_fade_threshold (5) y se pliega desde
  -karma_fold_threshold (10), ambos en el panel del superusuario.
"""
from django.db.models import Count, F, Q


def aplicar_voto(modelo, clave, user, value, autor):
    """Registra/alterna el voto y mueve el karma del autor. Devuelve el delta
    aplicado al karma (0 si no cambio nada)."""
    from apps.accounts.models import User
    value = 1 if value >= 0 else -1
    obj = modelo.objects.filter(user=user, **clave).first()
    if obj is None:
        modelo.objects.create(user=user, value=value, **clave)
        delta = value
    elif obj.value == value:
        obj.delete()
        delta = -value
    else:
        delta = value - obj.value
        obj.value = value
        obj.save(update_fields=['value'])
    if delta and autor is not None and autor.pk != user.pk:
        User.objects.filter(pk=autor.pk).update(karma=F('karma') + delta)
    return delta


def recuento(modelo, clave, user=None):
    """(ups, downs, mi_voto) de un objeto."""
    qs = modelo.objects.filter(**clave)
    agg = qs.aggregate(ups=Count('pk', filter=Q(value=1)),
                       downs=Count('pk', filter=Q(value=-1)))
    mio = 0
    if user is not None and getattr(user, 'is_authenticated', False):
        mio = qs.filter(user=user).values_list('value', flat=True).first() or 0
    return agg['ups'] or 0, agg['downs'] or 0, mio


def umbrales():
    """(difuminar, plegar) — puntuacion NEGATIVA a partir de la cual pasa."""
    from apps.panel.models import SystemSetting
    fade = max(1, SystemSetting.get_int('karma_fade_threshold', 5))
    fold = max(fade, SystemSetting.get_int('karma_fold_threshold', 10))
    return fade, fold


def decorar_mensajes(mensajes, user=None):
    """Cuelga ups/downs/score/my_vote/faded/folded de cada mensaje machina de
    la pagina, en DOS consultas para toda la pagina."""
    from .models import MessageVote
    ids = [m.pk for m in mensajes]
    if not ids:
        return mensajes
    filas = (MessageVote.objects.filter(machina_post_id__in=ids)
             .values('machina_post_id')
             .annotate(ups=Count('pk', filter=Q(value=1)),
                       downs=Count('pk', filter=Q(value=-1))))
    conteo = {f['machina_post_id']: (f['ups'], f['downs']) for f in filas}
    mios = {}
    if user is not None and getattr(user, 'is_authenticated', False):
        mios = dict(MessageVote.objects.filter(machina_post_id__in=ids, user=user)
                    .values_list('machina_post_id', 'value'))
    fade, fold = umbrales()
    for m in mensajes:
        m.ups, m.downs = conteo.get(m.pk, (0, 0))
        m.score = m.ups - m.downs
        m.my_vote = mios.get(m.pk, 0)
        m.faded = m.score <= -fade
        m.folded = m.score <= -fold
        m.is_own = bool(user is not None and getattr(user, 'pk', None) == m.poster_id)
    return mensajes
