from django.urls import path
from .views import WatchStream, ListStreams

urlpatterns = [
    path("", view=ListStreams.as_view(), name="list"),
    path("<str:pk>", view=WatchStream.as_view(), name="view"),
]
