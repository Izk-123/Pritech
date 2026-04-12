from django.urls import path
from .views import HomeView, InquiryCreateView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('inquire/', InquiryCreateView.as_view(), name='inquiry'),
]
