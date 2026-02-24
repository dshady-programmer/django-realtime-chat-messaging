"""
Abstract base models for the real-time chat messaging system.

These abstract models define the core fields and structure for chat entities.
Extend these models to add custom fields or override behavior without
modifying the package source code.

All models use %(app_label)s_%(class)s in related names to prevent conflicts
when extending in custom applications.
"""


from django.conf import settings 
from django.db import models
import uuid

from ..types import NOTIFICATION_TYPE

User = settings.AUTH_USER_MODEL
Message = settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL
Room = settings.REALTIME_CHAT_MESSAGING_ROOM_MODEL


class AbstractSession(models.Model):
    """
        Tracks active WebSocket connections for multi-device support.

        Fields:
            user: The authenticated user for this session
            channel_name: Django Channels layer channel identifier
            last_seen: Last activity timestamp (updated via heartbeat events)

        Note:
            Sessions older than INACTIVITY_THRESHOLD are considered expired
            and cleaned up on user reconnection.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    channel_name = models.CharField()
    last_seen = models.DateTimeField()
        
    class Meta:
        abstract = True

class AbstractRoomProperty(models.Model):
    """
        Extensible room configuration and preferences storage.

        Use this to store room-specific settings without modifying the Room
        model directly. Automatically created for every room via signals.

        Fields:
            preferences: JSON field for storing arbitrary room settings
                (e.g., mute status, notification preferences, themes)

        Note: 
            You should inherit and extend from this if you plan to add 
            more fields to the room
    """
    preferences = models.JSONField(default=dict)
    
    class Meta:
        abstract = True

class AbstractGroupChat(models.Model):
    """
        Base fields for multi-user chat rooms with admin controls.

        Fields:
            name: Display name for the group
            description: Optional group description
            creator: User who created the group (auto-assigned as admin)
            participants: All users in the group

        Permissions:
            - can_add_new_participants: Add members to group
            - can_remove_participants: Remove members from group
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
        Base fields for broadcast channels with moderator controls.

        Fields:
            name: Display name for the channel
            description: Optional channel description
            creator: User who created the channel (auto-assigned as moderator)
            subscribers: All users subscribed to the channel

        Permissions:
            - can_add_new_subscribers: Add subscribers to channel
            - can_remove_subscribers: Remove subscribers from channel
            - can_send_messages: Send messages in the channel

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
    Base fields for private chats between two users.

    Fields:
        participants: Must contain exactly 2 users (enforced by signals)
    """

    participants = models.ManyToManyField(User, related_name="+")
    
    class Meta:
        abstract = True

class AbstractMessage(models.Model):
    """
        Base fields for chat messages.

        Fields:
            id: UUID primary key
            room: The room this message belongs to
            sender: User who sent the message
            content: Message text content
            is_deleted: Soft delete flag (if MESSAGE_SOFT_DELETE enabled)
            created_at: Message creation timestamp
            updated_at: Last modification timestamp

        Indexes:
            - content: For message search
            - (content, sender): For filtered message search
    """

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
        Tracks when users read messages.

        Fields:
            id: UUID primary key
            message: The message that was read
            reader: The user who read the message
            read_at: Timestamp when message was read

        Constraint:
            Each user can only have one read receipt per message.
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

    """
        Emoji reactions to messages.

        Fields:
            id: UUID primary key
            message: The message being reacted to
            user: The user who reacted
            reaction_content: The emoji or reaction text (max 128 chars)
            created_at: When the reaction was added

        Constraint:
            Each user can only have one reaction per message. Changing reactions
            automatically deletes the old one (enforced by signals).
    """    
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

    """
        Tracks undelivered messages for push notification integration.

        Fields:
            id: UUID primary key
            recipients: Users who haven't received the message yet
            message: The message this notification is for
            notification_type: Type of notification (from NOTIFICATION_TYPE choices)

        Lifecycle:
            1. Created when message is sent to a room
            2. Recipients initialized with all room participants
            3. Users removed from recipients as they acknowledge delivery
            4. Auto-deleted when recipients list becomes empty (via signals)

        Note:
            Enable via ENABLE_NOTIFICATION setting. Design supports integration
            with Firebase, AWS SNS, or similar push notification services.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recipients = models.ManyToManyField(User, related_name='%(app_label)s_%(class)s_unread_messages')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_notifications')
    notification_type = models.CharField(max_length=64, choices=NOTIFICATION_TYPE, default=NOTIFICATION_TYPE[1][0])

    class Meta:
        abstract = True


class AbstractMessageMediaAsset(models.Model):
    """
        Base fields for external media attachments.

        Fields:
            id: UUID primary key
            message: The message this media is attached to
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="%(app_label)s_%(class)s_attachments")

    class Meta:
        abstract = True
