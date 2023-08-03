from django.urls import path
from .views import (
    CreateStream,
    FinishStream,
    ListStream,
    ListStreamSimulcasts,
    RemoveStreamSimulcast,
    ResetStreamKey,
    StreamStatusView,
    UpdateStream,
    RetrieveStream,
    DeleteStream,
    CreateStreamSimulcast,
    RetrieveStreamSimulcast,
)

urlpatterns = [
    path("list/", ListStream.as_view(), name="list-stream"),
    path("create/", CreateStream.as_view(), name="create-stream"),
    path("delete/<str:stream_id>", DeleteStream.as_view(), name="delete-stream"),
    path("finish/<str:stream_id>", FinishStream.as_view(), name="delete-stream"),
    path(
        "edit/<str:stream_id>/reset-stream-key",
        ResetStreamKey.as_view(),
        name="reset-stream-key",
    ),
    path("edit/<str:stream_id>", UpdateStream.as_view(), name="update-stream"),
    path("status/<int:stream_id>", StreamStatusView.as_view(), name="view-status"),
    path(
        "simulcast/<str:stream_id>/<str:simulcast_id>",
        RetrieveStreamSimulcast.as_view(),
        name="view-simulcast",
    ),
    path("simulcast/create", CreateStreamSimulcast.as_view(), name="create-simulcast"),
    path(
        "simulcast/list/<str:stream_id>",
        ListStreamSimulcasts.as_view(),
        name="list-simulcast",
    ),
    path(
        "simulcast/delete/<str:simulcast_id>",
        RemoveStreamSimulcast.as_view(),
        name="delete-simulcast",
    ),
    path("<str:pk>/", RetrieveStream.as_view(), name="view-stream"),
]
