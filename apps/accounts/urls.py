from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .login_view import VerifiedLoginView

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', VerifiedLoginView.as_view(), name='login'),
    path('verify/<str:token>/', views.verify_email, name='verify_email'),
    path('verify/resend/', views.resend_verification, name='resend_verification'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('settings/', views.settings_view, name='account_settings'),
    path('idioma/', views.set_language_pref, name='set_language_pref'),  # 4.4-A
    path('delete/', views.delete_account, name='delete_account'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/poll/', views.notifications_poll, name='notifications_poll'),
    path('mensajes/', views.pm_inbox, name='pm_inbox'),
    path('mensajes/enviar/<int:user_id>/', views.pm_send, name='pm_send'),
    path('mensajes/reportar/<int:pm_id>/', views.pm_report, name='pm_report'),
    path('amigos/', views.friends, name='friends'),
]
