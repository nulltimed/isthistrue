from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('settings/', views.settings_view, name='account_settings'),
    path('delete/', views.delete_account, name='delete_account'),
    path('notifications/', views.notifications, name='notifications'),
    path('amigos/', views.friends, name='friends'),
]
