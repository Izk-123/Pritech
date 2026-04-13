from django.urls import path
from .views import (
    ServiceListView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView,
    ServiceCategoryListView, ServiceCategoryCreateView, ServiceCategoryUpdateView,
    ServicePackageListView, ServicePackageCreateView, ServicePackageUpdateView, ServicePackageDeleteView,
)

urlpatterns = [
    # Services
    path('', ServiceListView.as_view(), name='service_list'),
    path('new/', ServiceCreateView.as_view(), name='service_create'),
    path('<int:pk>/edit/', ServiceUpdateView.as_view(), name='service_update'),
    path('<int:pk>/delete/', ServiceDeleteView.as_view(), name='service_delete'),

    # Categories
    path('categories/', ServiceCategoryListView.as_view(), name='service_category_list'),
    path('categories/new/', ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('categories/<int:pk>/edit/', ServiceCategoryUpdateView.as_view(), name='service_category_update'),

    # Packages
    path('packages/', ServicePackageListView.as_view(), name='service_package_list'),
    path('packages/new/', ServicePackageCreateView.as_view(), name='service_package_create'),
    path('packages/<int:pk>/edit/', ServicePackageUpdateView.as_view(), name='service_package_update'),
    path('packages/<int:pk>/delete/', ServicePackageDeleteView.as_view(), name='service_package_delete'),
]