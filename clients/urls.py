from django.urls import path
from .views import ClientListView, ClientCreateView, ClientDetailView, ClientUpdateView

urlpatterns = [
    path('', ClientListView.as_view(), name='client_list'),
    path('new/', ClientCreateView.as_view(), name='client_create'),
    path('<uuid:pk>/', ClientDetailView.as_view(), name='client_detail'),      # <-- changed
    path('<uuid:pk>/edit/', ClientUpdateView.as_view(), name='client_update'), # <-- changed
]