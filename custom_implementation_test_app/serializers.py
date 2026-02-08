from rest_framework import serializers

from realtime_chat_messaging.mixins.serializers import ChannelSerializerMixin, GroupChatListSerializerMixin, GroupChatSerializerMixin, GroupChatSerializerMixin, MessageSerializerMixin
from .models import CustomChannel, CustomMessage, CustomGroupChat, CustomRoomProperty
from realtime_chat_messaging.utils.loader import get_model
from django.contrib.auth import get_user_model
User = get_user_model()
# from django.core.exceptions import ValidationError

# ==================== CUSTOM SERIALIZER IMPLEMENTATIONS ====================

class CustomRoomPropertySerializer(serializers.ModelSerializer):
    """Custom room property serializer"""
    class Meta:
        model = CustomRoomProperty
        fields = ['id', 'preferences', 'archived']

class CustomMessageSerializer(
        MessageSerializerMixin,
        serializers.ModelSerializer
    ):
    """Custom message serializer"""
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    priority = serializers.CharField(default='normal')
    class Meta:
        model = CustomMessage
        fields = ['id', 'content','room', 'room_id', 'sender_id', 'sender_username', 'priority', 'metadata', 'created_at']

class CustomGroupChatSerializer(
        GroupChatSerializerMixin,
        serializers.ModelSerializer
    ):
    """Custom group chat serializer"""
    tags = serializers.JSONField(default=list)
    admins = serializers.SerializerMethodField()
    class Meta:
        model = CustomGroupChat
        fields = ['id', 'name', 'description', 'admins', 'participants', 'creator', 'max_participants', 'tags', "join_approval_required", "group_locked"]

    def get_admins(self, obj):  
        return [{"id": admin.id, "username": admin.username} for admin in obj.admins.all()]
    
class CustomGroupChatListSerializer(
        GroupChatListSerializerMixin,
        serializers.ModelSerializer
    ):
    class Meta:
        model = CustomGroupChat
        exclude = ['participants', 'admins', 'property']



class CustomChannelSerializer(
        ChannelSerializerMixin,
        serializers.ModelSerializer
    ):
    """Custom channel serializer"""
    preferences = serializers.JSONField(default=dict)
    moderators = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomChannel
        fields = ['id', 'name', 'description', 'creator', 'moderators', 'subscribers', 'max_subscribers', 'preferences']
    
    def get_moderators(self, obj):
        return [{"id": moderator.id, "username": moderator.username} for moderator in obj.moderators.all()]



    


