"""
Partial custom models for Scenario 4: Mixed override testing.

This app demonstrates overriding only Message and GroupChat models
while keeping other models (OneToOneChat, Channel, Session, etc.) as defaults.
"""
from django.db import models
from django.contrib.auth import get_user_model
from realtime_chat_messaging.mixins.models import AbstractMessage, AbstractGroupChat
from realtime_chat_messaging.models import Room

User = get_user_model()


class CustomMessage(AbstractMessage):
    """
    Custom Message with priority, tags, and read tracking.
    
    Use case: Organizations needing message categorization and priority handling.
    """
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='normal',
        db_index=True
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Message tags for categorization"
    )
    
    read_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times message was read"
    )
    
    importance_score = models.IntegerField(
        default=0,
        help_text="Calculated importance score"
    )
    
    class Meta(AbstractMessage.Meta):
        abstract = False
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['priority', 'created_at']),
            models.Index(fields=['importance_score']),
        ]
    
    def __str__(self):
        return f"[{self.priority}] {self.content[:30]}"
    
    def increment_read_count(self):
        """Increment read count"""
        self.read_count += 1
        self.save(update_fields=['read_count'])
    
    def calculate_importance(self):
        """Calculate importance score based on priority and reactions"""
        priority_scores = {'low': 1, 'normal': 2, 'high': 3, 'urgent': 4}
        score = priority_scores.get(self.priority, 0) * 10
        
        # Add reaction count
        if hasattr(self, 'reactions'):
            score += self.reactions.count() * 2
        
        self.importance_score = score
        self.save(update_fields=['importance_score'])
        return score


class CustomGroupChat(Room, AbstractGroupChat):
    """
    Custom GroupChat with department categorization and activity tracking.
    
    Use case: Corporate chat systems with department-based organization.
    """
    
    DEPARTMENT_CHOICES = [
        ('engineering', 'Engineering'),
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('hr', 'Human Resources'),
        ('finance', 'Finance'),
        ('general', 'General'),
    ]
    
    admins = models.ManyToManyField(User, related_name="partial_custom_groups_moderated")
    max_participants = models.PositiveBigIntegerField(default=100)
    avatar = models.URLField(null=True, blank=True)
    join_approval_required = models.BooleanField(default=False)
    group_locked = models.BooleanField(default=False)
    
    # Custom fields
    department = models.CharField(
        max_length=50,
        choices=DEPARTMENT_CHOICES,
        default='general',
        db_index=True
    )
    
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="Group categorization tags"
    )
    
    message_count = models.PositiveIntegerField(
        default=0,
        help_text="Total messages in this group"
    )
    
    last_activity = models.DateTimeField(
        auto_now=True,
        help_text="Last activity timestamp"
    )
    
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether group is archived"
    )
    
    class Meta(AbstractGroupChat.Meta):
        abstract = False
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['department', 'is_archived']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"[{self.department}] {self.name}"
    
    def increment_message_count(self):
        """Increment message count"""
        self.message_count += 1
        self.save(update_fields=['message_count', 'last_activity'])
    
    def archive(self):
        """Archive the group"""
        self.is_archived = True
        self.save(update_fields=['is_archived'])
    
    def unarchive(self):
        """Unarchive the group"""
        self.is_archived = False
        self.save(update_fields=['is_archived'])


# Signal to create property for custom models
from django.dispatch import receiver
from django.db.models.signals import pre_save


@receiver(pre_save, sender=CustomGroupChat)
def create_room_property(sender, instance, *args, **kwargs):
    """Create RoomProperty if not exists"""
    from realtime_chat_messaging.utils.loader import get_model
    RoomProperty = get_model("RoomProperty")
    
    if not hasattr(instance, 'property') or not instance.property:
        room_property = RoomProperty.objects.create()
        instance.property = room_property
