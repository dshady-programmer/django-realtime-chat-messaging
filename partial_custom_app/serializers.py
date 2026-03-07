"""
Custom serializers for Scenario 4 partial override.
"""
from rest_framework import serializers
from realtime_chat_messaging.mixins.serializers import MessageSerializerMixin, GroupChatSerializerMixin, GroupChatListSerializerMixin
from .models import CustomMessage, CustomGroupChat 


class CustomMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):
    """Serializer for CustomMessage with priority and tags"""
    
    priority = serializers.ChoiceField(
        choices=CustomMessage.PRIORITY_CHOICES,
        default='normal'
    )
    
    tags = serializers.JSONField(default=list)
    
    class Meta:
        model = CustomMessage
        fields = [
            'id', 'content', 'room', 'room_id', 'sender', 'sender_id',
            'priority', 'tags', 'read_count', 'importance_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'read_count', 'importance_score']
    
    def validate_tags(self, value):
        """Validate tags is a list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list")
        return value


class CustomGroupChatSerializer(GroupChatSerializerMixin, serializers.ModelSerializer):
    """Serializer for CustomGroupChat with department and activity tracking"""
    
    department = serializers.ChoiceField(
        choices=CustomGroupChat.DEPARTMENT_CHOICES,
        default='general'
    )
    
    tags = serializers.JSONField(default=list)
    admins = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomGroupChat
        fields = [
            'id', 'name', 'description', 'admins', 'participants', 'creator',
            'max_participants', 'department', 'tags', 'message_count',
            'last_activity', 'is_archived', 'join_approval_required', 'group_locked'
        ]
    
    def get_admins(self, obj):
        return [{"id": admin.id, "username": admin.username} for admin in obj.admins.all()]
    
    def validate_department(self, value):
        """Validate department choice"""
        valid_depts = [choice[0] for choice in CustomGroupChat.DEPARTMENT_CHOICES]
        if value not in valid_depts:
            raise serializers.ValidationError(f"Invalid department. Must be one of {valid_depts}")
        return value


class CustomGroupChatListSerializer(GroupChatListSerializerMixin, serializers.ModelSerializer):
    """List serializer for CustomGroupChat"""
    
    department = serializers.CharField()
    
    class Meta:
        model = CustomGroupChat
        exclude = ['participants', 'admins', 'property']
