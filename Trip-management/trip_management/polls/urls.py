from django.urls import path, include
from .views import Polls, MyPolls, PollDetail, VoteAPI

urlpatterns = [
    path("", Polls.as_view(), name = "polls"),
    path("mypolls/", MyPolls.as_view(), name = "mypolls"),
    path('<int:pk>/', PollDetail.as_view(), name='poll-detail'),
    path('vote/<int:pk>', VoteAPI.as_view(), name = "vote"),
]