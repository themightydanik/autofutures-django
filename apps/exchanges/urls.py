# ===== apps/exchanges/urls.py =====
from django.urls import path
from . import views

urlpatterns = [

    # =====================================================
    # EXCHANGES INFO
    # =====================================================
    path('supported', views.get_supported_exchanges, name='supported_exchanges'),
    path('balances', views.get_all_balances, name='all_balances'),

    # =====================================================
    # USER EXCHANGE MANAGEMENT (used by frontend)
    # =====================================================
    path('user/manage', views.manage_exchanges, name='manage_exchanges'),
    path('user/connect', views.connect_exchange, name='connect_exchange'),
    path('user/disconnect', views.disconnect_exchange, name='disconnect_exchange'),
]
