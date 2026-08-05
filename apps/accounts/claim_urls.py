from django.urls import path
from . import views
urlpatterns = [path('', views.claim_code, name='claim_code')]
