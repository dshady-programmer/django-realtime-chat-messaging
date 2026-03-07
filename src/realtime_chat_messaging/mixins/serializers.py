"""
Serializer mixins

These mixins provide reusable Fields, SerializerMethodFields and validation logic
for chat models. They handle nested serialization of related objects and
provide write-only fields for creating/updating instances.

All mixins use get_serializer() and get_model() for dynamic resolution,
allowing custom serializers and models to be used without code modification.

Usage:
    Extend these mixins in your concrete serializers::

        class CustomMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = Message
                fields = '__all__'
"""


from rest_framework import serializers
import bleach
from realtime_chat_messaging.utils.loader import get_model, get_serializer
from django.contrib.auth import get_user_model
User = get_user_model()




class OneToOneChatListSerializerMixin(serializers.Serializer):
    """
        Mixin for listing OneToOneChat rooms with peer and last message.

        Provides:
            - peer: The other participant (excludes current user)
            - last_message: Most recent message in the room

        Context Required:
            user: Current user to determine which participant is the peer
    """    
    peer = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    def get_peer(self, instance):
        """Get the other participant in the chat."""

        user = self.context.get('user')
        if not user:
            raise Exception("user context is required")
        peers = instance.participants.exclude(id=user.id)
        return get_serializer("UserSerializer")(peers.first()).data

    def get_last_message(self, instance):
        """Get the most recent message in the room."""
        return get_serializer("MessageSerializer")(instance.last_message).data


class GroupChatListSerializerMixin(serializers.Serializer):
    """
        Mixin for listing GroupChat rooms with creator and last message.

        Provides:
            - creator: User who created the group
            - last_message: Most recent message in the room
    """    
    creator = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    def get_last_message(self, instance):
        """Get the most recent message in the room."""
        return get_serializer("MessageSerializer")(instance.last_message).data

    def get_creator(self, obj):
        """Get the user who created the group."""
        return get_serializer("UserSerializer")(obj.creator).data

class ChannelListSerializerMixin(serializers.Serializer):
    """
        Mixin for listing Channel rooms with creator and last message.

        Provides:
            - creator: User who created the channel
            - last_message: Most recent message in the room
    """    
    creator = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    def get_last_message(self, instance):
        """Get the most recent message in the room."""
        return get_serializer("MessageSerializer")(instance.last_message).data

    def get_creator(self, obj):
        """Get the user who created the channel."""
        return get_serializer("UserSerializer")(obj.creator).data


class OneToOneChatSerializerMixin(serializers.Serializer):
    """
        Mixin for detailed OneToOneChat serialization.

        Provides:
            - participants: Both users in the chat
            - property: Room preferences and settings
    """    
    participants = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()

    def get_participants(self, obj):
        """Get all participants in the chat."""
        return get_serializer("UserSerializer")(obj.participants.all(), many=True).data

    def get_property(self, obj):
        """Get room property (preferences, settings)."""
        if hasattr(obj, 'property') and obj.property:
            return get_serializer("RoomPropertySerializer")(obj.property).data
        return None

class GroupChatSerializerMixin(serializers.Serializer):
    """
        Mixin for detailed GroupChat serialization.

        Provides:
            - creator: User who created the group
            - participants: All group members
            - property: Room preferences and settings
    """

    creator = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()

    def get_creator(self, obj):
        """Get the user who created the group."""
        return get_serializer("UserSerializer")(obj.creator).data

    def get_participants(self, obj):
        """Get all participants in the group."""
        return get_serializer("UserSerializer")(obj.participants.all(), many=True).data

    def get_property(self, obj):
        """Get room property (preferences, settings)."""
        if hasattr(obj, 'property') and obj.property:
            return get_serializer("RoomPropertySerializer")(obj.property).data
        return None


class ChannelSerializerMixin(serializers.Serializer):
    """
        Mixin for detailed Channel serialization.

        Provides:
            - creator: User who created the channel
            - subscribers: All channel subscribers
            - property: Room preferences and settings
    """    
    creator = serializers.SerializerMethodField()
    subscribers = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()

    def get_creator(self, obj):
        """Get the user who created the channel."""
        return get_serializer("UserSerializer")(obj.creator).data

    def get_subscribers(self, obj):
        """Get all subscribers in the channel."""
        return get_serializer("UserSerializer")(obj.subscribers.all(), many=True).data

    def get_property(self, obj):
        """Get room property (preferences, settings)."""
        if hasattr(obj, 'property') and obj.property:
            return get_serializer("RoomPropertySerializer")(obj.property).data
        return None


class ReadReceiptSerializerMixin(serializers.Serializer):
    """
        Mixin for ReadReceipt serialization.

        Provides:
            - reader: User who read the message (read-only nested)
            - reader_id: User ID for creating receipts (write-only)
            - message_id: Message ID for creating receipts (write-only)
    """   

    reader = serializers.SerializerMethodField()
    reader_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="reader", 
        write_only=True,
        required=True,
    )
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message", 
        write_only=True,
        required=True,
    )
    def get_reader(self, obj):
        """Get the user who read the message."""
        return get_serializer("UserSerializer")(obj.reader).data

class ReactionSerializerMixin(serializers.Serializer):
    """
        Mixin for Reaction serialization.

        Provides:
            - user: User who reacted (read-only nested)
            - user_id: User ID for creating reactions (write-only)
            - message: Message ID for creating reactions (write-only)
    """

    user = serializers.SerializerMethodField()
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user", 
        write_only=True,
        required=True,
    )
    message = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(), required=True,
        write_only=True
    )
    
    def get_user(self, obj):
        """Get the user who reacted."""
        return get_serializer("UserSerializer")(obj.user).data


class MessageMediaAssetSerializerMixin(serializers.Serializer):
    """
        Mixin for MessageMediaAsset serialization.

        Provides:
            - message_id: Message ID for creating attachments (write-only)
    """    
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message", 
        write_only=True,
        required=True,
    )



class MessageSerializerMixin(serializers.Serializer):
    """
        Mixin for Message serialization with nested relationships.

        Provides:
            - room: Minimal room info (read-only)
            - room_id: Room ID for creating messages (write-only)
            - sender: User who sent the message (read-only nested)
            - sender_id: User ID for creating messages (write-only)
            - read_receipts: All read receipts for this message
            - reactions: All reactions to this message
            - attachments: All media attachments

        Validation:
            - content: Sanitizes HTML to prevent XSS attacks (uses bleach)
    """    
    room = serializers.SerializerMethodField()
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Room").objects.all(),
        source="room",
        write_only=True,
        required=True
    )
    sender = serializers.SerializerMethodField()
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="sender", 
        write_only=True,
        required=True,
    )
    read_receipts = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    def validate_content(self, value):
        """
            Sanitize message content to prevent XSS attacks.

            Allows safe HTML tags (bold, italic, links, lists) while stripping
            potentially malicious content.
        """        
        ALLOWED_TAGS = ['b', 'i', 'strong', 'em', 'a', 'span', 'p', 'ul', 'ol', 'li', 'br']
        ALLOWED_ATTRS = {'a': ['href', 'title', 'target'], '*': ['class', 'id']}

        # Clean HTML to allow only certain tags/attributes
        clean_value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        return clean_value
    
    def get_sender(self, obj):
        """Get the user who sent the message."""
        return get_serializer("UserSerializer")(obj.sender).data


    def get_room(self, instance):
        """Get minimal room information (ID only)."""

        return {"id": str(instance.room.id)}
    

    def get_read_receipts(self, instance):
        """
            Get all read receipts for this message.

            Dynamically resolves the reverse relation accessor name to support
            custom ReadReceipt models.
        """        
        accessor = get_model("ReadReceipt")._meta.get_field("message").remote_field.get_accessor_name()
        qs = getattr(instance, accessor).all()

        return get_serializer("ReadReceiptSerializer")(qs, many=True).data

    def get_reactions(self, instance):
        """
            Get all reactions to this message.

            Dynamically resolves the reverse relation accessor name to support
            custom Reaction models.
        """        
        accessor = get_model("Reaction")._meta.get_field("message").remote_field.get_accessor_name()
        qs = getattr(instance, accessor).all()

        return get_serializer("ReactionSerializer")(qs, many=True).data

    def get_attachments(self, instance):
        """
            Get all media attachments for this message.

            Dynamically resolves the reverse relation accessor name to support
            custom MessageMediaAsset models.
        """        
        accessor = get_model("MessageMediaAsset")._meta.get_field("message").remote_field.get_accessor_name()
        qs = getattr(instance, accessor).all()

        return get_serializer("MessageMediaAssetSerializer")(qs, many=True).data
    
class ChatNotificationSerializerMixin(serializers.Serializer):
    """
        Mixin for ChatNotification serialization.

        Provides:
            - message: Full message data (read-only nested)
            - message_id: Message ID for creating notifications (write-only)
    """

    message = serializers.SerializerMethodField()
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message",
        write_only=True,
        required=True,
    )

    def get_message(self, instance):
        """Get the message associated with this notification."""
        return get_serializer("MessageSerializer")(instance.message).data
    