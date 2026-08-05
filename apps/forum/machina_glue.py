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
    MPost.objects.create(topic=topic, poster=analysis_post.author,
                         subject=topic.subject,
                         content=f'Discusión del análisis: /post/{analysis_post.pk}/',
                         approved=True)


def move_topic(analysis_post):
    """Al relegar/rescatar un post, su hilo se muda de subforo (moderacion coherente)."""
    from machina.core.db.models import get_model
    Topic = get_model('forum_conversation', 'Topic')
    main, off = get_or_create_forums()
    topic = Topic.objects.filter(slug=f'post-{analysis_post.pk}').first()
    if topic:
        topic.forum = off if analysis_post.category == 'OFFTOPIC' else main
        topic.save()
