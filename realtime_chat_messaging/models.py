from django.db import models
from django.contrib.auth import get_user_model
# Create your models here.
from django.db.models import F,Q
import uuid
from polymorphic.models import PolymorphicModel
from .types import ALLOWED_MIME_TYPES
from .model_mixins import AbstractChannel, AbstractGroupChat, AbstractMessage, AbstractOneToOneChat

User = get_user_model()



class Room(PolymorphicModel):
    """Generic models for all chat types"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    preferences = models.JSONField(default=dict)


class OneToOneChat(Room, AbstractOneToOneChat):
    pass



class GroupChat(Room, AbstractGroupChat):
    admins = models.ManyToManyField(User, related_name="groups_moderated")
    participants = models.ManyToManyField(User, related_name="groups_in")
    max_participants = models.PositiveBigIntegerField(default=10)
    avatar = models.URLField(null=True, blank=True)
    join_approval_required = models.BooleanField(default=False)
    group_locked = models.BooleanField(default=False) # in the case of "only admins can send messages"

    permissions = [
        ('can_add_new_participants', "Can add new participants")
    ]

class Channel(Room, AbstractChannel):
    subscribers = models.ManyToManyField(User, related_name="channels_subscribed")
    is_public = models.BooleanField(default=False)
    avatar = models.URLField(null=True, blank=True)
    moderators = models.ManyToManyField(User, related_name="channels_moderated")
    
    class Meta:
        permissions = [
            ("can_add_new_subscribers", "Can add new subscribers"), 
            ("can_send_messages", "Can send messages"),
        ]

    


class Message(AbstractMessage):
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name="replies")
    is_forwarded = models.BooleanField(default=False)
    forwarded_from = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name="forwarded")
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["content"], name="idx_content"),
            models.Index(fields=["content", "sender"], name="idx_sender_content")
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(is_forwarded=True, parent_message__isnull=False),
                name="forwarded_messages_cant_be_replies"
            )
        ]


class ReadReceipt(models.Model):

    """
    Optional: 
        you can enable read receipts in settings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="read")
    reader = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

class ChatNotification(models.Model):
    """
    Optional:
        you can enable notifications in settings.
    """
    NOTIFICATION_TYPE = (
        ('reaction', 'REACTION'),
        ('new_message', 'NEW_MESSAGE'),
        ('reply', 'REPLY')
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=64, choices=NOTIFICATION_TYPE, default=NOTIFICATION_TYPE[1][1])
    is_read = models.BooleanField(default=False)


class Reaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reactions")
    reaction_content = models.TextField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)


class MessageMediaAsset(models.Model):
    MEDIATYPE_CHOICES = [
        ("image", "Image"),
        ("video", "Video"),  # includes video notes 
        ("audio", "Audio"),  # includes voice notes
        ("file", "File"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    media_url = models.TextField() # This is the external link — not the file itself
    media_type = models.CharField(max_length=64, choices=MEDIATYPE_CHOICES)
    file_size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(blank=True, null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
         constraints = [
            models.CheckConstraint(
                condition=Q(mime_type__in=ALLOWED_MIME_TYPES),
                name="valid_mime_type"
            )
        ]
    """
    metadata samples
    for video note
        {
            "duration": 12.5,              # in seconds
            "resolution": "1080x1920",     # width x height
            "fps": 30,                      # frames per second
            "orientation": "portrait",      # or landscape
            "audio_codec": "aac",           # optional
            "video_codec": "h264",          # optional
            "size": 15234321                # optional, in bytes
        }

    for normal videos

        {
            "duration": 15.2,
            "resolution": "1080x1920",
            "fps": 30
        }

    for images
        {
            "width": 1080,
            "height": 1920,
            "orientation": "portrait"
        }
    
    for audio and voice notes
        {
            "duration": 2.8,
            "waveform": [0.2, 0.5, 0.1],
            "bitrate": 96000
        }

        {
            "pages": 43
        }


    """


