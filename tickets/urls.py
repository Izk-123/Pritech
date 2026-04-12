from django.urls import path
from .views import (TicketListView, TicketCreateView, TicketDetailView,
                    TicketTransitionView, AssignTicketView,
                    AddCommentView, AddWorkLogView)

urlpatterns = [
    path('', TicketListView.as_view(), name='ticket_list'),
    path('new/', TicketCreateView.as_view(), name='ticket_create'),
    path('<int:pk>/', TicketDetailView.as_view(), name='ticket_detail'),
    path('<int:pk>/transition/', TicketTransitionView.as_view(), name='ticket_transition'),
    path('<int:pk>/assign/', AssignTicketView.as_view(), name='ticket_assign'),
    path('<int:pk>/comment/', AddCommentView.as_view(), name='ticket_comment'),
    path('<int:pk>/worklog/', AddWorkLogView.as_view(), name='ticket_worklog'),
]
