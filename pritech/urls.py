from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('portfolio.urls')),
    path('dashboard/', include('core.urls')),
    path('clients/', include('clients.urls')),
    path('services/', include('services.urls')),
    path('tickets/', include('tickets.urls')),
    path('finance/', include('finance.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
