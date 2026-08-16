from django.conf import settings
from django.conf.urls.static import static
from django.urls import re_path
from apps.panel.media_serve import media_serve
from django.contrib import admin
from django.urls import path, include
from machina import urls as machina_urls
from apps.wiki.feeds import RecentVerdictsFeed, RecentChangesFeed
from apps.wiki.api import claims_list, claim_detail
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),      # selector de idioma (set_language)
    path('', include('django_prometheus.urls')),          # /metrics para tu Grafana
    path('accounts/', include('apps.accounts.urls')),
    path('claim/', include('apps.accounts.claim_urls')),  # canje de codigos
    # 4.3-A.6 P1: /panel/ aterriza en Ajustes — ahi vive la puerta del registro.
    path('panel/', RedirectView.as_view(url='/panel/settings/', permanent=False)),
    path('panel/', include('apps.panel.urls')),
    path('wiki/', include('apps.wiki.urls')),
    path('api/v1/claims/', claims_list, name='api_claims'),
    path('api/v1/claims/<slug:slug>/', claim_detail, name='api_claim'),
    # 4.2 C4: la pagina canonica de un analisis es /post/<pk>/ — el hilo machina
    # 'post-<pk>' redirige alli (analisis y conversacion son UNA pagina).
    re_path(r'^foro/forum/[^/]+/topic/post-(?P<pk>\d+)-\d+/',
            RedirectView.as_view(url='/post/%(pk)s/', permanent=True)),
    path('foro/', include(machina_urls)),                   # django-machina
    path('rss/veredictos/', RecentVerdictsFeed(), name='rss_verdicts'),
    path('rss/cambios/', RecentChangesFeed(), name='rss_changes'),
    path('', include('apps.analysis.urls')),
    re_path(r'^media/(?P<path>.*)$', media_serve, name='media'),
]
