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
    # 5.0-E: la cuenta completa — contraseñas, email, datos, 2FA.
    path('password/olvidada/', views.PasswordResetViewES.as_view(), name='password_reset'),
    path('password/olvidada/enviada/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='accounts/password_reset_done.html'),
         name='password_reset_done'),
    path('password/restablecer/<uidb64>/<token>/',
         views.PasswordResetConfirmViewES.as_view(), name='password_reset_confirm'),
    path('password/restablecida/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='accounts/password_reset_complete.html'),
         name='password_reset_complete'),
    path('password/cambiar/', views.PasswordChangeViewES.as_view(), name='password_change'),
    path('email/cambiar/', views.email_change, name='email_change'),
    path('email/confirmar/<str:token>/', views.email_change_confirm,
         name='email_change_confirm'),
    path('exportar/', views.export_data, name='export_data'),
    path('otp/activar/', views.otp_setup, name='otp_setup'),
    path('otp/desactivar/', views.otp_disable, name='otp_disable'),
    path('otp/', views.otp_verify, name='otp_verify'),
    path('idioma/', views.set_language_pref, name='set_language_pref'),  # 4.4-A
    path('delete/', views.delete_account, name='delete_account'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/poll/', views.notifications_poll, name='notifications_poll'),
    path('mensajes/', views.pm_inbox, name='pm_inbox'),
    path('mensajes/enviar/<int:user_id>/', views.pm_send, name='pm_send'),
    path('mensajes/reportar/<int:pm_id>/', views.pm_report, name='pm_report'),
    path('amigos/', views.friends, name='friends'),
]
