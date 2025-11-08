# ===== apps/users/health_urls.py =====
from django.urls import path
from django.http import JsonResponse
from django.db import connection
from datetime import datetime

def health_check(request):
    """Health check endpoint"""
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except:
        db_status = "disconnected"
    
    return JsonResponse({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'database': db_status
    })

urlpatterns = [
    path('', health_check, name='health_check'),
]
