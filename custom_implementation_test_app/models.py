from django.db import models
from realtime_chat_messaging.model_mixins import (
    AbstractChannel, AbstractMessage, AbstractOneToOneChat, AbstractRoom, AbstractGroupChat, AbstractSession
)
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


class CustomRoom(AbstractRoom):
    """Custom room model with additional fields"""
    preferences = models.JSONField(default=dict)
    archived = models.BooleanField(default=False)
    



class CustomGroupChat(CustomRoom, AbstractGroupChat):
    """Custom group chat with additional features"""
    admins = models.ManyToManyField(User, related_name="custom_groups_moderated")
    max_participants = models.PositiveBigIntegerField(default=100)
    avatar = models.URLField(null=True, blank=True)
    join_approval_required = models.BooleanField(default=False)
    group_locked = models.BooleanField(default=False)
    tags = models.JSONField(default=list)  # Additional field
    
    class Meta(AbstractGroupChat.Meta):
        abstract = False

class CustomOneToOneChat(CustomRoom, AbstractOneToOneChat):
    pass
    class Meta(AbstractOneToOneChat.Meta):
        abstract = False

        
class CustomChannel(CustomRoom, AbstractChannel):
    """Custom channel with additional features"""
    avatar = models.URLField(null=True, blank=True)
    moderators = models.ManyToManyField(User, related_name="+")
    max_subscribers = models.PositiveBigIntegerField(default=300)
 
    
    class Meta(AbstractChannel.Meta):
        abstract = False


class CustomSession(AbstractSession):
    """Custom session model with device info"""
    device_type = models.CharField(max_length=50, default='unknown')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
