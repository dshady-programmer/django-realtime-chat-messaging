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
    
    class Meta:
        model = CustomMessage
        fields = ['id', 'content', 'room_id', 'sender_id', 'sender_username', 'priority', 'metadata', 'created_at']


class CustomGroupChatSerializer(serializers.ModelSerializer):
    """Custom group chat serializer"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    tags = serializers.JSONField(default=list)
    admins = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    class Meta:
        model = CustomGroupChat
        fields = ['id', 'name', 'description', 'participants', 'creator_name', 'max_participants', 'tags', "join_approval_required", "group_locked"]

    def get_admins(self, obj):  
        return [admin.username for admin in obj.admins.all()]
    
    def get_participants(self, obj):
        return [participant.username for participant in obj.partcipants.all()]


class CustomChannelSerializer(serializers.ModelSerializer):
    """Custom channel serializer"""
    creator_name = serializers.CharField(source='creator.username', read_only=True)
    preferences = serializers.JSONField(default=dict)
    moderators = serializers.SerializerMethodField()
    subscribers = serializers.SerializerMethodField()


    
    class Meta:
        model = CustomChannel
        fields = ['id', 'name', 'description', 'creator_name', 'subscribers', 'max_subscribers', 'preferences']
    
    def get_moderators(self, obj):
        return [moderator.username for moderator in obj.moderators.all()]
    
    def get_subscribers(self, obj):
        return [participant.username for participant in obj.partcipants.all()]

class CustomRoomPropertySerializer(serializers.ModelSerializer):
    """Custom room property serializer"""
    class Meta:
        model = CustomRoomProperty
        fields = ['id', 'preferences', 'archived']
    


    


