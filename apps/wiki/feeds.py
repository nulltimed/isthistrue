"""RSS (quiz 14A): a los medios les encanta."""
from django.contrib.syndication.views import Feed
from .models import Claim, ClaimVersion


class RecentVerdictsFeed(Feed):
    title = 'isthistrue. — nuevos veredictos'
    link = '/'
    description = 'Afirmaciones verificadas recientemente'

    def items(self):
        return Claim.objects.filter(consolidated=True).order_by('-created_at')[:30]

    def item_title(self, item):
        return f'{item.get_color_display()} — {item.text_original[:120]}'

    def item_description(self, item):
        return item.what_evidence_says

    def item_link(self, item):
        return f'/wiki/claim/{item.slug or item.pk}/'


class RecentChangesFeed(Feed):
    title = 'isthistrue. — cambios recientes'
    link = '/wiki/cambios/'
    description = 'Re-verificaciones y cambios de color (transparencia total)'

    def items(self):
        return ClaimVersion.objects.select_related('claim').order_by('-created_at')[:50]

    def item_title(self, item):
        return f'{item.get_color_display()} — {item.claim.text_original[:120]}'

    def item_description(self, item):
        return f'Nueva versión del {item.created_at:%d/%m/%Y}'

    def item_link(self, item):
        return f'/wiki/claim/{item.claim.slug or item.claim.pk}/'
