from django.db import models
from django.contrib.auth import get_user_model
# Create your models here.
from django.db.models import F,Q
import uuid
from polymorphic.models import PolymorphicModel
from .types import ALLOWED_MIME_TYPES, MEDIATYPE_CHOICES
from .model_mixins import (
    AbstractRoom, AbstractChannel, AbstractGroupChat, 
    AbstractMessage, AbstractOneToOneChat, 
    AbstractReadReceipt, AbstractReaction, 
    AbstractChatNotification, AbstractMessageMediaAsset
)

User = get_user_model()



class Room(PolymorphicModel, AbstractRoom):
    """Generic models for all chat types"""
    preferences = models.JSONField(default=dict)
  


class OneToOneChat(Room, AbstractOneToOneChat):
    pass



class GroupChat(Room, AbstractGroupChat):
    admins = models.ManyToManyField(User, related_name="groups_moderated")
    max_participants = models.PositiveBigIntegerField(default=100)
    avatar = models.URLField(null=True, blank=True)
    join_approval_required = models.BooleanField(default=False)
    group_locked = models.BooleanField(default=False) # in the case of "only admins can send messages"

    class Meta:
        permissions = [
            ("can_add_new_participants", "Can add new participants"),
            ("can_remove_participants", "Can remove participants")
        ]

class Channel(Room, AbstractChannel):
    is_public = models.BooleanField(default=False)
    avatar = models.URLField(null=True, blank=True)
    moderators = models.ManyToManyField(User, related_name="channels_moderated")
    max_subscribers = models.PositiveBigIntegerField(default=300)
    
    class Meta:
        permissions = [
            ("can_add_new_subscribers", "Can add new subscribers"), 
            ("can_remove_subscribers", "Can remove subscribers"), 
            ("can_send_messages", "Can send messages"),
        ]

    


class Message(AbstractMessage):
    parent_message = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name="replies")
    is_forwarded = models.BooleanField(default=False)
    forwarded_from = models.ForeignKey('self', on_delete=models.SET_NULL, blank=True, null=True, related_name="forwarded")
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    delivered_to  = models.ManyToManyField(User, related_name="messages_received")

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


class ReadReceipt(AbstractReadReceipt):

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['message', 'reader'], name='unique_read_receipts'),
        ]

class ChatNotification(AbstractChatNotification):
    """
    Optional:
        you can enable notifications in settings.

    ChatNotification serves as a way to track undelivered messages, you can integrate with push notification services like firebase, aws sns etc..

    How it works: 
        When a message is sent to a room (OneToOneChat, GroupChat, Channel) a chat notication is created
        recipients would all the participants for OneToOneChat, GroupChat, Channel
        For each message read event that happens the user who opens the message would be removed from the recipient list 
        When there's no more user left in the recipients list, the notification would be deleted.

        This way notifications aren't created for every user, instead notifications are created per message basis
    """
    pass



class Reaction(AbstractReaction):
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['message', 'user'], name='unique_reaction'),
        ]


class MessageMediaAsset(AbstractMessageMediaAsset):


    media_url = models.CharField() # This is the external link — not the file itself
    media_type = models.CharField(max_length=64, choices=MEDIATYPE_CHOICES)
    file_size = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(default="image/jpeg")
    caption = models.CharField(blank=True, null=True)
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


    """




