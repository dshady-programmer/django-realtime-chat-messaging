from django.db import models
from realtime_chat_messaging.model_mixins import (
  AbstractMessage,  AbstractGroupChat, AbstractRoomProperty, AbstractSession,
  AbstractChannel
)

from realtime_chat_messaging.models import Room
from django.contrib.auth import get_user_model
User = get_user_model()

# Create your models here.
# ==================== CUSTOM MODEL IMPLEMENTATIONS ====================

class CustomMessage(AbstractMessage):
    """Custom message model with additional fields"""
    priority = models.CharField(max_length=20, default='normal')
    metadata = models.JSONField(default=dict)
    
    class Meta(AbstractMessage.Meta):
        abstract = False


class CustomRoomProperty(AbstractRoomProperty):
    """Custom room property model with additional fields"""
    archived = models.BooleanField(default=False)
    
    class Meta(AbstractRoomProperty.Meta):
        abstract = False




class CustomGroupChat(Room, AbstractGroupChat):
    """Custom group chat with additional features"""
    admins = models.ManyToManyField(User, related_name="custom_groups_moderated")
    max_participants = models.PositiveBigIntegerField(default=100)
    avatar = models.URLField(null=True, blank=True)
    join_approval_required = models.BooleanField(default=False)
    group_locked = models.BooleanField(default=False)
    tags = models.JSONField(default=list)  # Additional field
    
    class Meta(AbstractGroupChat.Meta):
        abstract = False

# class CustomOneToOneChat(Room, AbstractOneToOneChat):
#     pass
#     class Meta(AbstractOneToOneChat.Meta):
#         abstract = False

        
class CustomChannel(Room, AbstractChannel):
    """Custom channel with additional features"""
    avatar = models.URLField(null=True, blank=True)
    moderators = models.ManyToManyField(User, related_name="+")
    max_subscribers = models.PositiveBigIntegerField(default=300)
    preferences = models.JSONField(default=dict)  # Additional field
 
    
    class Meta(AbstractChannel.Meta):
        permissions = AbstractChannel.Meta.permissions + [
            ("can_manage_preferences", "Can manage channel preferences")
        ]
        abstract = False


class CustomSession(AbstractSession):
    """Custom session model with device info"""
    device_type = models.CharField(max_length=50, default='unknown')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
