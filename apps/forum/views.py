"""5.1-B.1 (orden de David): la pagina del Foro, rehecha.

La portada de machina era su indice generico y «no tenia sentido» (David).
5.9: categorias de SOLO ENLACES. 5.23-E (ENMIENDA de David al README): los 12
temas son SUBFOROS de Principal (arbol ampliable), y cada post se agrupa por
su categoria. Las paginas profundas de machina (hilos, paginacion) siguen
siendo suyas.
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


def _es_mod(request):
    u = request.user
    return bool(u.is_authenticated and (u.is_staff or u.level == 'MOD'))


def _descendientes(cat, arbol):
    """Slugs de la categoria y de todo lo que cuelga de ella."""
    hijos = {}
    for c, _p in arbol:
        hijos.setdefault(c.parent_id, []).append(c)
    out, pila = [], [cat]
    while pila:
        c = pila.pop()
        out.append(c.slug)
        pila.extend(hijos.get(c.pk, []))
    return out


def foro_home(request):
    """5.9 + 5.23-E: arriba las tres cintas (mas nuevos, mas comentados,
    profundos por votos); despues Principal AGRUPADO por categoria (arbol);
    al final Off-Topic. Cada entrada lleva su menu ⋮ (compacto)."""
    from django.db.models import Count, Q
    from apps.analysis.models import Category, Post
    from apps.analysis.views import _mas_comentados
    from apps.wiki.models import COLORS
    main = Post.objects.publicos().filter(category='MAIN').exclude(is_adult=True)
    off = Post.objects.publicos().filter(category='OFFTOPIC').exclude(is_adult=True)
    # 5.30-A (orden de David): ▲ menos ▼ (antes solo positivos).
    from django.db.models import F
    profundos = (main.filter(status='DONE')
                 .annotate(ups=Count('votes', filter=Q(votes__value=1)),
                           downs=Count('votes', filter=Q(votes__value=-1)))
                 .annotate(nv=F('ups') - F('downs'))
                 .order_by('-nv', '-created_at')[:10])
    arbol = Category.tree()
    conteo = dict(main.values_list('topic').annotate(n=Count('pk')).values_list('topic', 'n'))
    secciones, chips = [], []
    for cat, prof in arbol:
        slugs = _descendientes(cat, arbol)
        n = sum(conteo.get(s, 0) for s in slugs)
        chips.append({'cat': cat, 'prof': prof, 'n': n})
        directos = conteo.get(cat.slug, 0)
        if directos:
            secciones.append({'cat': cat, 'prof': prof, 'n': directos,
                              'posts': main.filter(topic=cat.slug).fijados_primero()[:8]})
    return render(request, 'forum/foro_home.html', {
        'nuevos': main.fijados_primero()[:10],
        'comentados': _mas_comentados(main),
        'profundos': profundos,
        'secciones': secciones, 'chips': chips,
        'off_nuevos': off.fijados_primero()[:10],
        'off_comentados': _mas_comentados(off),
        # 5.1-D: taxonomia viva — el buscador se puebla solo
        'temas': [(c.slug, c.name) for c, _p in arbol],
        'colores': COLORS,
        'is_mod': _es_mod(request),
        'pendientes': (Post.objects.filter(status='PENDING_APPROVAL').count()
                       if _es_mod(request) else 0),
    })


def foro_categoria(request, slug):
    """5.23-E: la pagina de un subforo — sus posts y los de sus subcategorias,
    fijados primero, paginados. Migas hasta la raiz."""
    from django.core.paginator import Paginator
    from django.http import Http404
    from apps.analysis.models import Category, Post
    cat = Category.objects.filter(slug=slug).exclude(slug=Category.ROOT_SLUG).first()
    if not cat:
        raise Http404
    arbol = Category.tree()
    slugs = _descendientes(cat, arbol)
    posts = (Post.objects.publicos().filter(category='MAIN', topic__in=slugs)
             .exclude(is_adult=True).fijados_primero())
    page = Paginator(posts, 30).get_page(request.GET.get('pagina', 1))
    hijas = [c for c, _p in arbol if c.parent_id == cat.pk]
    return render(request, 'forum/categoria.html', {
        'cat': cat, 'migas': cat.ancestors(), 'hijas': hijas,
        'page_obj': page, 'is_mod': _es_mod(request)})
