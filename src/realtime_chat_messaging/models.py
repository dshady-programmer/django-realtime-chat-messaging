"""
Core data models for the realtime_chat_messaging.

Defines the database schema for rooms (OneToOneChat, GroupChat, Channel),
messages, reactions, read receipts, notifications, and media assets.
All models except Room (being a polymorphic model) are swappable to allow for custom implementations.
"""

import uuid
from django.db import models
from django.conf import settings 
from polymorphic.models import PolymorphicModel
from django.db.models import Q
from .types import ALLOWED_MIME_TYPES, MEDIATYPE_CHOICES
from .mixins.models import (
    AbstractRoomProperty, AbstractChannel, AbstractGroupChat, 
    AbstractMessage, AbstractOneToOneChat, 
    AbstractReadReceipt, AbstractReaction, 
    AbstractChatNotification, AbstractMessageMediaAsset,
    AbstractSession
)

User = settings.AUTH_USER_MODEL



class Session(AbstractSession):
    """
        Concrete session model (swappable).

        Inherits all fields from AbstractSession. Override by creating a custom
        model and updating MODELS['Session'] in settings.
    """  
    class Meta:
        swappable = 'REALTIME_CHAT_MESSAGING_SESSION_MODEL'


class RoomProperty(AbstractRoomProperty):
    """
        Concrete room property model (swappable).

        Inherits preferences JSONField from AbstractRoomProperty. Extend this to
        add additional configuration fields for rooms.
    """
    class Meta:
        swappable = 'REALTIME_CHAT_MESSAGING_ROOMPROPERTY_MODEL'

class Room(PolymorphicModel):
    """
        Base model for all chat room types.

        Uses django-polymorphic to enable querying across OneToOneChat, GroupChat,
        and Channel with a single query. All custom chat types must inherit from
        this model.

        Note:
            The polymorphic pattern allows room lists to be retrieved efficiently
            without separate queries for each room type.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    last_message = models.ForeignKey(settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    property = models.OneToOneField(settings.REALTIME_CHAT_MESSAGING_ROOMPROPERTY_MODEL, on_delete=models.CASCADE, related_name="+")

class OneToOneChat(Room, AbstractOneToOneChat):
    """
        Concrete one-to-one chat model (swappable).

        Inherits participants field from AbstractOneToOneChat and polymorphic
        fields from Room. Signals enforce exactly 2 participants.
    """ 
    class Meta:
        swappable = 'REALTIME_CHAT_MESSAGING_ONETOONECHAT_MODEL'

class GroupChat(Room, AbstractGroupChat):
    """
        Concrete group chat model with admin controls (swappable).

        Inherits base fields from AbstractGroupChat. Adds:
        - admins: Users with management permissions
        - max_participants: Member limit (default 100)
        - avatar: Optional group image URL
        - join_approval_required: Requires admin approval to join
        - group_locked: When true, only admins can send messages
    """   
    admins = models.ManyToManyField(User, related_name="+")
    max_participants = models.PositiveBigIntegerField(default=100)
    avatar = models.URLField(null=True, blank=True)
    join_approval_required = models.BooleanField(default=False)
    group_locked = models.BooleanField(default=False) # in the case of "only admins can send messages"

    class Meta(AbstractGroupChat.Meta):
        abstract = False
        swappable = 'REALTIME_CHAT_MESSAGING_GROUPCHAT_MODEL'

class Channel(Room, AbstractChannel):
    """
        Concrete broadcast channel model with moderator controls (swappable).

        Inherits base fields from AbstractChannel. Adds:
        - is_public: Public channels are discoverable
        - avatar: Optional channel image URL
        - moderators: Users who can send messages and manage subscribers
        - max_subscribers: Subscriber limit (default 300)

        Note:
            By default, only moderators can send messages. Grant can_send_messages
            permission to specific subscribers for wider participation.
    """    
    is_public = models.BooleanField(default=False)
    avatar = models.URLField(null=True, blank=True)
    moderators = models.ManyToManyField(User, related_name="+")
    max_subscribers = models.PositiveBigIntegerField(default=300)
    
    class Meta(AbstractChannel.Meta):
        abstract = False
        swappable = 'REALTIME_CHAT_MESSAGING_CHANNEL_MODEL'

    


class Message(AbstractMessage):
    """
        Concrete message model with replies, forwarding, and editing (swappable).

        Inherits base fields from AbstractMessage. Adds:
        - parent_message: Creates reply thread
        - is_forwarded: Marks message as forwarded
        - forwarded_from: Original message source
        - is_edited: Tracks if content was modified
        - delivered_to: Users who have acknowledged delivery

        Constraint:
            Forwarded messages cannot be replies (DB-enforced).
    """    
    parent_message = models.ForeignKey(settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="%(app_label)s_%(class)s_replies")
    is_forwarded = models.BooleanField(default=False)
    forwarded_from = models.ForeignKey(settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="+")
    is_edited = models.BooleanField(default=False)
    delivered_to  = models.ManyToManyField(User, related_name="+")

    class Meta(AbstractMessage.Meta):
        abstract = False
        constraints = [
            models.CheckConstraint(
                condition=~Q(is_forwarded=True, parent_message__isnull=False),
                name="forwarded_messages_cant_be_replies"
            )
        ]
        swappable = 'REALTIME_CHAT_MESSAGING_MESSAGE_MODEL'


class ReadReceipt(AbstractReadReceipt):
    """
        Concrete read receipt model (swappable).

        Inherits all fields from AbstractReadReceipt. Tracks when users read
        messages and broadcasts via readreceipt.dispatch event.
    """
    class Meta(AbstractReadReceipt.Meta):
        abstract = False
        swappable = 'REALTIME_CHAT_MESSAGING_READRECEIPT_MODEL'



class ChatNotification(AbstractChatNotification):
    """
        Concrete notification model for push integration (swappable).

        Inherits all fields from AbstractChatNotification. Enable via
        ENABLE_NOTIFICATION setting for Firebase, AWS SNS, etc. integration.

        How it works: 
            When a message is sent to a room (OneToOneChat, GroupChat, Channel) a chat notication is created
            `recipients` would be all the participants of the room(OneToOneChat, GroupChat, Channel)
            For each message delivered event that happens the user who gets the message would be removed from the recipient list 
            When there's no more user left in the recipients list, the notification would be deleted.

            With this approach notifications are created per message basis
    """
    class Meta:
        swappable = 'REALTIME_CHAT_MESSAGING_CHATNOTIFICATION_MODEL'



class Reaction(AbstractReaction):
    """
    Concrete reaction model (swappable).

    Inherits all fields from AbstractReaction. Signals automatically replace
    old reactions when users react to the same message again.
    """    
    class Meta(AbstractReaction.Meta):
        abstract = False
        swappable = 'REALTIME_CHAT_MESSAGING_REACTION_MODEL'


class MessageMediaAsset(AbstractMessageMediaAsset):
    """
    External media attachments for messages.

    Stores URLs and metadata for images, videos, audio, voice notes, and
    video notes. Does not store files directly - use your own CDN/storage.

    Fields:
        media_url: External link to the media file
        media_type: Type category (image, video, audio, voice_note, video_note)
        mime_type: Must be in ALLOWED_MIME_TYPES (enforced by constraint)
        metadata: JSON field for type-specific data

    Metadata Examples:
        Video note::

            {
                "duration": 12.5,
                "resolution": "1080x1920",
                "fps": 30,
                "orientation": "portrait",
                "audio_codec": "aac",
                "video_codec": "h264"
            }

        Image::

            {
                "width": 1080,
                "height": 1920,
                "orientation": "portrait"
            }

        Audio/Voice note::

            {
                "duration": 2.8,
                "waveform": [0.2, 0.5, 0.1],
                "bitrate": 96000
            }
    """
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
        swappable = 'REALTIME_CHAT_MESSAGING_MESSAGEMEDIAASSET_MODEL'





