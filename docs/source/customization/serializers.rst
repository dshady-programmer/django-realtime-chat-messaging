Customizing Serializers
=======================

Serializers control how data is validated and formatted. This guide shows you how to override default serializers to add fields, change validation, or modify data structure.

Available Serializers
---------------------

The package provides 14 serializers you can override:

**User Serialization**

- ``UserSerializer`` - Basic user data in messages and rooms

**Room List Serializers (Simplified)**

- ``OneToOneChatListSerializer`` - OneToOne chat in room list
- ``GroupChatListSerializer`` - Group chat in room list
- ``ChannelListSerializer`` - Channel in room list
- ``RoomListPolymorphicSerializer`` - Handles all room types in list

**Room Detail Serializers (Complete)**

- ``OneToOneChatSerializer`` - Full OneToOne chat details
- ``GroupChatSerializer`` - Full group chat details
- ``ChannelSerializer`` - Full channel details
- ``RoomPolymorphicSerializer`` - Handles all room types in detail

**Message & Related**

- ``MessageSerializer`` - Message data with all relations
- ``MessageMediaAssetSerializer`` - Media attachments
- ``ReadReceiptSerializer`` - Read receipt data
- ``ReactionSerializer`` - Message reaction data
- ``ChatNotificationSerializer`` - Notification data

Why Override Serializers?
--------------------------

Common Reasons
~~~~~~~~~~~~~~

1. **Add custom fields** - Include profile pictures, badges, metadata
2. **Change validation** - Custom rules for content, permissions
3. **Modify output** - Restructure data for frontend needs
4. **Computed fields** - Add fields calculated at serialization time
5. **Filter data** - Hide sensitive information based on user

Basic Override Pattern
----------------------

Step 1: Create Custom Serializer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/serializers.py
   from rest_framework import serializers
   from django.contrib.auth import get_user_model
   
   User = get_user_model()
   
   class CustomUserSerializer(serializers.ModelSerializer):
       avatar_url = serializers.SerializerMethodField()
       is_online = serializers.BooleanField(read_only=True)
       
       class Meta:
           model = User
           fields = ['id', 'username', 'email', 'first_name', 
                    'last_name', 'avatar_url', 'is_online']
       
       def get_avatar_url(self, obj):
           if hasattr(obj, 'profile') and obj.profile.avatar:
               return obj.profile.avatar.url
           return None

Step 2: Configure in Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
       },
   }

Step 3: Test
~~~~~~~~~~~~

.. code-block:: python

   # Test in Django shell
   from myapp.serializers import CustomUserSerializer
   from django.contrib.auth import get_user_model
   
   User = get_user_model()
   user = User.objects.first()
   serializer = CustomUserSerializer(user)
   print(serializer.data)

Common Customization Examples
------------------------------

Example 1: Add Profile Picture to UserSerializer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use case:** Show user avatars in chat interface

.. code-block:: python

   # myapp/serializers.py
   from rest_framework import serializers
   from django.contrib.auth import get_user_model
   
   User = get_user_model()
   
   class CustomUserSerializer(serializers.ModelSerializer):
       avatar_url = serializers.SerializerMethodField()
       full_name = serializers.SerializerMethodField()
       
       class Meta:
           model = User
           fields = ['id', 'username', 'email', 'avatar_url', 'full_name']
       
       def get_avatar_url(self, obj):
           # If using django-storages with S3
           if hasattr(obj, 'profile') and obj.profile.avatar:
               return obj.profile.avatar.url
           
           # Default avatar
           return f'https://ui-avatars.com/api/?name={obj.username}'
       
       def get_full_name(self, obj):
           return f"{obj.first_name} {obj.last_name}".strip() or obj.username

Example 2: Add Priority Field to Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use case:** Implement message priorities (urgent, normal, low)

**Step 1: Extend Model**

.. code-block:: python

   # myapp/models.py
   from realtime_chat_messaging.model_mixins import AbstractMessage
   from django.db import models
   
   class CustomMessage(AbstractMessage):
       PRIORITY_CHOICES = [
           ('low', 'Low'),
           ('normal', 'Normal'),
           ('urgent', 'Urgent'),
       ]
       priority = models.CharField(
           max_length=10, 
           choices=PRIORITY_CHOICES, 
           default='normal'
       )
       tags = models.JSONField(default=list)

**Step 2: Custom Serializer**

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer as BaseMessageSerializer
   from .models import CustomMessage
   
   class CustomMessageSerializer(BaseMessageSerializer):
       priority = serializers.ChoiceField(
           choices=['low', 'normal', 'urgent'],
           default='normal'
       )
       tags = serializers.ListField(
           child=serializers.CharField(max_length=50),
           required=False,
           default=list
       )
       
       class Meta(BaseMessageSerializer.Meta):
           model = CustomMessage
           fields = BaseMessageSerializer.Meta.fields + ['priority', 'tags']
       
       def validate_priority(self, value):
           # Custom validation
           if value == 'urgent' and not self.context.get('user').is_staff:
               raise serializers.ValidationError(
                   "Only staff can send urgent messages"
               )
           return value

**Step 3: Configure**

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

Example 3: Add Room Metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use case:** Store custom room settings (theme, wallpaper, notifications)

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import GroupChatSerializer
   
   class CustomGroupChatSerializer(GroupChatSerializer):
       member_count = serializers.SerializerMethodField()
       unread_count = serializers.SerializerMethodField()
       
       class Meta(GroupChatSerializer.Meta):
           fields = GroupChatSerializer.Meta.fields + [
               'member_count', 
               'unread_count'
           ]
       
       def get_member_count(self, obj):
           return obj.participants.count()
       
       def get_unread_count(self, obj):
           user = self.context.get('user')
           if not user:
               return 0
           
           # Count unread messages for this user
           from realtime_chat_messaging.models import ChatNotification
           return ChatNotification.objects.filter(
               message__room=obj,
               recipients=user
           ).count()

Example 4: Custom Validation Rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use case:** Validate message content against business rules

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer
   import bleach
   import re
   
   class CustomMessageSerializer(MessageSerializer):
       
       def validate_content(self, value):
           # Call parent validation (HTML sanitization)
           value = super().validate_content(value)
           
           # Custom rules
           
           # 1. Minimum length
           if len(value.strip()) < 1:
               raise serializers.ValidationError(
                   "Message cannot be empty"
               )
           
           # 2. Maximum length
           if len(value) > 1000:
               raise serializers.ValidationError(
                   "Message too long (max 1000 characters)"
               )
           
           # 3. No spam (repeated characters)
           if re.search(r'(.)\1{10,}', value):
               raise serializers.ValidationError(
                   "Message appears to be spam"
               )
           
           # 4. Profanity filter (if enabled)
           from myapp.utils import contains_profanity
           if contains_profanity(value):
               raise serializers.ValidationError(
                   "Message contains inappropriate language"
               )
           
           return value
       
       def validate(self, attrs):
           # Cross-field validation
           room = attrs.get('room')
           user = self.context.get('user')
           
           # Check if user can send in this room
           if hasattr(room, 'group_locked') and room.group_locked:
               if user not in room.admins.all():
                   raise serializers.ValidationError(
                       "Only admins can post in locked groups"
                   )
           
           return super().validate(attrs)

Example 5: Filter Sensitive Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use case:** Hide email addresses from non-admin users

.. code-block:: python

   # myapp/serializers.py
   from rest_framework import serializers
   from django.contrib.auth import get_user_model
   
   User = get_user_model()
   
   class PrivacyAwareUserSerializer(serializers.ModelSerializer):
       email = serializers.SerializerMethodField()
       phone = serializers.SerializerMethodField()
       
       class Meta:
           model = User
           fields = ['id', 'username', 'email', 'phone']
       
       def get_email(self, obj):
           request_user = self.context.get('user')
           
           # Show full email to:
           # - The user themselves
           # - Staff/admin users
           if request_user and (request_user.id == obj.id or request_user.is_staff):
               return obj.email
           
           # Hide for others
           return None
       
       def get_phone(self, obj):
           request_user = self.context.get('user')
           
           # Only show to user themselves
           if request_user and request_user.id == obj.id:
               return obj.profile.phone if hasattr(obj, 'profile') else None
           
           return None

Working with Polymorphic Serializers
-------------------------------------

Room Polymorphic Serializers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When customizing room serializers, you may need to update the polymorphic serializer:

.. code-block:: python

   # myapp/serializers.py
   from rest_polymorphic.serializers import PolymorphicSerializer
   from realtime_chat_messaging.serializers import (
       OneToOneChatSerializer,
       GroupChatSerializer,
       ChannelSerializer,
   )
   
   # Custom individual serializers
   class CustomGroupChatSerializer(GroupChatSerializer):
       custom_field = serializers.CharField()
       
       class Meta(GroupChatSerializer.Meta):
           fields = GroupChatSerializer.Meta.fields + ['custom_field']
   
   # Update polymorphic serializer
   class CustomRoomPolymorphicSerializer(PolymorphicSerializer):
       resource_type_field_name = "type"
       model_serializer_mapping = {
           OneToOneChat: OneToOneChatSerializer,
           GroupChat: CustomGroupChatSerializer,  # Use custom
           Channel: ChannelSerializer,
       }

Context in Serializers
----------------------

Serializers receive context with useful information:

.. code-block:: python

   class CustomMessageSerializer(MessageSerializer):
       
       def validate(self, attrs):
           # Access context
           user = self.context.get('user')  # Current user
           request = self.context.get('request')  # Request object (if available)
           
           # Use context in validation
           if user and not user.is_active:
               raise serializers.ValidationError("User is inactive")
           
           return super().validate(attrs)

Context is passed automatically by event handlers:

.. code-block:: python

   # In handler
   serializer = MessageSerializer(data=data, context={'user': user})

Best Practices
--------------

1. Inherit from Default
~~~~~~~~~~~~~~~~~~~~~~~

Always inherit from the default serializer:

.. code-block:: python

   # ✅ Good
   from realtime_chat_messaging.serializers import MessageSerializer
   
   class CustomMessageSerializer(MessageSerializer):
       # Add your fields
       pass
   
   # ❌ Bad - Starting from scratch loses default behavior
   class CustomMessageSerializer(serializers.ModelSerializer):
       # Reimplementing everything
       pass

2. Call Parent Methods
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessageSerializer(MessageSerializer):
       
       def validate_content(self, value):
           # Call parent (includes HTML sanitization)
           value = super().validate_content(value)
           
           # Add your validation
           if 'spam' in value.lower():
               raise serializers.ValidationError("Spam detected")
           
           return value

3. Use SerializerMethodField for Computed Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessageSerializer(MessageSerializer):
       time_ago = serializers.SerializerMethodField()
       
       def get_time_ago(self, obj):
           from django.utils.timesince import timesince
           return timesince(obj.created_at)

4. Keep Serializers Focused
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One serializer = one purpose:

.. code-block:: python

   # ✅ Good - Separate serializers for list and detail
   class MessageListSerializer(serializers.ModelSerializer):
       # Minimal fields for list view
       pass
   
   class MessageDetailSerializer(serializers.ModelSerializer):
       # All fields for detail view
       pass
   
   # ❌ Bad - One giant serializer doing everything
   class MessageSerializer(serializers.ModelSerializer):
       # 50 fields, complex logic, slow
       pass

5. Document Custom Fields
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessageSerializer(MessageSerializer):
       priority = serializers.ChoiceField(
           choices=['low', 'normal', 'urgent'],
           help_text="Message priority level. Only staff can use 'urgent'.",
           default='normal'
       )

Testing Custom Serializers
---------------------------

Always test your custom serializers:

.. code-block:: python

   # tests/test_serializers.py
   from django.test import TestCase
   from myapp.serializers import CustomMessageSerializer
   from django.contrib.auth import get_user_model
   
   User = get_user_model()
   
   class CustomMessageSerializerTest(TestCase):
       
       def setUp(self):
           self.user = User.objects.create_user('testuser')
       
       def test_priority_validation_for_staff(self):
           """Staff can set urgent priority"""
           self.user.is_staff = True
           
           data = {
               'content': 'Urgent message',
               'priority': 'urgent',
               'room_id': '...',
               'sender_id': self.user.id,
           }
           
           serializer = CustomMessageSerializer(
               data=data,
               context={'user': self.user}
           )
           self.assertTrue(serializer.is_valid())
       
       def test_priority_validation_for_regular_user(self):
           """Regular users cannot set urgent priority"""
           data = {
               'content': 'Urgent message',
               'priority': 'urgent',
               'room_id': '...',
               'sender_id': self.user.id,
           }
           
           serializer = CustomMessageSerializer(
               data=data,
               context={'user': self.user}
           )
           self.assertFalse(serializer.is_valid())
           self.assertIn('priority', serializer.errors)

Performance Considerations
--------------------------

Avoid N+1 Queries
~~~~~~~~~~~~~~~~~

Use ``select_related`` and ``prefetch_related`` in handlers:

.. code-block:: python

   # In your custom handler
   messages = Message.objects.filter(room=room).select_related(
       'sender',
       'parent_message',
   ).prefetch_related(
       'reactions__user',
       'read_receipts__reader',
       'attachments',
   )

Limit Serialized Data
~~~~~~~~~~~~~~~~~~~~~

For list views, use minimal serializers:

.. code-block:: python

   class MessageListSerializer(MessageSerializer):
       class Meta(MessageSerializer.Meta):
           fields = ['id', 'content', 'sender', 'created_at']
           # Exclude heavy fields like reactions, read_receipts

Common Pitfalls
---------------

Pitfall 1: Forgetting to Update Related Serializers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # If you override MessageSerializer,
   # also check: ChatNotificationSerializer (includes message)

Pitfall 2: Breaking Required Signatures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # ❌ Wrong - Changed expected fields
   class CustomMessageSerializer(MessageSerializer):
       # Removed 'room_id' - handlers expect this!
       pass
   
   # ✅ Correct - Keep required fields, add optional ones
   class CustomMessageSerializer(MessageSerializer):
       priority = serializers.CharField(required=False)

Pitfall 3: Not Passing Context
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # ❌ Wrong - No context
   serializer = CustomMessageSerializer(data=data)
   
   # ✅ Correct - Pass context
   serializer = CustomMessageSerializer(data=data, context={'user': user})

Next Steps
----------

- :doc:`event-handlers` - Customize business logic
- :doc:`permissions` - Custom access control
- :doc:`abstract-models` - Extend database models
- :doc:`settings-reference` - All configuration options