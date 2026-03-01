"""
Concrete serializers for the real-time chat messaging system.

These serializers combine the mixin classes with Django REST Framework's
ModelSerializer to provide complete serialization for all chat models.

All serializers are swappable via the SERIALIZERS setting, allowing custom
implementations without modifying package code.

Key Features:
    - Polymorphic serialization for Room types (OneToOneChat, GroupChat, Channel)
    - Recursive serialization for message replies and forwards
    - XSS protection via content validation
    - Write-only fields for efficient creation
    - Read-only nested relationships
"""



from .models import (
        Channel, ChatNotification, GroupChat, 
        OneToOneChat, Message, MessageMediaAsset,
        ReadReceipt, Reaction, RoomProperty
    )

from .mixins.serializers import (
    MessageMediaAssetSerializerMixin,
    OneToOneChatListSerializerMixin, 
    GroupChatListSerializerMixin, 
    ChannelListSerializerMixin, 
    OneToOneChatSerializerMixin, 
    GroupChatSerializerMixin, 
    ChannelSerializerMixin, 
    ChatNotificationSerializerMixin,
    ReactionSerializerMixin,
    ReadReceiptSerializerMixin,
    MessageSerializerMixin
)

from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer
from django_rest_framework_recursive.fields import RecursiveField
from realtime_chat_messaging.utils.loader import get_model, get_serializer
from django.contrib.auth import get_user_model
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
        Basic user serializer for nested user representations.

        Override in settings to include additional user fields or customize output.
    """    
    class Meta:
        model = User
        fields = ["id","username", "email", "first_name", "last_name"]



class RoomPropertySerializer(serializers.ModelSerializer):
    """
        Serializer for room preferences and settings.

        Handles the preferences JSONField where custom room configuration is stored.
    """    
    class Meta:
        model = RoomProperty
        fields = ['preferences']


class OneToOneChatListSerializer(
        OneToOneChatListSerializerMixin, 
        serializers.ModelSerializer
    ):
    """
        List serializer for OneToOneChat rooms.

        Provides peer user and last message for efficient room listings.
    """

    class Meta:
        model = OneToOneChat
        exclude = ["participants", "property"]



class GroupChatListSerializer(
        GroupChatListSerializerMixin, 
        serializers.ModelSerializer
    ):
    """
        List serializer for GroupChat rooms.

        Provides creator and last message for efficient room listings.
        Excludes full participant/admin lists and property to reduce payload size.
    """    
    class Meta:
        model = GroupChat
        exclude = ['participants', 'admins', 'property']


class ChannelListSerializer(
        ChannelListSerializerMixin, 
        serializers.ModelSerializer
    ):
    """
        List serializer for Channel rooms.

        Provides creator and last message for efficient room listings.
        Excludes full subscriber/moderator lists and property to reduce payload size.
    """    
    class Meta:
        model = Channel
        exclude = ['subscribers', 'moderators', 'property']



class RoomListPolymorphicSerializer(PolymorphicSerializer):
    """
        Polymorphic serializer for listing all room types in a single query.

        Maps each room type to its corresponding list serializer. The 'type' field
        indicates the concrete room type (OneToOneChat, GroupChat, or Channel).

        Used by room.list event handler to efficiently return all user rooms.
    """    
    resource_type_field_name = "type"
    model_serializer_mapping = {
        get_model("OneToOneChat"): get_serializer("OneToOneChatListSerializer"),
        get_model("GroupChat"): get_serializer("GroupChatListSerializer"),
        get_model("Channel"): get_serializer("ChannelListSerializer"),
    }



class OneToOneChatSerializer(
        OneToOneChatSerializerMixin, 
        serializers.ModelSerializer
    ):
    """
        Detail serializer for OneToOneChat rooms.

        Includes full participants list and room property.
        Used by room.info and room.create events.
    """    
    class Meta:
        model = OneToOneChat
        exclude = ['last_message']

class GroupChatSerializer(
        GroupChatSerializerMixin,
        serializers.ModelSerializer
    ):
    """
        Detail serializer for GroupChat rooms.

        Includes full participants list, admins, and room property.
        Used by room.info and room.create events.
    """    
    admins = get_serializer("UserSerializer")(read_only=True, many=True)
    class Meta:
        model = GroupChat
        exclude = ['last_message']

class ChannelSerializer(
        ChannelSerializerMixin,
        serializers.ModelSerializer
    ):
    """
        Detail serializer for Channel rooms.

        Includes full subscribers list, moderators, and room property.
        Used by room.info and room.create events.
    """    
    moderators = get_serializer("UserSerializer")(read_only=True, many=True)
    class Meta:
        model = Channel
        exclude = ['last_message']


class RoomPolymorphicSerializer(PolymorphicSerializer):
    """
        Polymorphic serializer for creating and serializing room details.

        Handles room creation logic including:
        - Type validation and mapping
        - Creator assignment for GroupChat/Channel
        - Participant/subscriber addition
        - Room property creation and update
        - Automatic rollback on failure

        The 'type' field accepts either standard names (OneToOneChat, GroupChat,
        Channel) or custom model names if using swappable models.

        Validation:
            - Ensures valid room type
            - Validates property structure (must be dict)
            - Validates preferences structure (must be dict)
            - Prevents room creation if property doesn't get created in the creation chain

        Note:
            This serializer performs complex creation logic with automatic cleanup
            on failure. Override with caution.
    """


    resource_type_field_name = "type"
    model_serializer_mapping = {
        get_model("OneToOneChat"): get_serializer("OneToOneChatSerializer"),
        get_model("GroupChat"): get_serializer("GroupChatSerializer"),
        get_model("Channel"): get_serializer("ChannelSerializer"),
    }

    
    def is_valid(self, *args, **kwargs):
        """
            Validate and resolve the room type.

            Maps the 'type' field from client to the actual model class,
            supporting both standard and custom model names.
        """        
        self.loadedonetoonechat = get_model("OneToOneChat")
        self.loadedgroupchat = get_model("GroupChat")
        self.loadedchannel = get_model("Channel")

        mapping = {
            "OneToOneChat": self.loadedonetoonechat,
            "GroupChat": self.loadedgroupchat,
            "Channel": self.loadedchannel,
            self.loadedonetoonechat.__name__: self.loadedonetoonechat,
            self.loadedgroupchat.__name__: self.loadedgroupchat,
            self.loadedchannel.__name__: self.loadedchannel,
        }
        
        resource_type_str = self.initial_data.get("type")
        self.resource_type = mapping.get(resource_type_str)
        if not self.resource_type:
            raise serializers.ValidationError("Invalid resource type")
        self.initial_data["type"] = self.resource_type.__name__
        return super().is_valid(*args, **kwargs)
    
    def create(self, _):

        """
            Create a new room with property and members.

            Process:
            1. Extract and validate extra_fields and property
            2. Create room instance with appropriate creator
            3. Update room property with provided preferences
            4. Add participants/subscribers (including creator)
            5. Rollback on any failure

            Returns:
                Room instance (OneToOneChat, GroupChat, or Channel)

            Raises:
                ValidationError: If property structure is invalid or creation fails

            Works on the principle of ALL OR NOTHING
        """
        user = self.context.get("user")

        extra_fields = self.initial_data.pop('extra_fields', {})
        room_property = extra_fields.pop('property', {})

        if room_property:
            if not isinstance(room_property, dict):
                raise serializers.ValidationError("Room property must be a python dictionary/javascript object")
            preferences = room_property.get('preferences')
            if preferences and not isinstance(preferences, dict):
                raise serializers.ValidationError("preferences must be a python dictionary/javascript object")
        
        data = {
            **self.initial_data,
            **extra_fields
        }
        
        serializer_class = self.model_serializer_mapping.get(self.resource_type).__class__
        if not serializer_class:
            raise serializers.ValidationError("Invalid type")
       
        serializer = serializer_class(
            data=data,
            context=self.context,
        )
        serializer.is_valid(raise_exception=True)
        if self.resource_type in [self.loadedgroupchat, self.loadedchannel]:
            instance = serializer.save(creator=user)
        else:
            instance = serializer.save()
        if instance.property is None:
            raise serializers.ValidationError("Room Property can't be null")
        room_property_serializer = get_serializer("RoomPropertySerializer")(instance=instance.property, data=room_property, partial=True)
        room_property_serializer.is_valid(raise_exception=True)
        room_property_serializer.save()
        try:
            if self.resource_type == self.loadedonetoonechat:
                participants = data.get("participants")
                if not isinstance(participants, list):
                    participants = []
                participants = User.objects.filter(id__in=participants)
                instance.participants.set([*participants, user])
            elif self.resource_type == self.loadedgroupchat:
                participants = data.get("participants")
                if not isinstance(participants, list):
                    participants = []
                participants = User.objects.filter(id__in=participants)
                instance.participants.add(*participants, user)
    
            else:
                subscribers = data.get("subscribers")
                if not isinstance(subscribers, list):
                    subscribers = []
                subscribers = User.objects.filter(id__in=subscribers)
                instance.subscribers.add(*subscribers, user)
        except Exception as e:
            instance.delete()
            raise serializers.ValidationError(e)
        else:
            return instance



class ReadReceiptSerializer(
        ReadReceiptSerializerMixin,
        serializers.ModelSerializer
    ):

    """
        Serializer for read receipts.

        Tracks when users read messages. Combines reader info with timestamps.
    """    
    class Meta:
        model = ReadReceipt
        fields = ['reader_id', 'message_id', 'reader', 'read_at']


class ReactionSerializer(
        ReactionSerializerMixin,
        serializers.ModelSerializer
    ):
    """
        Serializer for message reactions.

        Disables DRF unique constraint validators to let signals handle
        the one-reaction-per-user-per-message constraint.
    """    
    class Meta:
        model = Reaction
        fields = "__all__"
        validators = [] # let signals take care of unique constraints



class MessageSerializer(
        MessageSerializerMixin,
        serializers.ModelSerializer
    ):

    """
        Serializer for messages with recursive nesting.

        Features:
        - Recursive serialization for replies (parent_message)
        - Recursive serialization for forwards (forwarded_from)
        - Read receipts, reactions, and attachments
        - XSS-safe content validation
        - Prevents updates to immutable fields

        Update Restrictions:
            The update() method prevents modification of:
            - sender, room, created_at, updated_at
            - is_deleted (use message.modify delete action)
            - forwarded_from, is_forwarded, parent_message (immutable)
            - Deleted messages cannot be updated

        Note:
            Only content field can be updated, triggering is_edited flag.
    """    
    parent_message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="parent_message",
        write_only=True,
        required=False
    )
    forwarded_from_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="forwarded_from",
        write_only=True,
        required=False
    )
    parent_message = RecursiveField(allow_null=True, read_only=True)
    forwarded_from = RecursiveField(allow_null=True, read_only=True)
    delivered_to = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = "__all__"
        depth = 2

    def get_delivered_to(self, instance):
        """Get list of usernames who have received the message."""
        return list(
            instance.delivered_to.values_list("username", flat=True)
        ) # returns [username1, username2] 
    
    def update(self, instance, validated_data):
        """
            Update message content only.

            Prevents modification of immutable fields and deleted messages.
            Requires content field to be provided.
        """        
        validated_data.pop("sender", None) # sender can't be updated
        validated_data.pop("room", None) # room can't be updated
        validated_data.pop("created_at", None) # created_at can't be updated
        validated_data.pop("updated_at", None) # updated_at is auto updated
        validated_data.pop("is_deleted", None) # is_deleted should be updated through another method
        validated_data.pop("forwarded_from", None) # forwarded_from can't be updated
        validated_data.pop("is_forwarded", None) # is_forwarded can't be updated aloong with forwarded_from
        validated_data.pop("parent_message", None) # parent_message can't be updated
        
        content = validated_data.get("content")
        # print("validated data in update method", validated_data)

        if not content:
            raise serializers.ValidationError("Content should be provided for update action")
        if instance.is_deleted:
            raise serializers.ValidationError("Deleted messages can't be updated")
        return super().update(instance, validated_data)


class ChatNotificationSerializer(
        ChatNotificationSerializerMixin,
        serializers.ModelSerializer
    ):
    """
        Serializer for chat notifications.

        Excludes recipients list from serialization (managed internally).
        Used for push notification integration.
    """    
    class Meta:
        model = ChatNotification
        exclude = ["recipients"]

    
class MessageMediaAssetSerializer(
        MessageMediaAssetSerializerMixin,
        serializers.ModelSerializer
    ):
    """
        Serializer for message media attachments.

        Excludes message field from serialization (provided via write-only
        message_id field in the mixin).
    """    
    class Meta:
        model = MessageMediaAsset
        exclude = ['message']
