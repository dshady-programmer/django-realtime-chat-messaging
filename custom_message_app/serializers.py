"""
Custom Message serializer for Scenario 1.
"""
from rest_framework import serializers
from realtime_chat_messaging.mixins.serializers import MessageSerializerMixin
from .models import CustomMessage


class CustomMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):
    """
    Serializer for CustomMessage with priority and metadata fields.
    """
    
    priority = serializers.ChoiceField(
        choices=CustomMessage.PRIORITY_CHOICES,
        default='normal'
    )
    
    is_high_priority = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CustomMessage
        fields = [
            'id', 'content', 'room', 'room_id', 'sender', 'sender_id',
            'priority', 'metadata', 'is_pinned', 'expiry_date',
            'is_high_priority', 'is_expired',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_priority(self, value):
        """Validate priority value"""
        valid_priorities = [choice[0] for choice in CustomMessage.PRIORITY_CHOICES]
        if value not in valid_priorities:
            raise serializers.ValidationError(f"Invalid priority. Must be one of {valid_priorities}")
        return value
    
    def validate_metadata(self, value):
        """Validate metadata is a dictionary"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a dictionary")
        return value
