from django.urls import path
from .views import ServiceListView, ServiceCreateView, ServiceUpdateView

urlpatterns = [
    path('', ServiceListView.as_view(), name='service_list'),
    path('new/', ServiceCreateView.as_view(), name='service_create'),
    path('<int:pk>/edit/', ServiceUpdateView.as_view(), name='service_update'),
]
