Customization Overview
======================

Django Realtime Chat Messaging is designed to be highly customizable while providing sensible defaults. This guide explains what can be customized and when you should customize it.

What Can Be Customized?
------------------------

The package allows customization at multiple levels:

1. **Settings** - Configure behavior via ``REALTIME_CHAT_MESSAGING`` dictionary
2. **Serializers** - Override data validation and serialization (14 serializers)
3. **Event Handlers** - Custom business logic for WebSocket events (15 handlers)
4. **Permissions** - Custom access control logic (6 permission functions)
5. **Event Mapper** - Add new events or override event routing
6. **Exception Handler** - Custom error handling and logging
7. **Models** - Extend base models with custom fields (via abstract models)
8. **Consumer** - Override entire consumer methods for complete control

Customization Levels
---------------------

Simple Customization (Settings Only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Best for:** Toggling features, changing defaults

**Examples:**
- Enable soft delete for messages
- Adjust behavior without writing code

**Complexity:** ⭐ Low

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': True,
   }

Moderate Customization (Serializers)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Best for:** Adding fields, custom validation, changing data structure

**Examples:**
- Add ``profile_picture`` to UserSerializer
- Validate message length differently
- Add custom fields to Message

**Complexity:** ⭐⭐ Medium

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
       },
   }

Advanced Customization (Handlers/Permissions)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Best for:** Custom business logic, integrations, special workflows

**Examples:**
- Upload files to S3 before creating messages
- Integrate with external notification service
- Implement premium tier restrictions
- Custom permission logic

**Complexity:** ⭐⭐⭐ High

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'EVENT_HANDLERS': {
           'create_message': 'myapp.handlers.custom_create_message',
       },
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.premium_room_check',
       },
   }

Expert Customization (Consumer/Models)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Best for:** Completely custom behavior, new features

**Examples:**
- Add new WebSocket events
- Extend models with complex relationships
- Override entire consumer flow

**Complexity:** ⭐⭐⭐⭐ Expert

.. code-block:: python

   # consumers.py
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   
   class CustomChatConsumer(ChatMessagingConsumer):
       async def receive_custom_event(self, data):
           # Completely custom functionality
           pass

When to Customize
-----------------

Use Default Behavior
~~~~~~~~~~~~~~~~~~~~~

**When:**
- Starting a new project
- Requirements match default features
- Prototyping or MVP

**Don't customize until you have a specific need.**

Override Serializers
~~~~~~~~~~~~~~~~~~~~

**When:**
- Need additional fields (avatar, bio, custom metadata)
- Custom validation rules
- Different data structure for frontend
- Adding computed fields

**Example scenarios:**
- "I need to include user's profile picture URL"
- "Messages should have a priority field"
- "Need to validate against profanity list"

Override Event Handlers
~~~~~~~~~~~~~~~~~~~~~~~

**When:**
- Need pre/post processing (logging, analytics, notifications)
- External integrations (S3, CDN, push notifications)
- Custom business logic (approval workflows, moderation)
- Multi-step operations

**Example scenarios:**
- "Upload files to S3 before saving message"
- "Send push notification when message created"
- "Log all room creations to audit system"
- "Integrate with existing notification service"

Override Permissions
~~~~~~~~~~~~~~~~~~~~

**When:**
- Custom access control beyond default
- Premium/subscription tiers
- Time-based restrictions
- Complex permission logic

**Example scenarios:**
- "Free users can only create 2 groups"
- "Premium rooms require subscription"
- "Users need approval to post in certain channels"

Override Event Mapper
~~~~~~~~~~~~~~~~~~~~~

**When:**
- Adding completely new events
- Changing default event handling
- Custom routing logic

**Example scenarios:**
- "Add 'user.status' event for online/offline"
- "Add 'message.pin' functionality"
- "Custom typing indicator behavior"

Override Models
~~~~~~~~~~~~~~~

**When:**
- Need additional database fields
- Custom model methods
- Different relationships

**Example scenarios:**
- "Messages need 'priority' and 'tags' fields"
- "Rooms need 'category' and 'color' fields"
- "Custom read receipt logic"

Customization Strategy
----------------------

The Principle of Least Modification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Start small, extend gradually:**

1. Try default behavior first
2. Override only what's necessary
3. Call default implementations when possible
4. Keep customizations isolated

**Example: Adding file upload**

❌ **Bad approach:**

.. code-block:: python

   # Rewrite entire create_message handler from scratch
   def custom_create_message(data, user):
       # 50 lines of duplicated code
       # Hard to maintain, breaks on updates

✅ **Good approach:**

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import create_message
   
   @database_sync_to_async
   def custom_create_message(data, user):
       # Handle file upload (custom logic)
       if 'file' in data:
           file_url = upload_to_s3(data['file'])
           data['extra_fields']['media'] = [{'media_url': file_url, ...}]
           data.pop('file')
       
       # Call default handler (reuse existing logic)
       return await create_message(data, user)

Composition Over Replacement
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Prefer extending to replacing:**

.. code-block:: python

   # ✅ Extend default behavior
   def custom_handler(data, user):
       result = default_handler(data, user)
       # Add custom logic
       send_analytics(result)
       return result
   
   # ❌ Replace everything
   def custom_handler(data, user):
       # Duplicate all default logic
       # Your custom logic
       pass

Understanding Dependencies
---------------------------

When you customize one component, you may need to customize related components:

Serializer Dependencies
~~~~~~~~~~~~~~~~~~~~~~~

**If you override a model**, you typically need to override its serializer:

.. code-block:: python

   # Custom model with extra field
   class CustomMessage(AbstractMessage):
       priority = models.IntegerField(default=0)
   
   # Need custom serializer too
   class CustomMessageSerializer(serializers.ModelSerializer):
       class Meta:
           model = CustomMessage
           fields = '__all__'

**If you override a serializer**, related serializers might need updating:

.. code-block:: python

   # If you customize MessageSerializer
   # Consider: MessageMediaAssetSerializer, ChatNotificationSerializer

Handler Dependencies
~~~~~~~~~~~~~~~~~~~~

**If you override a model**, handlers using that model need awareness:

.. code-block:: python

   # Default handler expects default Message model
   # If you have CustomMessage with different fields,
   # override handlers that create/query messages

Permission Dependencies
~~~~~~~~~~~~~~~~~~~~~~~

**If you override models**, default permissions won't work:

.. code-block:: python

   # Default permissions check: room.participants.filter(pk=user.pk)
   # If your CustomRoom has different member structure,
   # override permission functions

Configuration Best Practices
-----------------------------

Organize Settings
~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py - Keep organized
   REALTIME_CHAT_MESSAGING = {
       # Core behavior
       'MESSAGE_SOFT_DELETE': True,
       
       # Serializers
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
           'MessageSerializer': 'myapp.serializers.CustomMessageSerializer',
       },
       
       # Business logic
       'EVENT_HANDLERS': {
           'create_message': 'myapp.handlers.custom_create_message',
       },
       
       # Access control
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.custom_room_permission',
       },
   }

Document Your Customizations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/handlers.py
   
   @database_sync_to_async
   def custom_create_message(data, user):
       """
       Custom message handler that uploads files to S3.
       
       Extends default behavior by:
       - Uploading files to S3 before creating message
       - Generating presigned URLs for media
       - Logging message creation to analytics
       
       Args:
           data (dict): Message data from WebSocket
           user (User): User creating the message
       
       Returns:
           dict: Serialized message data
       """
       # Implementation...

Test Your Customizations
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # tests/test_custom_handlers.py
   from django.test import TestCase
   from myapp.handlers import custom_create_message
   
   class CustomHandlerTests(TestCase):
       async def test_file_upload_to_s3(self):
           # Test your custom logic
           pass

Common Customization Patterns
------------------------------

Pattern 1: Adding Fields
~~~~~~~~~~~~~~~~~~~~~~~~~

**Need:** Add custom fields to existing models

**Solution:**

1. Create custom model inheriting from Abstract model
2. Create custom serializer
3. Update settings

.. code-block:: python

   # myapp/models.py
   from realtime_chat_messaging.model_mixins import AbstractMessage
   
   class CustomMessage(AbstractMessage):
       priority = models.IntegerField(default=0)
       tags = models.JSONField(default=list)
   
   # myapp/serializers.py
   class CustomMessageSerializer(serializers.ModelSerializer):
       class Meta:
           model = CustomMessage
           fields = '__all__'
   
   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'MODELS': {'Message': 'myapp.models.CustomMessage'},
       'SERIALIZERS': {'MessageSerializer': 'myapp.serializers.CustomMessageSerializer'},
   }

Pattern 2: External Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Need:** Integrate with external service (S3, analytics, notifications)

**Solution:** Override handlers, call default, add integration

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import create_message
   
   @database_sync_to_async
   def custom_create_message(data, user):
       # Pre-processing
       track_event('message_attempt', user.id)
       
       # Call default
       result = await create_message(data, user)
       
       # Post-processing
       send_push_notification(result)
       
       return result

Pattern 3: Access Control
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Need:** Custom permission logic (premium tiers, quotas)

**Solution:** Override permission functions

.. code-block:: python

   from realtime_chat_messaging.permissions.helpers import have_room_permission
   
   @database_sync_to_async
   def custom_room_permission(user, room_id):
       # Check default permission
       is_permitted, room = await have_room_permission(user, room_id)
       
       if not is_permitted:
           return False, room
       
       # Custom logic
       if room.is_premium and not user.profile.is_subscribed:
           return False, room
       
       return True, room

Pattern 4: New Events
~~~~~~~~~~~~~~~~~~~~~

**Need:** Add custom WebSocket events

**Solution:** Extend event mapper, add handler method

.. code-block:: python

   # myapp/consumers.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers
   
   def custom_event_mapper(consumer):
       handlers = map_event_type_to_handlers(consumer)
       handlers['user.status'] = consumer.handle_user_status
       return handlers
   
   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'EVENT_MAPPER': 'myapp.consumers.custom_event_mapper',
   }

Next Steps
----------

Now that you understand customization principles:

1. **Review default behavior** - :doc:`../quickstart`
2. **Learn what to customize** - Following sections:
   
   - :doc:`serializers` - Add fields, validate data
   - :doc:`event-handlers` - Custom business logic
   - :doc:`permissions` - Access control
   - :doc:`abstract-models` - Extend models
   - :doc:`settings-reference` - All configuration options

3. **Test thoroughly** - Write tests for customizations

Remember: **Start simple, customize only when needed, and always test your changes!**