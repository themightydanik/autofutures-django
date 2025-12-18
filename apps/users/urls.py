from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register', views.register, name='register'),
    path('login', views.login, name='login'),
    path('google', views.google_login, name='google_login'),
    path('logout', views.logout, name='logout'),

    # User data
    path('profile', views.get_profile, name='get_profile'),
    path('settings', views.user_settings, name='user_settings'),
]

