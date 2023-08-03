from rest_framework import serializers
from .models import Simulcast, Stream


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = "__all__"
        read_only_fields = ["creator", "created_at", "visibility", "status"]


class SimpleStreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = ["stream_id", "title", "description", "playback_id"]


class ViewsCounterSerializer(serializers.Serializer):
    views = serializers.IntegerField(default=0)
    viewers = serializers.IntegerField(default=0)


class SimulcastSerializer(serializers.ModelSerializer):
    class Meta:
        model = Simulcast
        fields = "__all__"
