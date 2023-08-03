from rest_framework.permissions import BasePermission
from .models import Stream, StreamStatus


class StreamActive(BasePermission):
    def has_object_permission(self, request, view, obj: Stream):
        return obj.status == StreamStatus.ACTIVE


class StreamNotActive(BasePermission):
    def has_object_permission(self, request, view, obj: Stream):
        return obj.status != StreamStatus.ACTIVE


class StreamEnabled(BasePermission):
    def has_object_permission(self, request, view, obj: Stream):
        return obj.status != StreamStatus.DISABLED


class StreamDisabled(BasePermission):
    def has_object_permission(self, request, view, obj: Stream):
        return obj.status == StreamStatus.DISABLED


class CanWatchStream(BasePermission):
    def has_object_permission(self, request, view, obj: Stream):
        return True
