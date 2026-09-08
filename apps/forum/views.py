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
    """5.9 (orden de David, supersede los bloques-con-mensajes del 5.1-B):
    el Foro en CATEGORIAS de SOLO ENLACES — «Sin mostrar comentarios, sólo el
    enlace al post». Principal: mas nuevos, mas comentados, y analizados en
    profundidad por votos (= analisis COMPLETO con veredictos, DONE; si David
    quiso otra cosa por «en profundidad», se ajusta aqui). Off-Topic: mas
    nuevos y mas comentados."""
    from django.db.models import Count, Q
    from apps.analysis.models import Category, Post
    from apps.analysis.views import _mas_comentados
    from apps.wiki.models import COLORS
    main = Post.objects.filter(category='MAIN').exclude(is_adult=True)
    off = Post.objects.filter(category='OFFTOPIC').exclude(is_adult=True)
    profundos = (main.filter(status='DONE')
                 .annotate(nv=Count('votes', filter=Q(votes__value=1)))
                 .order_by('-nv', '-created_at')[:10])
    return render(request, 'forum/foro_home.html', {
        'nuevos': main.order_by('-created_at')[:10],
        'comentados': _mas_comentados(main),
        'profundos': profundos,
        'off_nuevos': off.order_by('-created_at')[:10],
        'off_comentados': _mas_comentados(off),
        # 5.1-D: taxonomia viva — el buscador se puebla solo
        'temas': list(Category.objects.values_list('slug', 'name')),
        'colores': COLORS,
    })
