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
    class Meta:
        model = User
        fields = ["id","username", "email", "first_name", "last_name"]



class RoomPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomProperty
        fields = ['preferences']


class OneToOneChatListSerializer(
        OneToOneChatListSerializerMixin, 
        serializers.ModelSerializer
    ):
    class Meta:
        model = OneToOneChat
        exclude = ["participants", "property"]



class GroupChatListSerializer(
        GroupChatListSerializerMixin, 
        serializers.ModelSerializer
    ):
    class Meta:
        model = GroupChat
        exclude = ['participants', 'admins', 'property']


class ChannelListSerializer(
        ChannelListSerializerMixin, 
        serializers.ModelSerializer
    ):
    class Meta:
        model = Channel
        exclude = ['subscribers', 'moderators', 'property']



class RoomListPolymorphicSerializer(PolymorphicSerializer):
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
    class Meta:
        model = OneToOneChat
        exclude = ['last_message']

class GroupChatSerializer(
        GroupChatSerializerMixin,
        serializers.ModelSerializer
    ):
    admins = get_serializer("UserSerializer")(read_only=True, many=True)
    class Meta:
        model = GroupChat
        exclude = ['last_message']

class ChannelSerializer(
        ChannelSerializerMixin,
        serializers.ModelSerializer
    ):
    moderators = get_serializer("UserSerializer")(read_only=True, many=True)
    class Meta:
        model = Channel
        exclude = ['last_message']


class RoomPolymorphicSerializer(PolymorphicSerializer):
    resource_type_field_name = "type"
    model_serializer_mapping = {
        get_model("OneToOneChat"): get_serializer("OneToOneChatSerializer"),
        get_model("GroupChat"): get_serializer("GroupChatSerializer"),
        get_model("Channel"): get_serializer("ChannelSerializer"),
    }

    
    def is_valid(self, *args, **kwargs):
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
    class Meta:
        model = ReadReceipt
        fields = ['reader_id', 'message_id', 'reader', 'read_at']


class ReactionSerializer(
        ReactionSerializerMixin,
        serializers.ModelSerializer
    ):
    class Meta:
        model = Reaction
        fields = "__all__"
        validators = [] # let signals take care of unique constraints



class MessageSerializer(
        MessageSerializerMixin,
        serializers.ModelSerializer
    ):
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
        return list(
            instance.delivered_to.values_list("username", flat=True)
        ) # returns [username1, username2] 
    
    def update(self, instance, validated_data):
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
    class Meta:
        model = ChatNotification
        exclude = ["recipients"]

    
class MessageMediaAssetSerializer(
        MessageMediaAssetSerializerMixin,
        serializers.ModelSerializer
    ):
    class Meta:
        model = MessageMediaAsset
        exclude = ['message']
