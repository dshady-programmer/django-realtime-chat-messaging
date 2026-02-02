from .models import (
        Channel, ChatNotification, GroupChat, 
        OneToOneChat, Message, MessageMediaAsset,
        ReadReceipt, Reaction, RoomProperty
    )
from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer
from django_rest_framework_recursive.fields import RecursiveField
import bleach
from realtime_chat_messaging.utils.loader import get_model, get_serializer
from django.contrib.auth import get_user_model
User = get_user_model()


RESOURCE_TYPES = ["OneToOne", "Group", "Channel"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id","username", "email", "first_name", "last_name"]


class RoomPropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomProperty
        fields = ['preferences']

class OneToOneChatListSerializer(serializers.ModelSerializer):
    peer = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    class Meta:
        model = OneToOneChat
        exclude = ["participants", "property"]
    
    def get_peer(self, instance):
        user = self.context.get('user')
        if not user:
            raise Exception("user context is required")
        peers = instance.participants.exclude(id=user.id)
        return get_serializer("UserSerializer")(peers.first()).data

    def get_last_message(self, instance):
        return get_serializer("MessageSerializer")(instance.last_message).data


class GroupChatListSerializer(serializers.ModelSerializer):
    creator = get_serializer("UserSerializer")(read_only=True)
    last_message = serializers.SerializerMethodField()
    class Meta:
        model = GroupChat
        exclude = ['participants', 'admins', 'property']

    def get_last_message(self, instance):
        return get_serializer("MessageSerializer")(instance.last_message).data

class ChannelListSerializer(serializers.ModelSerializer):
    creator = get_serializer("UserSerializer")(read_only=True)
    last_message = serializers.SerializerMethodField()
    class Meta:
        model = Channel
        exclude = ['subscribers', 'moderators', 'property']
    
    def get_last_message(self, instance):
        return get_serializer("MessageSerializer")(instance.last_message).data


class RoomListPolymorphicSerializer(PolymorphicSerializer):
    resource_type_field_name = "type"
    model_serializer_mapping = {
        get_model("OneToOneChat"): get_serializer("OneToOneChatListSerializer"),
        get_model("GroupChat"): get_serializer("GroupChatListSerializer"),
        get_model("Channel"): get_serializer("ChannelListSerializer"),
    }



class OneToOneChatSerializer(serializers.ModelSerializer):
    participants = get_serializer("UserSerializer")(many=True, read_only=True)
    property = get_serializer("RoomPropertySerializer")()

    class Meta:
        model = OneToOneChat
        exclude = ['last_message']

class GroupChatSerializer(serializers.ModelSerializer):
    creator = get_serializer("UserSerializer")(read_only=True)
    participants = get_serializer("UserSerializer")(read_only=True, many=True)
    admins = get_serializer("UserSerializer")(read_only=True, many=True)
    property = get_serializer("RoomPropertySerializer")()
    class Meta:
        model = GroupChat
        exclude = ['last_message']

class ChannelSerializer(serializers.ModelSerializer):
    creator = get_serializer("UserSerializer")(read_only=True)
    subscribers = get_serializer("UserSerializer")(read_only=True, many=True)
    moderators = get_serializer("UserSerializer")(read_only=True, many=True)
    property = get_serializer("RoomPropertySerializer")()
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

 

    def create(self, _):
        user = self.context.get("user")
        # print('self.initial', self.initial_data)
        # resource_type = eval(self.initial_data.get("type")) # unsafe  
        onetoonechat = get_model("OneToOneChat")
        groupchat = get_model("GroupChat")
        channel = get_model("Channel")
        mapping = {
            "OneToOneChat": onetoonechat,
            "GroupChat": groupchat,
            "Channel": channel,
        }
        resource_type_str = self.initial_data.get("type")
        resource_type = mapping.get(resource_type_str)
        if not resource_type:
            raise serializers.ValidationError("Invalid type")

        extra_fields = self.initial_data.pop('extra_fields', {})

        room_property = extra_fields.get('property')

        if room_property:
            if not isinstance(room_property, dict):
                raise serializers.ValidationError("Room property must be a python dictionary/javascript object")
            preferences = room_property.get('preferences')
            if preferences and not isinstance(preferences, dict):
                raise serializers.ValidationError("preferences must be a python dictionary/javascript object")
        else:
            extra_fields['property'] = {}
            
        data = {
            **self.initial_data,
            **extra_fields
        }
        # print('data', data)

        serializer_class = self.model_serializer_mapping.get(resource_type).__class__
        if not serializer_class:
            raise serializers.ValidationError("Invalid type")
       
        serializer = serializer_class(
            data=data,
            context=self.context,
        )
        serializer.is_valid(raise_exception=True)
        if resource_type in [groupchat, channel]:
            instance = serializer.save(creator=user)
        else:
            instance = serializer.save()
        
        try:
          
            if resource_type == onetoonechat:
                participants = data.get("participants")
                if not isinstance(participants, list):
                    participants = []
                participants = User.objects.filter(id__in=participants)
                instance.participants.set([*participants, user])
            elif resource_type == groupchat:
                participants = data.get("participants")
                if not isinstance(participants, list):
                    participants = []
                participants = User.objects.filter(id__in=participants)
                instance.participants.add(*participants)
    
            else:
                subscribers = data.get("subscribers")
                if not isinstance(subscribers, list):
                    subscribers = []
                subscribers = User.objects.filter(id__in=subscribers)
                instance.subscribers.add(*subscribers)
        except Exception as e:
            instance.delete()
            raise serializers.ValidationError(e)
        else:
            return instance

class ReadReceiptSerializer(serializers.ModelSerializer):
    reader = get_serializer("UserSerializer")(read_only=True)
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
    class Meta:
        model = ReadReceipt
        fields = ['reader_id', 'message_id', 'reader', 'read_at']


class ReactionSerializer(serializers.ModelSerializer):
    user = get_serializer("UserSerializer")(read_only=True)
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
    class Meta:
        model = Reaction
        fields = "__all__"
        validators = [] # let signals take care of unique constraints
    



class MessageMediaAssetSerializer(serializers.ModelSerializer):
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message", 
        write_only=True,
        required=True,
    )
    class Meta:
        model = MessageMediaAsset
        exclude = ['message']


class MessageSerializer(serializers.ModelSerializer):
    room = serializers.SerializerMethodField(read_only=True)
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Room").objects.all(),
        source="room",
        write_only=True,
        required=True
    )
    sender = get_serializer("UserSerializer")(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="sender", 
        write_only=True,
        required=True,
    )
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
    read_receipts = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    delivered_to = serializers.SerializerMethodField()
    class Meta:
        model = Message
        fields = "__all__"
        depth = 2

    def validate_content(self, value):
        ALLOWED_TAGS = ['b', 'i', 'strong', 'em', 'a', 'span', 'p', 'ul', 'ol', 'li', 'br']
        ALLOWED_ATTRS = {'a': ['href', 'title', 'target'], '*': ['class', 'id']}

        # Clean HTML to allow only certain tags/attributes
        clean_value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        return clean_value
    
    def get_room(self, instance):
        return {"id": str(instance.room.id)}
    
    def get_delivered_to(self, instance):
        return list(
            instance.delivered_to.values_list("username", flat=True)
        ) # returns [username1, username2]

    def get_read_receipts(self, instance):
        accessor = get_model("ReadReceipt")._meta.get_field("message").remote_field.get_accessor_name()
        qs = getattr(instance, accessor).all()

        return get_serializer("ReadReceiptSerializer")(qs, many=True).data

    def get_reactions(self, instance):
        accessor = get_model("Reaction")._meta.get_field("message").remote_field.get_accessor_name()
        qs = getattr(instance, accessor).all()

        return get_serializer("ReactionSerializer")(qs, many=True).data

    def get_attachments(self, instance):
        accessor = get_model("MessageMediaAsset")._meta.get_field("message").remote_field.get_accessor_name()
        qs = getattr(instance, accessor).all()

        return get_serializer("MessageMediaAssetSerializer")(qs, many=True).data
    
class ChatNotificationSerializer(serializers.ModelSerializer):
    message = get_serializer("MessageSerializer")(read_only=True)
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message",
        write_only=True,
        required=True,
    )

    class Meta:
        model = ChatNotification
        exclude = ["recipients"]

    