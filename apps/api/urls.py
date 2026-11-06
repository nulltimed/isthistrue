from django.urls import path

from . import views

urlpatterns = [
    # Publicas (sin clave): documentacion + solicitud + reclamacion.
    path('', views.api_home, name='api_home'),
    path('reclamar/<int:pk>/<slug:token>/', views.api_appeal, name='api_appeal'),
    # v1 (solo lectura, con clave X-API-Key):
    path('v1/claims/', views.claims_list, name='api_claims'),
    path('v1/claims/<slug:slug>/', views.claim_detail, name='api_claim'),
    path('v1/analisis/', views.posts_list, name='api_posts'),
    path('v1/analisis/<int:pk>/', views.post_detail, name='api_post'),
    path('v1/analisis/<int:pk>/transcripcion/', views.post_transcript,
         name='api_transcript'),
    path('v1/canales/', views.channels_list, name='api_channels'),
    path('v1/stats/', views.stats, name='api_stats'),
]
