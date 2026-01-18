from django.conf import settings 
from django.db import models
import uuid
from polymorphic.models import PolymorphicModel
from .types import NOTIFICATION_TYPE

User = settings.AUTH_USER_MODEL
Message = settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL
Room = settings.REALTIME_CHAT_MESSAGING_ROOM_MODEL


class AbstractSession(models.Model):
    """
    User session model to keep track of user sessions
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    channel_name = models.CharField()
    last_seen = models.DateTimeField()

class AbstractRoom(PolymorphicModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    last_message = models.ForeignKey(Message, on_delete=models.SET_NULL, related_name="message_room", null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class AbstractGroupChat(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="groups_owned")
    participants = models.ManyToManyField(User, related_name="groups_in")


    class Meta:
        permissions = [
            ("can_add_new_participants", "Can add new participants"),
            ("can_remove_participants", "Can remove participants")
        ]
        abstract = True


class AbstractChannel(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channels_owned")
    subscribers = models.ManyToManyField(User, related_name="channels_subscribed")

    

    class Meta:
        permissions = [
            ("can_add_new_subscribers", "Can add new subscribers"), 
            ("can_remove_subscribers", "Can remove subscribers"), 
            ("can_send_messages", "Can send messages"),
        ]
        abstract = True
        


class AbstractOneToOneChat(models.Model):
    participants = models.ManyToManyField(User, related_name="chats")
    
    class Meta:
        abstract = True

class AbstractMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="room_messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_messages")
    content = models.TextField()
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["content"], name="idx_content"),
            models.Index(fields=["content", "sender"], name="idx_sender_content")
        ]



class AbstractReadReceipt(models.Model):
    """
    Optional: 
        you can enable read receipts in settings
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="read_receipts")
    reader = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(fields=['message', 'reader'], name='unique_read_receipts'),
        ]

class AbstractReaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reactions")
    reaction_content = models.TextField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(fields=['message', 'user'], name='unique_reaction'),
        ]


class AbstractChatNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recipients = models.ManyToManyField(User, related_name='unread_messages')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=64, choices=NOTIFICATION_TYPE, default=NOTIFICATION_TYPE[1][0])

    class Meta:
        abstract = True


class AbstractMessageMediaAsset(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")

    class Meta:
        abstract = True
