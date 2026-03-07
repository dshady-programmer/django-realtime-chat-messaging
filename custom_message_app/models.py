"""
Custom Message model for Scenario 1: Message-only override testing.

This app demonstrates overriding only the Message model while using
all other default models.
"""
from django.db import models
from realtime_chat_messaging.mixins.models import AbstractMessage


class CustomMessage(AbstractMessage):
    """
    Custom Message model with additional fields for priority and metadata.
    
    Use case: Applications that need to add urgency/importance to messages
    or attach custom metadata without modifying other models.
    """
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('critical', 'Critical')
    ]
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='normal',
        db_index=True,
        help_text="Message priority level"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom metadata for the message"
    )
    
    is_pinned = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this message is pinned in the room"
    )
    
    expiry_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiry date for temporary messages"
    )
    
    class Meta(AbstractMessage.Meta):
        abstract = False
        ordering = ['-priority', '-created_at']  # High priority first
        indexes = [
            models.Index(fields=['priority', 'created_at']),
            models.Index(fields=['is_pinned', 'room']),
        ]
    
    def __str__(self):
        return f"[{self.priority.upper()}] {self.content[:50]}"
    
    @property
    def is_high_priority(self):
        """Check if message is high priority or above"""
        return self.priority in ['high', 'urgent', 'critical']
    
    @property
    def is_expired(self):
        """Check if message has expired"""
        if not self.expiry_date:
            return False
        from django.utils import timezone
        return timezone.now() > self.expiry_date
