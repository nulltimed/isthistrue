from django.urls import path
from . import views
from apps.panel.dsa import complaint_form
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.index, name='index'),
    path('submit/', views.submit, name='submit'),
    path('analizar/', views.submit),  # alias en español (guia 3.9 lo nombra asi)
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/<int:pk>/status/', views.post_status, name='post_status'),
    path('post/<int:pk>/fragmento/hilo/', views.post_thread_fragment, name='post_thread_fragment'),
    path('post/<int:pk>/fragmento/cuerpo/', views.post_body_fragment, name='post_body_fragment'),
    path('post/<int:pk>/vote/<str:kind>/', views.vote, name='post_vote'),
    path('post/<int:pk>/relegate/', views.relegate, name='post_relegate'),
    path('post/<int:pk>/unrelegate/', views.unrelegate, name='post_unrelegate'),
    path('post/<int:pk>/reply/', views.reply, name='post_reply'),
    path('post/<int:pk>/subscribe/', views.subscribe, name='post_subscribe'),
    path('oracion/<int:pk>/votar/<str:direction>/', views.segment_vote, name='segment_vote'),
    path('post/<int:pk>/hablante/proponer/', views.propose_speaker_name, name='propose_speaker_name'),
    path('mensaje/<int:mpost_id>/reportar/', views.message_report, name='message_report'),
    path('mensaje/<int:mpost_id>/editar/', views.message_edit, name='message_edit'),
    path('mensaje/<int:mpost_id>/ocultar/', views.message_hide_toggle, name='message_hide'),
    path('mensaje/<int:mpost_id>/sensible/', views.message_sensitive_toggle, name='message_sensitive'),
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
