from django.urls import path
from . import views

urlpatterns = [
    path('profile', views.get_profile, name='get_profile'),
    path('settings', views.user_settings, name='user_settings'),
]
