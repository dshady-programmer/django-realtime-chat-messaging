from rest_framework import serializers
from .models import CustomMessage, CustomGroupChat
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
    participant_count = serializers.SerializerMethodField()
    tags = serializers.JSONField(default=list)
    
    class Meta:
        model = CustomGroupChat
        fields = ['id', 'name', 'creator_name', 'participant_count', 'tags']
    
    def get_participant_count(self, obj):
        return obj.participants.count()