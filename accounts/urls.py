from django.urls import path
from .views import ClientRegisterView, CustomLoginView, CustomLogoutView, StaffListView, ProfileView

urlpatterns = [
    path('register/', ClientRegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('staff/', StaffListView.as_view(), name='staff_list'),
    path('profile/', ProfileView.as_view(), name='profile'),
]
