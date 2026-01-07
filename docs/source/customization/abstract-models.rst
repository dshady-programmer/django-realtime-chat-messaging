Extending with Abstract Models
===============================

Abstract models allow you to extend the package's base models with custom fields while maintaining compatibility with the package's functionality.

Why Use Abstract Models?
-------------------------

**Use abstract models when you need to:**

- Add custom database fields
- Add custom model methods
- Change field types or constraints
- Add custom properties or computed fields

**Don't use abstract models if you only need to:**

- Change serialization (use custom serializers instead)
- Add business logic (use custom handlers instead)
- Change validation (use custom serializers instead)

Available Abstract Models
-------------------------

The package provides 4 abstract models:

.. code-block:: python

   from realtime_chat_messaging.model_mixins import (
       AbstractMessage,
       AbstractGroupChat,
       AbstractChannel,
       AbstractOneToOneChat
   )

AbstractMessage
~~~~~~~~~~~~~~~

Base model for messages with core fields.

**Default Fields:**

.. code-block:: python

   class AbstractMessage(models.Model):
       id = models.UUIDField(primary_key=True, default=uuid.uuid4)
       room = models.ForeignKey("Room", on_delete=models.CASCADE, 
                               related_name="room_messages")
       sender = models.ForeignKey(User, on_delete=models.CASCADE, 
                                 related_name="user_messages")
       content = models.TextField()
       created_at = models.DateTimeField(auto_now_add=True)
       updated_at = models.DateTimeField(auto_now=True)

       class Meta:
           abstract = True

AbstractGroupChat
~~~~~~~~~~~~~~~~~

Base model for group chats.

**Default Fields:**

.. code-block:: python

   class AbstractGroupChat(models.Model):
       name = models.CharField(max_length=64)
       description = models.TextField(null=True, blank=True)
       creator = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  related_name="groups_owned")

       class Meta:
           abstract = True

AbstractChannel
~~~~~~~~~~~~~~~

Base model for channels.

**Default Fields:**

.. code-block:: python

   class AbstractChannel(models.Model):
       name = models.CharField(max_length=64)
       description = models.TextField(null=True, blank=True)
       creator = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  related_name="channels_owned")

       class Meta:
           abstract = True

AbstractOneToOneChat
~~~~~~~~~~~~~~~~~~~~

Base model for one-to-one chats.

**Default Fields:**

.. code-block:: python

   class AbstractOneToOneChat(models.Model):
       participants = models.ManyToManyField(User, related_name="chats")
       
       class Meta:
           abstract = True

Basic Usage Pattern
-------------------

Step 1: Create Custom Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.model_mixins import AbstractMessage

   class CustomMessage(AbstractMessage):
       # Add your custom fields
       priority = models.CharField(
           max_length=10,
           choices=[('low', 'Low'), ('normal', 'Normal'), ('urgent', 'Urgent')],
           default='normal'
       )
       tags = models.JSONField(default=list)
       pinned = models.BooleanField(default=False)
       
       class Meta:
           # Inherit indexes from AbstractMessage if needed
           indexes = AbstractMessage.Meta.indexes + [
               models.Index(fields=['priority', 'created_at']),
               models.Index(fields=['pinned']),
           ]

Step 2: Create Custom Serializer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer
   from rest_framework import serializers
   from .models import CustomMessage

   class CustomMessageSerializer(MessageSerializer):
       priority = serializers.ChoiceField(
           choices=['low', 'normal', 'urgent'],
           default='normal'
       )
       tags = serializers.ListField(
           child=serializers.CharField(),
           required=False
       )
       pinned = serializers.BooleanField(default=False)
       
       class Meta(MessageSerializer.Meta):
           model = CustomMessage
           fields = MessageSerializer.Meta.fields + ['priority', 'tags', 'pinned']

Step 3: Configure Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'MODELS': {
           'Message': 'myapp.models.CustomMessage',
       },
       'SERIALIZERS': {
           'MessageSerializer': 'myapp.serializers.CustomMessageSerializer',
       },
   }

Step 4: Run Migrations
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python manage.py makemigrations
   python manage.py migrate

Complete Examples
-----------------

Example 1: Message with Priority and Tags
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use Case**: Support system with urgent/normal/low priority messages and tagging.

**Model:**

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.model_mixins import AbstractMessage

   class PriorityMessage(AbstractMessage):
       PRIORITY_CHOICES = [
           ('low', 'Low'),
           ('normal', 'Normal'),
           ('urgent', 'Urgent'),
       ]
       
       priority = models.CharField(
           max_length=10,
           choices=PRIORITY_CHOICES,
           default='normal',
           db_index=True
       )
       tags = models.JSONField(default=list)
       assigned_to = models.ForeignKey(
           User,
           on_delete=models.SET_NULL,
           null=True,
           blank=True,
           related_name='assigned_messages'
       )
       resolved = models.BooleanField(default=False)
       resolved_at = models.DateTimeField(null=True, blank=True)
       
       class Meta:
           indexes = [
               models.Index(fields=['priority', '-created_at']),
               models.Index(fields=['resolved', 'priority']),
               models.Index(fields=['assigned_to', 'resolved']),
           ]
       
       def mark_resolved(self):
           from django.utils import timezone
           self.resolved = True
           self.resolved_at = timezone.now()
           self.save()

**Serializer:**

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer
   from rest_framework import serializers
   from .models import PriorityMessage

   class PriorityMessageSerializer(MessageSerializer):
       priority = serializers.ChoiceField(
           choices=['low', 'normal', 'urgent'],
           default='normal'
       )
       tags = serializers.ListField(
           child=serializers.CharField(max_length=50),
           required=False
       )
       assigned_to = serializers.PrimaryKeyRelatedField(
           queryset=User.objects.all(),
           required=False,
           allow_null=True
       )
       resolved = serializers.BooleanField(read_only=True)
       resolved_at = serializers.DateTimeField(read_only=True)
       
       class Meta(MessageSerializer.Meta):
           model = PriorityMessage
           fields = MessageSerializer.Meta.fields + [
               'priority', 'tags', 'assigned_to', 'resolved', 'resolved_at'
           ]
       
       def validate_priority(self, value):
           # Only staff can set urgent priority
           user = self.context.get('user')
           if value == 'urgent' and not user.is_staff:
               raise serializers.ValidationError(
                   "Only staff can set urgent priority"
               )
           return value

Example 2: Group Chat with Categories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use Case**: Organize groups by category (work, personal, hobbies, etc.).

**Model:**

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.model_mixins import AbstractGroupChat

   class CategorizedGroupChat(AbstractGroupChat):
       CATEGORY_CHOICES = [
           ('work', 'Work'),
           ('personal', 'Personal'),
           ('hobbies', 'Hobbies'),
           ('education', 'Education'),
           ('other', 'Other'),
       ]
       
       category = models.CharField(
           max_length=20,
           choices=CATEGORY_CHOICES,
           default='other',
           db_index=True
       )
       color = models.CharField(
           max_length=7,  # Hex color #RRGGBB
           default='#2196F3'
       )
       icon = models.CharField(max_length=50, blank=True)  # Icon name or emoji
       
       class Meta:
           indexes = [
               models.Index(fields=['category', 'creator']),
               models.Index(fields=['creator', 'category']),
           ]
       
       def get_category_display_color(self):
           colors = {
               'work': '#FF5722',
               'personal': '#4CAF50',
               'hobbies': '#9C27B0',
               'education': '#2196F3',
               'other': '#607D8B',
           }
           return colors.get(self.category, '#607D8B')

**Serializer:**

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import GroupChatSerializer
   from rest_framework import serializers
   from .models import CategorizedGroupChat

   class CategorizedGroupChatSerializer(GroupChatSerializer):
       category = serializers.ChoiceField(
           choices=['work', 'personal', 'hobbies', 'education', 'other'],
           default='other'
       )
       color = serializers.CharField(max_length=7, default='#2196F3')
       icon = serializers.CharField(max_length=50, required=False, allow_blank=True)
       category_color = serializers.SerializerMethodField()
       
       class Meta(GroupChatSerializer.Meta):
           model = CategorizedGroupChat
           fields = GroupChatSerializer.Meta.fields + [
               'category', 'color', 'icon', 'category_color'
           ]
       
       def get_category_color(self, obj):
           return obj.get_category_display_color()

Example 3: Channel with Subscription Tiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use Case**: Premium channels require subscription.

**Model:**

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.model_mixins import AbstractChannel

   class PremiumChannel(AbstractChannel):
       TIER_CHOICES = [
           ('free', 'Free'),
           ('basic', 'Basic'),
           ('premium', 'Premium'),
           ('enterprise', 'Enterprise'),
       ]
       
       required_tier = models.CharField(
           max_length=20,
           choices=TIER_CHOICES,
           default='free',
           db_index=True
       )
       is_verified = models.BooleanField(default=False)
       verified_at = models.DateTimeField(null=True, blank=True)
       monthly_price = models.DecimalField(
           max_digits=10,
           decimal_places=2,
           default=0.00
       )
       
       class Meta:
           indexes = [
               models.Index(fields=['required_tier', 'is_public']),
               models.Index(fields=['is_verified', '-created_at']),
           ]
       
       def can_user_access(self, user):
           """Check if user's subscription tier is sufficient"""
           tier_hierarchy = ['free', 'basic', 'premium', 'enterprise']
           user_tier = user.profile.subscription_tier
           
           user_tier_level = tier_hierarchy.index(user_tier)
           required_tier_level = tier_hierarchy.index(self.required_tier)
           
           return user_tier_level >= required_tier_level

**Serializer:**

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import ChannelSerializer
   from rest_framework import serializers
   from .models import PremiumChannel

   class PremiumChannelSerializer(ChannelSerializer):
       required_tier = serializers.ChoiceField(
           choices=['free', 'basic', 'premium', 'enterprise'],
           default='free'
       )
       is_verified = serializers.BooleanField(read_only=True)
       verified_at = serializers.DateTimeField(read_only=True)
       monthly_price = serializers.DecimalField(
           max_digits=10,
           decimal_places=2,
           default=0.00
       )
       user_can_access = serializers.SerializerMethodField()
       
       class Meta(ChannelSerializer.Meta):
           model = PremiumChannel
           fields = ChannelSerializer.Meta.fields + [
               'required_tier', 'is_verified', 'verified_at',
               'monthly_price', 'user_can_access'
           ]
       
       def get_user_can_access(self, obj):
           user = self.context.get('user')
           if not user:
               return False
           return obj.can_user_access(user)

Advanced Patterns
-----------------

Pattern 1: Timestamped Models with Soft Delete
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.model_mixins import AbstractMessage

   class AuditableMessage(AbstractMessage):
       # Track modifications
       modified_by = models.ForeignKey(
           User,
           on_delete=models.SET_NULL,
           null=True,
           related_name='modified_messages'
       )
       modification_count = models.IntegerField(default=0)
       
       # Soft delete with audit trail
       deleted_by = models.ForeignKey(
           User,
           on_delete=models.SET_NULL,
           null=True,
           related_name='deleted_messages'
       )
       deleted_at = models.DateTimeField(null=True, blank=True)
       deletion_reason = models.TextField(blank=True)
       
       def soft_delete(self, deleted_by, reason=''):
           from django.utils import timezone
           self.is_deleted = True
           self.deleted_by = deleted_by
           self.deleted_at = timezone.now()
           self.deletion_reason = reason
           self.save()
       
       def track_modification(self, modified_by):
           self.modified_by = modified_by
           self.modification_count += 1
           self.save()

Pattern 2: Searchable Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from django.contrib.postgres.search import SearchVectorField, SearchVector
   from realtime_chat_messaging.model_mixins import AbstractMessage

   class SearchableMessage(AbstractMessage):
       search_vector = SearchVectorField(null=True)
       
       class Meta:
           indexes = [
               models.Index(fields=['search_vector']),
           ]
       
       def save(self, *args, **kwargs):
           # Update search vector on save
           super().save(*args, **kwargs)
           self.search_vector = SearchVector('content')
           super().save(update_fields=['search_vector'])
       
       @classmethod
       def search(cls, query):
           from django.contrib.postgres.search import SearchQuery
           return cls.objects.filter(
               search_vector=SearchQuery(query)
           )

Pattern 3: Threaded Conversations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.model_mixins import AbstractMessage

   class ThreadedMessage(AbstractMessage):
       thread_root = models.ForeignKey(
           'self',
           on_delete=models.CASCADE,
           null=True,
           blank=True,
           related_name='thread_messages'
       )
       reply_count = models.IntegerField(default=0)
       last_reply_at = models.DateTimeField(null=True, blank=True)
       
       def get_thread(self):
           """Get all messages in this thread"""
           if self.thread_root:
               return ThreadedMessage.objects.filter(
                   thread_root=self.thread_root
               ).order_by('created_at')
           else:
               # This is root, get all replies
               return self.thread_messages.all().order_by('created_at')
       
       def update_thread_stats(self):
           """Update reply count and last reply time"""
           if self.parent_message:
               root = self.parent_message.thread_root or self.parent_message
               root.reply_count = root.thread_messages.count()
               root.last_reply_at = root.thread_messages.latest('created_at').created_at
               root.save()

Handling Migrations
-------------------

Initial Migration
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # After creating custom model
   python manage.py makemigrations myapp
   python manage.py migrate myapp

Adding Fields to Existing Model
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Add field to your custom model
   class CustomMessage(AbstractMessage):
       # ... existing fields ...
       new_field = models.CharField(max_length=100, default='')
   
   # Create migration
   python manage.py makemigrations myapp
   python manage.py migrate myapp

Data Migration
~~~~~~~~~~~~~~

.. code-block:: python

   # migrations/0002_populate_priority.py
   from django.db import migrations

   def set_default_priority(apps, schema_editor):
       CustomMessage = apps.get_model('myapp', 'CustomMessage')
       CustomMessage.objects.filter(priority__isnull=True).update(
           priority='normal'
       )

   class Migration(migrations.Migration):
       dependencies = [
           ('myapp', '0001_initial'),
       ]

       operations = [
           migrations.RunPython(set_default_priority),
       ]

Permission Implications
-----------------------

When you override models, default permissions may not work as expected:

**Issue:**

.. code-block:: python

   # Default permission checks: room.participants.filter(pk=user.pk)
   # If your CustomRoom has different structure, this breaks

**Solution**: Override permission functions:

.. code-block:: python

   # myapp/permissions.py
   from channels.db import database_sync_to_async
   
   @database_sync_to_async
   def custom_room_permission(user, room_id):
       from myapp.models import CustomRoom
       
       room = get_object_or_404(CustomRoom, id=room_id)
       
       # Your custom logic
       if hasattr(room, 'custom_members'):
           return room.custom_members.filter(pk=user.pk).exists(), room
       
       # Fallback to default
       return default_permission(user, room_id)
   
   # Configure in settings
   REALTIME_CHAT_MESSAGING = {
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.custom_room_permission',
       },
   }

Testing Custom Models
---------------------

.. code-block:: python

   # tests/test_custom_models.py
   from django.test import TestCase
   from myapp.models import PriorityMessage
   from django.contrib.auth import get_user_model

   User = get_user_model()

   class PriorityMessageTests(TestCase):
       
       def setUp(self):
           self.user = User.objects.create_user('testuser')
           self.room = Room.objects.create()
       
       def test_default_priority(self):
           """New messages have normal priority by default"""
           message = PriorityMessage.objects.create(
               room=self.room,
               sender=self.user,
               content='Test message'
           )
           
           self.assertEqual(message.priority, 'normal')
       
       def test_urgent_priority(self):
           """Can set urgent priority"""
           message = PriorityMessage.objects.create(
               room=self.room,
               sender=self.user,
               content='Urgent!',
               priority='urgent'
           )
           
           self.assertEqual(message.priority, 'urgent')
       
       def test_mark_resolved(self):
           """Can mark message as resolved"""
           message = PriorityMessage.objects.create(
               room=self.room,
               sender=self.user,
               content='Issue'
           )
           
           message.mark_resolved()
           
           self.assertTrue(message.resolved)
           self.assertIsNotNone(message.resolved_at)

Best Practices
--------------

1. Always Inherit from Abstract Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # ✅ Correct
   from realtime_chat_messaging.model_mixins import AbstractMessage
   
   class CustomMessage(AbstractMessage):
       custom_field = models.CharField(max_length=100)
   
   # ❌ Wrong - Loses all default fields
   from django.db import models
   
   class CustomMessage(models.Model):
       # Missing all AbstractMessage fields!
       custom_field = models.CharField(max_length=100)

2. Update Related Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you override a model, update:
- Serializer for that model
- Potentially: related serializers
- Potentially: permissions
- Potentially: handlers

3. Maintain Compatibility
~~~~~~~~~~~~~~~~~~~~~~~~~~

Don't remove or rename default fields:

.. code-block:: python

   # ❌ Wrong - Removes required field
   class CustomMessage(AbstractMessage):
       # Don't override core fields
       content = None  # This breaks everything!
   
   # ✅ Correct - Add new fields
   class CustomMessage(AbstractMessage):
       priority = models.CharField(max_length=10)

4. Use Indexes Wisely
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessage(AbstractMessage):
       priority = models.CharField(max_length=10, db_index=True)
       
       class Meta:
           indexes = [
               models.Index(fields=['priority', '-created_at']),
               models.Index(fields=['room', 'priority']),
           ]

5. Document Your Extensions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class PriorityMessage(AbstractMessage):
       """
       Message with priority levels for support ticketing.
       
       Additional Fields:
           - priority: Message urgency (low/normal/urgent)
           - tags: List of tags for categorization
           - assigned_to: User assigned to handle this message
           - resolved: Whether issue is resolved
       
       Usage:
           message = PriorityMessage.objects.create(
               room=room,
               sender=user,
               content='Help needed',
               priority='urgent'
           )
       """
       # ... fields ...

Next Steps
----------

- :doc:`serializers` - Create custom serializers for your models
- :doc:`event-handlers` - Adapt handlers for custom models
- :doc:`permissions` - Update permissions for custom models
- :doc:`settings-reference` - Configure custom models in settings