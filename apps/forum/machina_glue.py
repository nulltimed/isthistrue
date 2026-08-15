"""
Pegamento con django-machina (decision congelada: opcion B del quiz de arquitectura).
- Dos foros reales: Principal y Off-Topic (quiz 1A); los 12 temas seran etiquetas.
- Ningun hilo nace sin post analizado (quiz 3A): los topics los crea el sistema.
- Sin mensajes privados (quiz 4A): machina no los trae; no se añaden.
"""
from django.utils.text import slugify


def get_or_create_forums():
    from machina.core.db.models import get_model
    Forum = get_model('forum', 'Forum')
    main, _ = Forum.objects.get_or_create(slug='principal',
        defaults={'name': 'Principal', 'type': Forum.FORUM_POST})
    off, _ = Forum.objects.get_or_create(slug='off-topic',
        defaults={'name': 'Off-Topic', 'type': Forum.FORUM_POST})
    return main, off


def create_topic_for_post(analysis_post):
    """Cada post analizado abre su hilo de discusion en el foro que le toca."""
    from machina.core.db.models import get_model
    Topic = get_model('forum_conversation', 'Topic')
    MPost = get_model('forum_conversation', 'Post')
    main, off = get_or_create_forums()
    forum = off if analysis_post.category == 'OFFTOPIC' else main
    if Topic.objects.filter(slug=f'post-{analysis_post.pk}').exists():
        return
    topic = Topic.objects.create(
        forum=forum, subject=(analysis_post.title or analysis_post.url)[:100],
        slug=f'post-{analysis_post.pk}', poster=analysis_post.author,
        type=Topic.TOPIC_POST, status=Topic.TOPIC_UNLOCKED)
    # 4.2 A5: la caja "Opina" del autor es el PRIMER mensaje del hilo.
    content = (analysis_post.author_opinion.strip()
               or f'Discusión del análisis: /post/{analysis_post.pk}/')
    MPost.objects.create(topic=topic, poster=analysis_post.author,
                         subject=topic.subject, content=content, approved=True)


def get_topic_for_post(analysis_post):
    """El hilo machina de un post analizado (o None si aun no existe). 4.2 C4."""
    from machina.core.db.models import get_model
    Topic = get_model('forum_conversation', 'Topic')
    return Topic.objects.filter(slug=f'post-{analysis_post.pk}').first()


def add_reply(analysis_post, user, content):
    """Respuesta en el hilo desde la pagina del analisis (4.2 C4). Pasa por la
    moderacion Haiku como cualquier mensaje del foro."""
    from machina.core.db.models import get_model
    MPost = get_model('forum_conversation', 'Post')
    topic = get_topic_for_post(analysis_post)
    if topic is None:
        create_topic_for_post(analysis_post)
        topic = get_topic_for_post(analysis_post)
    mpost = MPost.objects.create(topic=topic, poster=user,
                                 subject=f'Re: {topic.subject}'[:100],
                                 content=content, approved=True)
    from apps.forum.moderation import moderate_machina_post
    moderate_machina_post.delay(mpost.pk)
    from apps.analysis.models import PostSubscription
    from apps.accounts.services import notify
    for sub in (PostSubscription.objects.filter(post=analysis_post, on_messages=True)
                .exclude(user=user).select_related('user')):
        notify(sub.user, f'Nuevo mensaje de {user.username} en: '
                         f'{(analysis_post.title or analysis_post.url)[:80]}',
               f'/post/{analysis_post.pk}/#hilo')
    return mpost


def move_topic(analysis_post):
    """Al relegar/rescatar un post, su hilo se muda de subforo (moderacion coherente)."""
    from machina.core.db.models import get_model
    Topic = get_model('forum_conversation', 'Topic')
    main, off = get_or_create_forums()
    topic = Topic.objects.filter(slug=f'post-{analysis_post.pk}').first()
    if topic:
        topic.forum = off if analysis_post.category == 'OFFTOPIC' else main
        topic.save()
