from django.urls import path
from . import views
urlpatterns = [
    path('codes/', views.codes, name='panel_codes'),
    path('settings/', views.settings_panel, name='panel_settings'),
    path('staging/', views.staging_invites, name='panel_staging'),
    path('reclamaciones/', views.complaints, name='panel_complaints'),
    path('donaciones/', views.donations_panel, name='panel_donations'),
    path('moderadores/', views.moderators_panel, name='panel_moderators'),
    path('moderador/', views.moderator_settings_panel, name='panel_moderator_settings'),
]
