"""5.1-B.1 (orden de David): la pagina del Foro, rehecha.

La portada de machina era su indice generico y «no tenia sentido» (David).
Ahora: cada foro (Principal y Off-Topic) con sus ultimos 10 mensajes, y arriba
un buscador por afirmacion, tipo de claim y categoria del post. Las paginas
profundas de machina (hilos, paginacion) siguen siendo suyas.
"""
from django.shortcuts import render


def _mensajes_de(forum, n=10):
    from machina.core.db.models import get_model
    MPost = get_model('forum_conversation', 'Post')
    filas = []
    for m in (MPost.objects.filter(approved=True, topic__forum=forum)
              .select_related('topic', 'poster').order_by('-created')[:n]):
        slug = m.topic.slug or ''
        if slug.startswith('post-'):
            enlace = f'/post/{slug.split("-", 1)[1]}/#hilo'
        else:
            enlace = f'/foro/forum/{forum.slug}-{forum.pk}/topic/{slug}-{m.topic.pk}/'
        filas.append({'m': m, 'enlace': enlace})
    return filas


def foro_home(request):
    from machina.core.db.models import get_model
    from apps.analysis.models import TOPICS
    from apps.wiki.models import COLORS
    Forum = get_model('forum', 'Forum')
    principal = Forum.objects.filter(slug='principal').first()
    offtopic = Forum.objects.filter(slug='off-topic').first()
    return render(request, 'forum/foro_home.html', {
        'principal': principal,
        'principal_msgs': _mensajes_de(principal) if principal else [],
        'offtopic': offtopic,
        'offtopic_msgs': _mensajes_de(offtopic) if offtopic else [],
        'temas': TOPICS, 'colores': COLORS,
    })
