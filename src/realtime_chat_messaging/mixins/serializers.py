
from rest_framework import serializers
import bleach
from realtime_chat_messaging.utils.loader import get_model, get_serializer
from django.contrib.auth import get_user_model
User = get_user_model()




class OneToOneChatListSerializerMixin(serializers.Serializer):
    peer = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    def get_peer(self, instance):
        user = self.context.get('user')
        if not user:
            raise Exception("user context is required")
        peers = instance.participants.exclude(id=user.id)
        return get_serializer("UserSerializer")(peers.first()).data

    def get_last_message(self, instance):
        return get_serializer("MessageSerializer")(instance.last_message).data


class GroupChatListSerializerMixin(serializers.Serializer):
    creator = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    def get_last_message(self, instance):
        return get_serializer("MessageSerializer")(instance.last_message).data

    def get_creator(self, obj):
        return get_serializer("UserSerializer")(obj.creator).data

class ChannelListSerializerMixin(serializers.Serializer):
    creator = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    def get_last_message(self, instance):
        return get_serializer("MessageSerializer")(instance.last_message).data

    def get_creator(self, obj):
        return get_serializer("UserSerializer")(obj.creator).data


class OneToOneChatSerializerMixin(serializers.Serializer):
    participants = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()

    def get_participants(self, obj):
        return get_serializer("UserSerializer")(obj.participants.all(), many=True).data

    def get_property(self, obj):
        if hasattr(obj, 'property') and obj.property:
            return get_serializer("RoomPropertySerializer")(obj.property).data
        return None

class GroupChatSerializerMixin(serializers.Serializer):
    creator = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()

    def get_creator(self, obj):
        return get_serializer("UserSerializer")(obj.creator).data

    def get_participants(self, obj):
        return get_serializer("UserSerializer")(obj.participants.all(), many=True).data

    def get_property(self, obj):
        if hasattr(obj, 'property') and obj.property:
            return get_serializer("RoomPropertySerializer")(obj.property).data
        return None


class ChannelSerializerMixin(serializers.Serializer):
    creator = serializers.SerializerMethodField()
    subscribers = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()

    def get_creator(self, obj):
        return get_serializer("UserSerializer")(obj.creator).data

    def get_subscribers(self, obj):
        return get_serializer("UserSerializer")(obj.subscribers.all(), many=True).data

    def get_property(self, obj):
        if hasattr(obj, 'property') and obj.property:
            return get_serializer("RoomPropertySerializer")(obj.property).data
        return None


class ReadReceiptSerializerMixin(serializers.Serializer):
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
        return get_serializer("UserSerializer")(obj.reader).data

class ReactionSerializerMixin(serializers.Serializer):
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
        return get_serializer("UserSerializer")(obj.user).data


class MessageMediaAssetSerializerMixin(serializers.Serializer):
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message", 
        write_only=True,
        required=True,
    )



class MessageSerializerMixin(serializers.Serializer):
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
        ALLOWED_TAGS = ['b', 'i', 'strong', 'em', 'a', 'span', 'p', 'ul', 'ol', 'li', 'br']
        ALLOWED_ATTRS = {'a': ['href', 'title', 'target'], '*': ['class', 'id']}

        # Clean HTML to allow only certain tags/attributes
        clean_value = bleach.clean(value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        return clean_value
    
    def get_sender(self, obj):
        return get_serializer("UserSerializer")(obj.sender).data


    def get_room(self, instance):
        return {"id": str(instance.room.id)}
    

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
    
class ChatNotificationSerializerMixin(serializers.Serializer):
    message = serializers.SerializerMethodField()
    message_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Message").objects.all(),
        source="message",
        write_only=True,
        required=True,
    )

    def get_message(self, instance):
        return get_serializer("MessageSerializer")(instance.message).data
    