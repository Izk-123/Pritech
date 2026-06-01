# pritech/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Custom error handlers – uses your templates/403.html, 404.html, 500.html
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

urlpatterns = [
    path('admin/', admin.site.urls),

    # Allauth social login – moved to /social/ to avoid conflict with your custom accounts views
    path('social/', include('allauth.urls')),

    # Your custom authentication views (login, register, 2FA, profile, team, etc.)
    path('accounts/', include('accounts.urls')),

    # Other apps
    path('', include('portfolio.urls')),          # Public portfolio pages
    path('dashboard/', include('core.urls')),     # Dashboard & HTMX partials
    path('clients/', include('clients.urls')),    # Client management
    path('services/', include('services.urls')),  # Service catalogue
    path('tickets/', include('tickets.urls')),    # Support tickets
    path('finance/', include('finance.urls')),    # Quotations, invoices, expenses, reports
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)