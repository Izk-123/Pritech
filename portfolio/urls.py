from django.urls import path
from .views import HomeView, InquiryCreateView, newsletter_subscribe

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('inquire/', InquiryCreateView.as_view(), name='inquiry'),
    path('newsletter/subscribe/', newsletter_subscribe, name='newsletter_subscribe'),
]
