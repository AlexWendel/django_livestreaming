import base64
import mux_python
import time
import requests

from datetime import timedelta
from django.views.generic import CreateView, DetailView
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from jose import jwt
from mux_python.exceptions import NotFoundException

from .models import *
from .permissions import *
from .serializers import (
    SimpleStreamSerializer,
    SimulcastSerializer,
    StreamSerializer,
    ViewsCounterSerializer,
)

from rest_framework import status
from rest_framework.response import Response
from rest_framework.serializers import ValidationError
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.generics import (
    GenericAPIView,
    RetrieveAPIView,
    CreateAPIView,
    ListAPIView,
    DestroyAPIView,
    UpdateAPIView,
)

# TODO: Get mux settings from Database Settings App
configuration = mux_python.Configuration()
configuration.username = settings.MUX_TOKEN_ID
configuration.password = settings.MUX_TOKEN_SECRET


def epoch_to_datetime(epoch):
    return time.strftime("%Y-%m-%d %H:%M:%S", epoch)


class CreateStream(CreateAPIView):
    model = Stream
    serializer_class = StreamSerializer
    queryset = Stream.objects

    def perform_create(self, serializer):
        initial_data = serializer.validated_data

        visibility = initial_data.get("visibility", PlaybackPolicy.PUBLIC)
        latency = initial_data.get("latency_mode", StreamLatencyMode.STANDARD)
        test = initial_data.get(
            "test_mode", True
        )  # TODO: Remember to change this to false

        mux_data = self.create_mux_stream(visibility, latency, test)

        playback_id = mux_data.data.playback_ids[0].id
        stream_id = mux_data.data.id
        stream_key = mux_data.data.stream_key

        initial_data["playback_id"] = playback_id
        initial_data["stream_id"] = stream_id
        initial_data["stream_key"] = stream_key
        # initial_data["creator"] = self.request.user.profile # TODO: Set creator on create
        instance = serializer.save()

    def create_mux_stream(
        self,
        visibility=PlaybackPolicy.PUBLIC,
        latency_mode=StreamLatencyMode.STANDARD,
        test_mode=False,
    ):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))

        if visibility not in PlaybackPolicy.choices:
            visibility = PlaybackPolicy.PUBLIC

        playback_policies = {
            PlaybackPolicy.PUBLIC: mux_python.PlaybackPolicy.PUBLIC,
            PlaybackPolicy.PRIVATE: mux_python.PlaybackPolicy.SIGNED,
        }

        new_asset_settings = mux_python.CreateAssetRequest(
            playback_policy=[playback_policies[visibility]]
        )

        create_live_stream_request = mux_python.CreateLiveStreamRequest(
            playback_policy=[mux_python.PlaybackPolicy.PUBLIC],
            new_asset_settings=new_asset_settings,
            latency_mode=latency_mode,
            test=test_mode,
        )

        try:
            create_live_stream_response = live_api.create_live_stream(
                create_live_stream_request
            )
            return create_live_stream_response
        except:
            raise ValidationError(
                _("Error while performing operation: create-mux_stream")
            )


class ListStream(ListAPIView):
    model = Stream
    queryset = Stream.objects
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        return (
            StreamSerializer if self.request.user.is_staff else SimpleStreamSerializer
        )


class DeleteStream(DestroyAPIView):
    model = Stream
    queryset = Stream.objects
    permission_classes = [StreamNotActive]
    lookup_field = "stream_id"

    def perform_destroy(self, instance: Stream):
        try:
            self.delete_mux_stream(instance.stream_id)
        except:
            raise APIException("Error while performing operation: delete_mux_stream.")
        return super().perform_destroy(instance)

    def delete_mux_stream(self, stream_id):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        live_api.delete_live_stream(stream_id)


class UpdateStream(UpdateAPIView):
    model = Stream
    queryset = Stream.objects
    http_method_names = ["patch"]
    permission_classes = [StreamEnabled]
    lookup_field = "stream_id"
    serializer_class = StreamSerializer

    def perform_update(self, serializer):
        update_data: dict = serializer.validated_data

        instance = self.get_object()
        latency_mode = update_data.get("latency_mode")

        if (
            latency_mode in StreamLatencyMode.choices
            and instance.latency_mode != latency_mode
        ):
            stream_id = instance.stream_id
            self.update_mux_stream(stream_id, update_data)

        return super().perform_update(serializer)

    def update_mux_stream(self, stream_id, update_data):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        stream_update_request = mux_python.UpdateLiveStreamRequest(
            latency_mode=update_data["latency_mode"], max_continuous_duration=None
        )
        live_api.update_live_stream(
            live_stream_id=stream_id, update_live_stream_request=stream_update_request
        )


# TODO: Change the serializer used based on user permission level
class RetrieveStream(RetrieveAPIView):
    model = Stream
    queryset = Stream.objects
    lookup_field = "stream_id"
    lookup_url_kwarg = "pk"
    serializer_class = SimpleStreamSerializer


class ResetStreamKey(UpdateAPIView):
    model = Stream
    queryset = Stream.objects
    serializer_class = StreamSerializer
    permission_classes = [StreamNotActive, StreamEnabled]
    http_method_names = ["patch"]
    lookup_field = "stream_id"

    def perform_update(self, serializer):
        update_data = serializer.validated_data

        instance: Stream = self.get_object()

        try:
            new_stream_key = self.regenerate_mux_stream_key(instance.stream_id)
            update_data["stream_key"] = new_stream_key
        except:
            raise APIException(
                "Error while performing operation: reset_mux_stream_key."
            )

        return super().perform_update(serializer)

    def regenerate_mux_stream_key(self, stream_id):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        key_update = live_api.reset_stream_key(live_stream_id=stream_id)
        return key_update.data.stream_key


class FinishStream(DestroyAPIView):
    model = Stream
    queryset = Stream.objects
    serializer_class = StreamSerializer
    lookup_field = "stream_id"

    def perform_destroy(self, instance: Stream):
        try:
            self.finish_mux_stream(instance.stream_id)
        except:
            raise APIException("Error while performing operation: finish_mux_stream.")
        instance.status = StreamStatus.IDLE
        instance.save()

    def finish_mux_stream(self, stream_id):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        live_api.signal_live_stream_complete(live_stream_id=stream_id)


class DisableStream(UpdateAPIView):
    model = Stream
    queryset = Stream.objects
    serializer_class = StreamSerializer
    permission_classes = [StreamEnabled, StreamNotActive]
    http_method_names = ["patch"]
    lookup_field = "stream_id"

    def perform_update(self, serializer):
        instance: Stream = self.get_object()
        try:
            self.disable_mux_stream(instance.stream_id)
        except:
            raise APIException("Error while performing operation: disable_mux_stream.")
        instance.status = StreamStatus.DISABLED
        instance.save()

    def disable_mux_stream(self, stream_id):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        live_api.disable_live_stream(live_stream_id=stream_id)


class EnableStream(UpdateAPIView):
    model = Stream
    queryset = Stream.objects
    serializer_class = StreamSerializer
    permission_classes = [StreamDisabled]
    http_method_names = ["patch"]
    lookup_field = "stream_id"

    def perform_update(self, serializer):
        instance: Stream = self.get_object()
        try:
            self.enable_mux_stream(instance.stream_id)
        except:
            raise APIException("Error while performing operation: enable_mux_stream.")

        instance.status = StreamStatus.IDLE
        instance.save()

    def enable_mux_stream(self, stream_id):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        live_api.enable_live_stream(live_stream_id=stream_id)


class StreamStatusView(RetrieveAPIView):
    serializer_class = ViewsCounterSerializer
    queryset = StreamStatusJWT.objects
    permission_classes = [StreamEnabled]
    lookup_field = "stream_id"

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())

        # Perform the lookup filtering.
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        assert lookup_url_kwarg in self.kwargs, (
            "Expected view %s to be called with a URL keyword argument "
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            "attribute on the view correctly."
            % (self.__class__.__name__, lookup_url_kwarg)
        )

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = queryset.filter(**filter_kwargs)

        # Making sure the stream exists
        stream = Stream.objects.filter(id=filter_kwargs["stream_id"])
        if not stream.exists():
            raise APIException(_("Stream not found."), status.HTTP_404_NOT_FOUND)

        stream_instance = stream.first()

        # Create JWT if doesn't exist
        if not obj.exists():
            status_token = self.create_status_token(stream_instance)
        else:
            instance: StreamStatusJWT = obj.first()
            expired = instance.expires_at < timezone.now()
            status_token = instance

            # If the JWT is expired, delete the old and create a new one.
            if expired:
                instance.delete()
                status_token = self.create_status_token(stream_instance)

        # May raise a permission denied
        self.check_object_permissions(self.request, status_token.stream)

        return status_token

    def create_status_token(self, stream: Stream):
        expiration_time = timezone.now() + timedelta(hours=5)
        key = self.generate_jwt(stream_id=stream.id, expires_at=expiration_time)
        status_token = StreamStatusJWT.objects.create(
            token=key, stream=stream, expires_at=expiration_time
        )
        return status_token

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer_class = self.get_serializer_class()
        kwargs.setdefault("context", self.get_serializer_context())

        stream_id = instance.stream.id
        try:
            status = self.get_stream_status(stream_id)
            serializer = serializer_class(instance)

            return Response(serializer.data)
        except NotFoundException:
            raise APIException(_("Stream not found"), status.HTTP_404_NOT_FOUND)

    def generate_jwt(self, stream_id, expires_at):
        # TODO: Get keys from Database Settings App
        signing_key_id = settings.MUX_SIGNING_KEY
        private_key_base64 = settings.MUX_PRIVATE_KEY
        private_key = base64.b64decode(private_key_base64).decode("utf-8")

        token = {
            "sub": stream_id,
            "exp": expires_at,  # 5 hours
            "aud": "live_stream_id",
        }
        headers = {"kid": signing_key_id}

        json_web_token = jwt.encode(
            token, private_key, algorithm="RS256", headers=headers
        )
        return json_web_token

    def get_stream_status(self, token):
        r = requests.get(f"https://stats.mux.com/counts?token={token}")
        return r.json()


# Simulcasts
class CreateStreamSimulcast(CreateAPIView):
    models = Simulcast
    queryset = Simulcast.objects
    permission_classes = [StreamEnabled, StreamNotActive]
    serializer_class = SimulcastSerializer

    def perform_create(self, serializer):
        initial_data = serializer.validated_data

        stream = initial_data["stream"]
        stream_key = initial_data["stream_key"]
        url = initial_data["url"]

        # Getting simulacast ID
        simulcast = self.create_mux_simulcast(stream.stream_id, stream_key, url)
        initial_data["simulcast_id"] = simulcast.data.id
        serializer.save()

    def create_mux_simulcast(
        self, stream_id, stream_key, url
    ) -> mux_python.SimulcastTarget:
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        request = mux_python.CreateSimulcastTargetRequest(
            stream_key=stream_key, url=url
        )
        return live_api.create_live_stream_simulcast_target(
            stream_id, create_simulcast_target_request=request
        )


class ListStreamSimulcasts(ListAPIView):
    models = Simulcast
    serializer_class = SimulcastSerializer
    lookup_url_kwarg = "stream_id"

    def get_queryset(self):
        stream_id = self.kwargs[self.lookup_url_kwarg]
        return Simulcast.objects.filter(stream__stream_id=stream_id)


class RemoveStreamSimulcast(DestroyAPIView):
    models = Simulcast
    queryset = Simulcast.objects
    serializer_class = SimulcastSerializer
    permission_classes = [StreamEnabled, StreamNotActive]
    lookup_field = "simulcast_id"
    lookup_url_kwarg = "simulcast_id"

    def perform_destroy(self, instance: Simulcast):
        try:
            self.remove_mux_simulcast(instance.stream.stream_id, instance.simulcast_id)
        except mux_python.exceptions.ApiException:
            raise ValidationError(
                _("Error while performing operation: remove_mux_simulcast")
            )
        return super().perform_destroy(instance)

    def remove_mux_simulcast(self, stream_id, simulcast_id):
        live_api = mux_python.LiveStreamsApi(mux_python.ApiClient(configuration))
        live_api.delete_live_stream_simulcast_target(
            live_stream_id=stream_id, simulcast_target_id=simulcast_id
        )


class RetrieveStreamSimulcast(RetrieveAPIView):
    models = Simulcast

    def get_queryset(self):
        stream_id = self.kwargs.get("stream_id", "")
        simulcast_id = self.kwargs.get("simulcast_id", "")
        return Simulcast.objects.filter(stream_id=stream_id, simulcast_id=simulcast_id)


# Webhooks
class UpdateStreamStatus(GenericAPIView):
    pass
