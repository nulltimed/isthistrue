from django.urls import path
from . import views
urlpatterns = [
    path('codes/', views.codes, name='panel_codes'),
    path('settings/', views.settings_panel, name='panel_settings'),
    path('staging/', views.staging_invites, name='panel_staging'),
    path('reclamaciones/', views.complaints, name='panel_complaints'),
]
