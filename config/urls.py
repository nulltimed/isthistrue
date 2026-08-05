from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from machina import urls as machina_urls
from apps.wiki.feeds import RecentVerdictsFeed, RecentChangesFeed
from apps.wiki.api import claims_list, claim_detail
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('django_prometheus.urls')),          # /metrics para tu Grafana
    path('accounts/', include('apps.accounts.urls')),
    path('claim/', include('apps.accounts.claim_urls')),  # canje de codigos
    path('panel/', RedirectView.as_view(url='/panel/codes/', permanent=False)),
    path('panel/', include('apps.panel.urls')),
    path('wiki/', include('apps.wiki.urls')),
    path('api/v1/claims/', claims_list, name='api_claims'),
    path('api/v1/claims/<slug:slug>/', claim_detail, name='api_claim'),
    path('foro/', include(machina_urls)),                   # django-machina
    path('rss/veredictos/', RecentVerdictsFeed(), name='rss_verdicts'),
    path('rss/cambios/', RecentChangesFeed(), name='rss_changes'),
    path('', include('apps.analysis.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
