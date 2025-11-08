# ===== apps/analytics/urls.py =====
from django.urls import path
from . import views

urlpatterns = [
    path('pnl', views.get_pnl_data, name='pnl_data'),
    path('statistics', views.get_statistics, name='statistics'),
]
