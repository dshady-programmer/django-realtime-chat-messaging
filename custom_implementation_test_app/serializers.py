from rest_framework import serializers
from .models import CustomChannel, CustomMessage, CustomGroupChat, CustomRoomProperty
from realtime_chat_messaging.utils.loader import get_model
from django.contrib.auth import get_user_model
User = get_user_model()
# from django.core.exceptions import ValidationError

# ==================== CUSTOM SERIALIZER IMPLEMENTATIONS ====================

class CustomMessageSerializer(serializers.ModelSerializer):
    """Custom message serializer"""
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    priority = serializers.CharField(default='normal')
    room_id = serializers.PrimaryKeyRelatedField(
        queryset=get_model("Room").objects.all(),
        source="room",
        write_only=True,
        required=True
    )
    sender_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source="sender", 
        write_only=True,
        required=True,
    )
    room = serializers.SerializerMethodField()
    class Meta:
        model = CustomMessage
        fields = ['id', 'content','room', 'room_id', 'sender_id', 'sender_username', 'priority', 'metadata', 'created_at']

    def get_room(self, obj):
        return {
            "id": str(obj.room.id)
        }
class CustomGroupChatSerializer(serializers.ModelSerializer):
    """Custom group chat serializer"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    tags = serializers.JSONField(default=list)
    admins = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    class Meta:
        model = CustomGroupChat
        fields = ['id', 'name', 'description', 'admins', 'participants', 'creator_name', 'max_participants', 'tags', "join_approval_required", "group_locked"]

    def get_admins(self, obj):  
        return [{"id": admin.id, "username": admin.username} for admin in obj.admins.all()]
    
    def get_participants(self, obj):
        return [{"id": participant.id, "username": participant.username} for participant in obj.participants.all()]


class CustomGroupChatListSerializer(serializers.ModelSerializer):
    creator = serializers.CharField(source='creator.username', read_only=True)
    last_message = serializers.SerializerMethodField()
    class Meta:
        model = CustomGroupChat
        exclude = ['participants', 'admins', 'property']

    def get_last_message(self, instance):
        return CustomMessageSerializer(instance.last_message).data



class CustomChannelSerializer(serializers.ModelSerializer):
    """Custom channel serializer"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    preferences = serializers.JSONField(default=dict)
    moderators = serializers.SerializerMethodField()
    subscribers = serializers.SerializerMethodField()


    
    class Meta:
        model = CustomChannel
        fields = ['id', 'name', 'description', 'creator_name', 'moderators', 'subscribers', 'max_subscribers', 'preferences']
    
    def get_moderators(self, obj):
        return [{"id": moderator.id, "username": moderator.username} for moderator in obj.moderators.all()]
    
    def get_subscribers(self, obj):
        return [{"id": subscriber.id, "username": subscriber.username} for subscriber in obj.subscribers.all()]

class CustomRoomPropertySerializer(serializers.ModelSerializer):
    """Custom room property serializer"""
    class Meta:
        model = CustomRoomProperty
        fields = ['id', 'preferences', 'archived']
    


    


