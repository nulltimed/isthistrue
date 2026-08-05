from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from machina.app import board
from apps.wiki.feeds import RecentVerdictsFeed, RecentChangesFeed

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('django_prometheus.urls')),          # /metrics para tu Grafana
    path('accounts/', include('apps.accounts.urls')),
    path('claim/', include('apps.accounts.claim_urls')),  # canje de codigos
    path('panel/', include('apps.panel.urls')),
    path('wiki/', include('apps.wiki.urls')),
    path('foro/', include(board.urls)),                   # django-machina
    path('rss/veredictos/', RecentVerdictsFeed(), name='rss_verdicts'),
    path('rss/cambios/', RecentChangesFeed(), name='rss_changes'),
    path('', include('apps.analysis.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
