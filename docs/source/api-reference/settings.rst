Settings Reference
==================

Complete reference for all configuration options in ``REALTIME_CHAT_MESSAGING`` settings.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

All package settings go in a single dictionary in your Django ``settings.py``:

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "MODELS": {...},
       "SERIALIZERS": {...},
       "EVENT_HANDLER_CLASS": "...",
       "PERMISSION_HANDLER_CLASS": "...",
       "EVENT_MAPPER": "...",
       "EXCEPTION_HANDLER_CLASS": "...",
       "MESSAGE_SOFT_DELETE": True,
       "ENABLE_NOTIFICATION": True,
   }

All settings are optional - the package uses sensible defaults.

MODELS
------

Swap any model with your custom implementation.

**Type:** ``dict``

**Default:**

.. code-block:: python

   {
       "Room": "realtime_chat_messaging.Room",
       "OneToOneChat": "realtime_chat_messaging.OneToOneChat",
       "GroupChat": "realtime_chat_messaging.GroupChat",
       "Channel": "realtime_chat_messaging.Channel",
       "Message": "realtime_chat_messaging.Message",
       "MessageMediaAsset": "realtime_chat_messaging.MessageMediaAsset",
       "ReadReceipt": "realtime_chat_messaging.ReadReceipt",
       "ChatNotification": "realtime_chat_messaging.ChatNotification",
       "Reaction": "realtime_chat_messaging.Reaction",
   }

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.models.CustomMessage",
           "Room": "myapp.models.CustomRoom",
       }
   }

**Requirements:**

* Must inherit from the corresponding Abstract base:
  
  - ``AbstractRoom``
  - ``AbstractOneToOneChat``
  - ``AbstractGroupChat``
  - ``AbstractChannel``
  - ``AbstractMessage``
  - ``AbstractReadReceipt``
  - ``AbstractReaction``
  - ``AbstractChatNotification``
  - ``AbstractMessageMediaAsset``

* Must include all required fields from abstract base
* Must be defined BEFORE running migrations

.. warning::
   **Extending Room requires extending all room types**
   
   If you swap ``Room``, you MUST also swap ``OneToOneChat``, ``GroupChat``, and ``Channel`` because they inherit from ``Room``. Otherwise migrations will fail.

**Example: Custom Message Model**

.. code-block:: python

   # myapp/models.py
   from realtime_chat_messaging.model_mixins import AbstractMessage
   from django.db import models

   class CustomMessage(AbstractMessage):
       priority = models.CharField(
           max_length=10,
           choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')],
           default='normal'
       )
       is_pinned = models.BooleanField(default=False)
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_MESSAGE_MODEL'

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.CustomMessage"
       }
   }

See :doc:`../customization/models` for complete guide.

SERIALIZERS
-----------

Swap any serializer to customize JSON representation.

**Type:** ``dict``

**Default:**

.. code-block:: python

   {
       "UserSerializer": "realtime_chat_messaging.serializers.UserSerializer",
       "OneToOneChatListSerializer": "realtime_chat_messaging.serializers.OneToOneChatListSerializer",
       "GroupChatListSerializer": "realtime_chat_messaging.serializers.GroupChatListSerializer",
       "ChannelListSerializer": "realtime_chat_messaging.serializers.ChannelListSerializer",
       "OneToOneChatSerializer": "realtime_chat_messaging.serializers.OneToOneChatSerializer",
       "GroupChatSerializer": "realtime_chat_messaging.serializers.GroupChatSerializer",
       "ChannelSerializer": "realtime_chat_messaging.serializers.ChannelSerializer",
       "ReadReceiptSerializer": "realtime_chat_messaging.serializers.ReadReceiptSerializer",
       "ReactionSerializer": "realtime_chat_messaging.serializers.ReactionSerializer",
       "MessageMediaAssetSerializer": "realtime_chat_messaging.serializers.MessageMediaAssetSerializer",
       "MessageSerializer": "realtime_chat_messaging.serializers.MessageSerializer",
       "ChatNotificationSerializer": "realtime_chat_messaging.serializers.ChatNotificationSerializer",
       "RoomListPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomListPolymorphicSerializer",
       "RoomPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomPolymorphicSerializer",
   }

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
           "UserSerializer": "myapp.serializers.CustomUserSerializer",
       }
   }

**Requirements:**

* Should inherit from base serializer or provide same interface
* Must handle all required fields
* Must be compatible with swapped models

**Example: Custom Message Serializer**

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer as BaseMessageSerializer

   class CustomMessageSerializer(BaseMessageSerializer):
       priority = serializers.CharField(read_only=True)
       is_pinned = serializers.BooleanField(read_only=True)
       
       class Meta(BaseMessageSerializer.Meta):
           fields = BaseMessageSerializer.Meta.fields + ['priority', 'is_pinned']

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer"
       }
   }

See :doc:`../customization/serializers` for complete guide.

EVENT_HANDLER_CLASS
-------------------

Override the event handler class to customize business logic.

**Type:** ``str`` (import path)

**Default:** ``"realtime_chat_messaging.utils.handlers.EventHandler"``

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler"
   }

**Requirements:**

* Must inherit from ``EventHandler`` or implement all handler mixins
* Can override specific methods while keeping others
* All methods must maintain same signature

**Example: Custom Event Handler**

.. code-block:: python

   # myapp/handlers.py
   from realtime_chat_messaging.utils.handlers import EventHandler
   import firebase_admin

   class CustomEventHandler(EventHandler):
       
       @staticmethod
       def create_chat_notification(message, type, user):
           # Call parent to create database notification
           EventHandler.create_chat_notification(message, type, user)
           
           # Add push notification
           room = message.room
           recipients = room.participants.exclude(id=user.id)
           
           for recipient in recipients:
               if hasattr(recipient, 'fcm_token') and recipient.fcm_token:
                   firebase_admin.messaging.send(
                       messaging.Message(
                           notification=messaging.Notification(
                               title=f"New message from {user.username}",
                               body=message.content[:100]
                           ),
                           token=recipient.fcm_token
                       )
                   )

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler"
   }

See :doc:`../customization/handlers` for complete guide.

PERMISSION_HANDLER_CLASS
------------------------

Override permission handler to customize access control.

**Type:** ``str`` (import path)

**Default:** ``"realtime_chat_messaging.permissions.handlers.PermissionHandler"``

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler"
   }

**Requirements:**

* Must inherit from ``PermissionHandler`` or implement ``PermissionHelperMixin``
* All methods must return ``(is_permitted: bool, room: Room)`` tuple
* Can customize permission logic while maintaining interface

**Example: Custom Permission Handler**

.. code-block:: python

   # myapp/permissions.py
   from realtime_chat_messaging.permissions.handlers import PermissionHandler

   class CustomPermissionHandler(PermissionHandler):
       
       @staticmethod
       def _have_send_message_permission(user, data, default_admin_names={"group": "admins", "channel": "moderators"}):
           is_permitted, room = PermissionHandler._have_send_message_permission(
               user, data, default_admin_names
           )
           
           # Additional check: User must have verified email
           if is_permitted and not user.email_verified:
               return False, room
           
           return is_permitted, room

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler"
   }

.. note::
   **Optional Field Handling**
   
   If you've added custom fields to ``GroupChat`` or ``Channel`` models (like renaming ``admins`` to ``moderators_list``), pass ``default_admin_names`` parameter:
   
   .. code-block:: python

      default_admin_names = {
          "group": "moderators_list",  # Custom field name
          "channel": "super_moderators"
      }

See :doc:`../customization/permissions` for complete guide.

EVENT_MAPPER
------------

Map event types to consumer handler methods. Use this to add custom events.

**Type:** ``str`` (import path to function)

**Default:** ``"realtime_chat_messaging.variables.consumers.map_event_type_to_handlers"``

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_MAPPER": "myapp.events.custom_event_mapper"
   }

**Requirements:**

* Must be a function that accepts ``self`` (consumer instance)
* Must return a dictionary mapping event names to handler methods
* Can extend default mappings or replace entirely

**Example: Add Custom Events**

.. code-block:: python

   # myapp/events.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers

   def custom_event_mapper(consumer_instance):
       # Get default mappings
       default_handlers = map_event_type_to_handlers(consumer_instance)
       
       # Add custom events
       default_handlers.update({
           "message.pin": consumer_instance.handle_pin_message,
           "message.unpin": consumer_instance.handle_unpin_message,
           "room.archive": consumer_instance.handle_archive_room,
       })
       
       return default_handlers

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "EVENT_MAPPER": "myapp.events.custom_event_mapper"
   }

Then create custom consumer:

.. code-block:: python

   # myapp/consumers.py
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from realtime_chat_messaging.utils.decorators import ExceptionHandler

   class CustomChatConsumer(ChatMessagingConsumer):
       
       @ExceptionHandler.exception_handler_decorator
       async def handle_pin_message(self, data):
           # Your custom logic
           message_id = data.get('message_id')
           # ... pin message logic
           
           await self.send_group(
               f"group-{data['room_id']}",
               "message.pinned",
               {"message_id": message_id}
           )

See :doc:`../customization/consumers` for complete guide.

EXCEPTION_HANDLER_CLASS
-----------------------

Customize error handling and logging.

**Type:** ``str`` (import path)

**Default:** ``"realtime_chat_messaging.utils.decorators.ExceptionHandler"``

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EXCEPTION_HANDLER_CLASS": "myapp.errors.CustomExceptionHandler"
   }

**Requirements:**

* Must provide ``exception_handler_decorator`` classmethod
* Must handle all exception types gracefully
* Should send error responses to client

**Example: Custom Exception Handler**

.. code-block:: python

   # myapp/errors.py
   from functools import wraps
   import json
   import logging
   from sentry_sdk import capture_exception

   logger = logging.getLogger(__name__)

   class CustomExceptionHandler:
       
       @classmethod
       def exception_handler_decorator(cls, func):
           @wraps(func)
           async def wrapper(self, *args, **kwargs):
               try:
                   return await func(self, *args, **kwargs)
               except Exception as exc:
                   # Log to Sentry
                   capture_exception(exc)
                   
                   # Log locally
                   logger.error(
                       f"Error in {func.__name__}: {exc}",
                       exc_info=True,
                       extra={'user_id': self.user.id if hasattr(self, 'user') else None}
                   )
                   
                   # Send to client
                   await self.send(text_data=json.dumps({
                       "error": {
                           "code": 4006,
                           "detail": "An error occurred. Support has been notified."
                       }
                   }))
           
           return wrapper

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "EXCEPTION_HANDLER_CLASS": "myapp.errors.CustomExceptionHandler"
   }

MESSAGE_SOFT_DELETE
-------------------

Control message deletion behavior.

**Type:** ``bool``

**Default:** ``False``

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MESSAGE_SOFT_DELETE": True
   }

**Options:**

``True`` - Soft Delete
   * Sets ``is_deleted=True`` on message
   * Message stays in database
   * Can be recovered by setting ``is_deleted=False``
   * Frontend should hide deleted messages
   * Replies and forwards maintain reference

``False`` - Hard Delete
   * Removes message from database permanently
   * Cannot be recovered
   * Replies lose ``parent_message`` reference (set to ``null``)
   * Forwards lose ``forwarded_from`` reference (set to ``null``)

**When to use Soft Delete:**

* Compliance requirements (must retain all data)
* Audit trails needed
* Users might want to recover
* Investigation purposes

**When to use Hard Delete:**

* Privacy regulations (GDPR "right to be forgotten")
* Storage constraints
* No recovery needed

**Frontend Handling:**

If using soft delete, filter in frontend:

.. code-block:: javascript

   const visibleMessages = messages.filter(msg => !msg.is_deleted);

Or backend when fetching:

.. code-block:: python

   Message.objects.filter(room=room, is_deleted=False)

ENABLE_NOTIFICATION
-------------------

Enable or disable the notification tracking system.

**Type:** ``bool``

**Default:** ``True``

**Usage:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "ENABLE_NOTIFICATION": False
   }

**When Enabled (``True``):**

* ``ChatNotification`` records created for each message
* Tracks which users haven't acknowledged messages
* ``recipients`` list updated as users acknowledge
* Notifications deleted when all users acknowledge
* Enables push notification integration

**When Disabled (``False``):**

* No ``ChatNotification`` records created
* No unread message tracking
* ``message.acknowledged`` still works (updates ``delivered_to`` field)
* Saves database writes and queries
* Use when notifications aren't needed

**Impact on Features:**

.. list-table::
   :header-rows: 1
   :widths: 40 30 30

   * - Feature
     - Enabled
     - Disabled
   * - Unread message count
     - ✅ Available
     - ❌ Not available
   * - Notification on connect
     - ✅ Dispatched
     - ❌ Not dispatched
   * - Push notification integration
     - ✅ Possible
     - ❌ Not possible
   * - ``delivered_to`` tracking
     - ✅ Works
     - ✅ Works
   * - Database writes per message
     - +1 (notification)
     - 0

**Use Cases:**

Enable when:
   * Need unread counts
   * Integrating push notifications
   * Building notification center
   * Users expect delivery tracking

Disable when:
   * Simple chat without notifications
   * Performance critical (high message volume)
   * Notifications handled elsewhere
   * Reducing database load

Complete Configuration Example
------------------------------

Here's a full example with all settings customized:

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       # Custom Models
       "MODELS": {
           "Message": "myapp.models.CustomMessage",
           "Room": "myapp.models.CustomRoom",
           "OneToOneChat": "myapp.models.CustomOneToOneChat",
           "GroupChat": "myapp.models.CustomGroupChat",
           "Channel": "myapp.models.CustomChannel",
       },
       
       # Custom Serializers
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
           "UserSerializer": "myapp.serializers.CustomUserSerializer",
           "RoomPolymorphicSerializer": "myapp.serializers.CustomRoomPolymorphicSerializer",
       },
       
       # Custom Handlers
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler",
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler",
       "EXCEPTION_HANDLER_CLASS": "myapp.errors.CustomExceptionHandler",
       
       # Custom Events
       "EVENT_MAPPER": "myapp.events.custom_event_mapper",
       
       # Feature Toggles
       "MESSAGE_SOFT_DELETE": True,
       "ENABLE_NOTIFICATION": True,
   }

Migration Strategy
------------------

When changing model settings:

1. **Make changes in settings**

   .. code-block:: python

      REALTIME_CHAT_MESSAGING = {
          "MODELS": {
              "Message": "myapp.CustomMessage"
          }
      }

2. **Create migrations**

   .. code-block:: bash

      python manage.py makemigrations

3. **Review migrations**

   Check that swappable foreign keys use correct model

4. **Run migrations**

   .. code-block:: bash

      python manage.py migrate

5. **Update serializers if needed**

   If model has new fields, update corresponding serializer

.. warning::
   **Never change model settings after deploying to production** without a migration plan. Changing swappable models requires data migration.

Validation
----------

Settings are validated on Django startup. Invalid settings raise ``ImproperlyConfigured``:

.. code-block:: text

   django.core.exceptions.ImproperlyConfigured: 
   MessageSerializer key 'InvalidSerializer' not in valid serializers keys

**Validation checks:**

* All MODELS keys are valid
* All SERIALIZERS keys are valid
* Handler classes are importable
* Event mapper function exists

See Also
--------

* :doc:`../customization/models` - Extend models
* :doc:`../customization/serializers` - Custom serializers
* :doc:`../customization/handlers` - Override business logic
* :doc:`../customization/consumers` - Add custom events
* :doc:`../deployment/production-checklist` - Production settings