from django.urls import path
from . import views
from apps.panel.dsa import complaint_form
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.index, name='index'),
    path('submit/', views.submit, name='submit'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/status/', views.post_status, name='post_status'),
    path('post/<int:pk>/vote/<str:kind>/', views.vote, name='post_vote'),
    path('buscar/', views.search, name='search'),
    path('hablante/votar/<int:proposal_id>/', views.vote_speaker_name, name='vote_speaker_name'),
    path('post/<int:pk>/upvote/', views.upvote, name='post_upvote'),
    path('donaciones/', views.donations_page, name='donations'),
    path('reclamaciones/', complaint_form, name='complaint_form'),
    path('metodologia/', TemplateView.as_view(template_name='legal/metodologia.html'), name='methodology'),
    path('legal/aviso/', TemplateView.as_view(template_name='legal/aviso_legal.html'), name='legal_notice'),
    path('legal/privacidad/', TemplateView.as_view(template_name='legal/privacidad.html'), name='privacy'),
    path('legal/cookies/', TemplateView.as_view(template_name='legal/cookies.html'), name='cookies'),
    path('legal/condiciones/', TemplateView.as_view(template_name='legal/condiciones.html'), name='terms'),
]
