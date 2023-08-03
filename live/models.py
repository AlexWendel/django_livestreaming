from pathlib import Path

from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.dispatch import receiver

THUMBNAILS_UPLOAD_PATH = Path("lives/thumbnails/")


class Profile(models.Model):
    first_name = models.CharField(max_length=64)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")


class PlaybackPolicy(models.TextChoices):
    PUBLIC = "public", _("Public")
    PRIVATE = "private", _("Private")


class StreamLatencyMode(models.TextChoices):
    LOW = "low", _("Low")
    REDUCED = "reduced", _("Reduced")
    STANDARD = "standard", _("Standard")


class StreamStatus(models.TextChoices):
    IDLE = "idle", _("Idle")
    ACTIVE = "active", _("Active")
    DISABLED = "disabled", _("Disabled")


class StreamStatusJWT(models.Model):
    token = models.TextField(null=False)
    stream = models.OneToOneField(
        "Stream", on_delete=models.CASCADE, related_name="status_jwt"
    )
    expires_at = models.DateTimeField(null=False)


class StreamThumbnail(models.Model):
    stream = models.OneToOneField(
        "Stream", on_delete=models.CASCADE, related_name="thumbnail"
    )
    thumbnail = models.ImageField(
        upload_to=f"{THUMBNAILS_UPLOAD_PATH}/",
        null=False,
        default=(THUMBNAILS_UPLOAD_PATH / "default.png").as_posix(),
    )


class Stream(models.Model):
    stream_id = models.CharField(max_length=80, null=True)
    stream_key = models.CharField(max_length=64, null=True)
    playback_id = models.CharField(max_length=100, null=True)
    title = models.CharField(max_length=250, null=False)
    description = models.TextField(null=True)
    status = models.CharField(
        max_length=10, choices=StreamStatus.choices, default=StreamStatus.IDLE
    )

    visibility = models.CharField(
        max_length=7, choices=PlaybackPolicy.choices, default=PlaybackPolicy.PUBLIC
    )
    latency_mode = models.CharField(
        max_length=8,
        choices=StreamLatencyMode.choices,
        default=StreamLatencyMode.STANDARD,
    )
    test_mode = models.BooleanField(default=True)
    # enabled = models.BooleanField(default=True)

    creator = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="streams", null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def thumbnail_url(self):
        if self.status != StreamStatus.ACTIVE:
            return self.thumbnail.thumbnail.url
        return f"https://image.mux.com/{self.playback_id}/animated.webp"


class SimulcastService(models.Model):
    rmtp_url = models.CharField(max_length=256)
    name = models.CharField(max_length=32, unique=True)


class Simulcast(models.Model):
    class Meta:
        unique_together = ("stream_key", "stream")  # TODO: Make this work

    simulcast_id = models.CharField(
        max_length=128, unique=True
    )  # TODO: Remove this null
    stream = models.ForeignKey(Stream, on_delete=models.CASCADE)
    stream_key = models.CharField(max_length=128, unique=True)
    url = models.CharField(max_length=512)


# Create thumbnail when new stream is created
@receiver(models.signals.post_save, sender=Stream)
def create_thumbnail(sender, instance: Stream, created: bool, **kwargs):
    if created:
        stream_thumbnail = StreamThumbnail(stream=instance)
        stream_thumbnail.save()
