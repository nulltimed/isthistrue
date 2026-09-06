from django.urls import path
from . import views
from .cards import claim_card

from django.views.generic import RedirectView
urlpatterns = [
    # 5.1-A: la wiki tiene PORTADA propia (antes redirigia a cambios).
    path('', views.wiki_home, name='wiki_home'),
    # 5.5-H: el buscador unico de la landing (sin opciones).
    path('buscar/', views.wiki_search, name='wiki_search'),
    # 5.6-B: autocompletado del buscador (JSON).
    path('sugerencias/', views.wiki_suggest, name='wiki_suggest'),
    path('cambios/', views.recent_changes, name='recent_changes'),
    # 5.1-C: la rejilla completa de personas sale de la portada a su pagina.
    path('personas/', views.people_index, name='people_index'),
    # 5.4-C: la wiki del analisis de cada video
    path('video/<slug:slug>/', views.video_analysis, name='wiki_video'),
    # 4.3-C: la ficha vive en la RAIZ (/persona/...), igual en escierto, isthistrue
    # y wikitrue. Esta ruta antigua bajo /wiki/ se conserva y redirige, para no
    # romper enlaces ya publicados.
    path('persona/<slug:slug>/', views.person_page_legacy, name='person_page_legacy'),
    path('claim/<slug:slug>/tarjeta.png', claim_card, name='claim_card'),
    path('claim/<slug:slug>/seguir/', views.follow_claim, name='follow_claim'),
    # 5.12: el historial del claim (orden de David).
    path('claim/<slug:slug>/historial/', views.claim_history, name='claim_history'),
    path('claim/<slug:slug>/', views.claim_page, name='claim_page'),
]
