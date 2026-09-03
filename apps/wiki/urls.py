from django.urls import path
from . import views
from .cards import claim_card

from django.views.generic import RedirectView
urlpatterns = [
    # 5.1-A: la wiki tiene PORTADA propia (antes redirigia a cambios).
    path('', views.wiki_home, name='wiki_home'),
    path('cambios/', views.recent_changes, name='recent_changes'),
    # 4.3-C: la ficha vive en la RAIZ (/persona/...), igual en escierto, isthistrue
    # y wikitrue. Esta ruta antigua bajo /wiki/ se conserva y redirige, para no
    # romper enlaces ya publicados.
    path('persona/<slug:slug>/', views.person_page_legacy, name='person_page_legacy'),
    path('claim/<slug:slug>/tarjeta.png', claim_card, name='claim_card'),
    path('claim/<slug:slug>/seguir/', views.follow_claim, name='follow_claim'),
    path('claim/<slug:slug>/', views.claim_page, name='claim_page'),
]
