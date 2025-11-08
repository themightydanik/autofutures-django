from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/user/', include('apps.users.user_urls')),
    path('api/trading/', include('apps.trading.urls')),
    path('api/exchanges/', include('apps.exchanges.urls')),
    path('api/analytics/', include('apps.analytics.urls')),
    path('api/arbitrage/', include('apps.arbitrage.urls')),
    path('api/market/', include('apps.exchanges.market_urls')),
    path('health/', include('apps.users.health_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "AutoFutures Administration"
admin.site.site_title = "AutoFutures Admin"
admin.site.index_title = "Welcome to AutoFutures"
