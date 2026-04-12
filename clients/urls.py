from django.urls import path
from .views import ClientListView, ClientCreateView, ClientDetailView, ClientUpdateView

urlpatterns = [
    path('', ClientListView.as_view(), name='client_list'),
    path('new/', ClientCreateView.as_view(), name='client_create'),
    path('<int:pk>/', ClientDetailView.as_view(), name='client_detail'),
    path('<int:pk>/edit/', ClientUpdateView.as_view(), name='client_update'),
]
