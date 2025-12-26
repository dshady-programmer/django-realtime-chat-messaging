from .models import (
        Channel, ChatNotification, GroupChat, 
        OneToOneChat, Message, MessageMediaAsset,
        ReadReceipt, Reaction, User, Room
    )

from rest_framework import serializers
from rest_polymorphic.serializers import PolymorphicSerializer
from django_rest_framework_recursive.fields import RecursiveField
import bleach


RESOURCE_TYPES = ["OneToOne", "Group", "Channel"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id","username", "email", "first_name", "last_name"]


class OneToOneChatListSerializer(serializers.ModelSerializer):
    peer = serializers.SerializerMethodField(read_only=True)
    last_message = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = OneToOneChat
        exclude = ["participants", "preferences"]
    
    def get_peer(self, instance):
        user = self.context.get('user')
        if not user:
            raise Exception("user context is required")
        peers = instance.participants.exclude(id=user.id)
        return UserSerializer(peers.first()).data

    def get_last_message(self, instance):
        return MessageSerializer(instance.last_message).data



class GroupChatListSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    last_message = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = GroupChat
        exclude = ['participants', 'admins', 'preferences']

    def get_last_message(self, instance):
        return MessageSerializer(instance.last_message).data

class ChannelListSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    last_message = serializers.SerializerMethodField(read_only=True)
    class Meta:
        model = Channel
        exclude = ['subscribers', 'moderators', 'preferences']
    
    def get_last_message(self, instance):
        return MessageSerializer(instance.last_message).data


class RoomListPolymorphicSerializer(PolymorphicSerializer):
    resource_type_field_name = "type"
    model_serializer_mapping = {
        OneToOneChat: OneToOneChatListSerializer,
        GroupChat: GroupChatListSerializer,
        Channel: ChannelListSerializer,
    }



class OneToOneChatSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    class Meta:
        model = OneToOneChat
        exclude = ['last_message']

class GroupChatSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    participants = UserSerializer(read_only=True, many=True)
    admins = UserSerializer(read_only=True, many=True)
    class Meta:
        model = GroupChat
        exclude = ['last_message']

class ChannelSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    subscribers = UserSerializer(read_only=True, many=True)
    moderators = UserSerializer(read_only=True, many=True)
    class Meta:
        model = Channel
        exclude = ['last_message']


class RoomPolymorphicSerializer(PolymorphicSerializer):
    resource_type_field_name = "type"
    model_serializer_mapping = {
        OneToOneChat: OneToOneChatSerializer,
        GroupChat: GroupChatSerializer,
        Channel: ChannelSerializer,
    }

 

    def create(self, _):
        user = self.context.get("user")
        # print('self.initial', self.initial_data)
        # resource_type = eval(self.initial_data.get("type")) # unsafe  
        mapping = {
            "OneToOneChat": OneToOneChat,
            "GroupChat": GroupChat,
            "Channel": Channel,
        }
        resource_type_str = self.initial_data.get("type")
        resource_type = mapping.get(resource_type_str)
        if not resource_type:
            raise serializers.ValidationError("Invalid type")

        extra_fields = self.initial_data.pop('extra_fields') if 'extra_fields' in self.initial_data else {}
        preferences = extra_fields.get('preferences')
        if preferences and not isinstance(preferences, dict):
            raise serializer.ValidationError("preferences must be a python dictionary/javascript object")
            
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
        if resource_type in [GroupChat, Channel]:
            instance = serializer.save(creator=user)
        else:
            instance = serializer.save()
        
        try:
            if resource_type == OneToOneChat:
                participants = data.get("participants")
                participants = User.objects.filter(id__in=participants)
                instance.participants.set([*participants,user ])
            elif resource_type == GroupChat:
                participants = data.get("participants")
                participants = User.objects.filter(id__in=participants)
                instance.participants.add(*participants)
    
            else:
                subscribers = data.get("subscribers")
                if not subscribers:
                    raise Exception("Channel must have at least one subscriber")
                subscribers = User.objects.filter(id__in=subscribers)
                instance.subscribers.add(*subscribers)
                
        except Exception as e:
            instance.delete()
            raise serializers.ValidationError(e)
        else:
            return instance

class ReadReceiptSerializer(serializers.ModelSerializer):
    reader = UserSerializer(read_only=True)
    reader_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="reader", 
        write_only=True,
        required=True,
    )
    class Meta:
        model = ReadReceipt
        fields = ['reader_id', 'reader', 'read_at']


class ReactionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="user", 
        write_only=True,
        required=True,
    )
    message = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(), required=True,
        write_only=True
        )
    class Meta:
        model = Reaction
        fields = "__all__"
        validators = []
    



class MessageMediaAssetSerializer(serializers.ModelSerializer):
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(),
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
        queryset=Room.objects.all(),
        source="room",
        write_only=True,
        required=True
    )
    sender = UserSerializer(read_only=True)
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="sender", 
        write_only=True,
        required=True,
    )
    parent_message_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(),
        source="parent_message",
        write_only=True,
        required=False
    )
    forwarded_from_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(),
        source="forwarded_from",
        write_only=True,
        required=False
    )
    parent_message = RecursiveField(allow_null=True, read_only=True)
    forwarded_from = RecursiveField(allow_null=True, read_only=True)
    read_receipts = ReadReceiptSerializer(read_only=True, many=True)
    reactions = ReactionSerializer(read_only=True, many=True)
    attachments = MessageMediaAssetSerializer(read_only=True, many=True)
    class Meta:
        model = Message
        fields = "__all__"
        depth = 2

    def validate_content(self, value):
        ALLOWED_TAGS = ['b', 'i', 'strong', 'em', 'a']
        ALLOWED_ATTRS = {'a': ['href', 'title', 'target']}

        # Clean HTML to allow only certain tags/attributes
        clean_value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        return clean_value
    
    def get_room(self, instance):
        return {"id": str(instance.room.id)}

    
class ChatNotificationSerializer(serializers.ModelSerializer):
    message = MessageSerializer(read_only=True)
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(),
        source="message",
        write_only=True,
        required=True,
    )

    class Meta:
        model = ChatNotification
        exclude = ["recipients"]

    