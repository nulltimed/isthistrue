from django.apps import AppConfig


class ForumConfig(AppConfig):
    name = 'apps.forum'

    def ready(self):
        from django.db.models.signals import post_save
        from django.apps import apps as dj_apps

        def _on_machina_post(sender, instance, created, **kwargs):
            if created:
                from .moderation import moderate_machina_post
                moderate_machina_post.delay(instance.pk)

        try:
            MPost = dj_apps.get_model('forum_conversation', 'Post')
            post_save.connect(_on_machina_post, sender=MPost,
                              dispatch_uid='moderation_cascade')
        except LookupError:
            pass
