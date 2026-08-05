from django.urls import path
from . import views
from .cards import claim_card

from django.views.generic import RedirectView
urlpatterns = [
    path('', RedirectView.as_view(url='/wiki/cambios/', permanent=False)),
    path('cambios/', views.recent_changes, name='recent_changes'),
    path('persona/<slug:slug>/', views.person_page, name='person_page'),
    path('claim/<slug:slug>/tarjeta.png', claim_card, name='claim_card'),
    path('claim/<slug:slug>/seguir/', views.follow_claim, name='follow_claim'),
    path('claim/<slug:slug>/', views.claim_page, name='claim_page'),
]
