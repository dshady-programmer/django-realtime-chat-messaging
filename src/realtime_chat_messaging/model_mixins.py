from django.conf import settings 
from django.db import models
import uuid

from .types import NOTIFICATION_TYPE

User = settings.AUTH_USER_MODEL
Message = settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL
Room = settings.REALTIME_CHAT_MESSAGING_ROOM_MODEL


class AbstractSession(models.Model):
    """
    User session model to keep track of user sessions
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    channel_name = models.CharField()
    last_seen = models.DateTimeField()
        
    class Meta:
        abstract = True

class AbstractRoomProperty(models.Model):
    """
    Additional properties for a Room

    Use case: mute status, notification preferences, etc.

    Use this model to extend Room model without modifying it directly
    """
    preferences = models.JSONField(default=dict)
    
    class Meta:
        abstract = True

class AbstractGroupChat(models.Model):
    """
    Group Chat model base fields
    """
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    participants = models.ManyToManyField(User, related_name="+")


    class Meta:
        permissions = [
            ("can_add_new_participants", "Can add new participants"),
            ("can_remove_participants", "Can remove participants")
        ]
        abstract = True


class AbstractChannel(models.Model):

    """  
    Channel model base fields
    """
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    subscribers = models.ManyToManyField(User, related_name="+")

    

    class Meta:
        permissions = [
            ("can_add_new_subscribers", "Can add new subscribers"), 
            ("can_remove_subscribers", "Can remove subscribers"), 
            ("can_send_messages", "Can send messages"),
        ]
        abstract = True
        


class AbstractOneToOneChat(models.Model):
    """
    One to One Chat model base fields
    """

    participants = models.ManyToManyField(User, related_name="+")
    
    class Meta:
        abstract = True

class AbstractMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="+")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    content = models.TextField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["content"]),
            models.Index(fields=["content", "sender"])
        ]



class AbstractReadReceipt(models.Model):
    """
    Optional: 
        you can enable read receipts in settings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="%(app_label)s_%(class)s_read_receipts")
    reader = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(fields=['message', 'reader'], name='unique_read_receipts'),
        ]

class AbstractReaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="%(app_label)s_%(class)s_reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="%(app_label)s_%(class)s_reactions")
    reaction_content = models.TextField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(fields=['message', 'user'], name='unique_reaction'),
        ]


class AbstractChatNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recipients = models.ManyToManyField(User, related_name='%(app_label)s_%(class)s_unread_messages')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_notifications')
    notification_type = models.CharField(max_length=64, choices=NOTIFICATION_TYPE, default=NOTIFICATION_TYPE[1][0])

    class Meta:
        abstract = True


class AbstractMessageMediaAsset(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="%(app_label)s_%(class)s_attachments")

    class Meta:
        abstract = True
