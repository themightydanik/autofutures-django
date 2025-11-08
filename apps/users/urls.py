# ===== apps/users/urls.py =====
from django.urls import path
from . import views

urlpatterns = [
    path('register', views.register, name='register'),
    path('login', views.login, name='login'),
    path('google', views.google_login, name='google_login'),
    path('logout', views.logout, name='logout'),
]
