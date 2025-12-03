# apps/exchanges/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("supported/", views.get_supported_exchanges),
    path("connect/", views.connect_exchange),
    path("disconnect/<str:exchange_id>/", views.disconnect_exchange),
    path("manage/", views.manage_exchanges),
    path("balance/<str:exchange_id>/", views.get_balance),
]
