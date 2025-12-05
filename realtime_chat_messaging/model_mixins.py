from django.contrib.auth import get_user_model
from django.db import models
import uuid


User = get_user_model()

class AbstractGroupChat(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="groups_owned")

    class Meta:
        abstract = True

class AbstractChannel(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(null=True, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channels_owned")

    class Meta:
        abstract = True

class AbstractOneToOneChat(models.Model):
    participants = models.ManyToManyField(User, related_name="chats")
    
    class Meta:
        abstract = True

class AbstractMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    room = models.ForeignKey("Room", on_delete=models.CASCADE, related_name="room_messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
