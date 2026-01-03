Settings Reference
==================

Complete reference for all configuration options in Django Realtime Chat Messaging. All settings are prefixed with ``REALTIME_CHAT_MESSAGING`` and placed in your ``settings.py``.

Basic Configuration
-------------------

Settings are configured as a dictionary:

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': True,
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
       },
       # ... other settings
   }

Core Settings
-------------

MESSAGE_SOFT_DELETE
~~~~~~~~~~~~~~~~~~~

Controls whether message deletion is soft (marks as deleted) or hard (removes from database).

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': True,
   }

:Type: ``bool``
:Default: ``False``
:Description: When ``True``, deleted messages are marked with ``is_deleted=True`` but remain in database. When ``False``, messages are permanently deleted.

.. warning::
   When using soft delete, your frontend must filter out ``is_deleted=True`` messages. The package returns all messages regardless of deletion status.

**Use Cases:**

- Compliance/audit requirements (keep all message history)
- User "undo" functionality
- Message recovery features

**Example with soft delete:**

.. code-block:: python

   # Messages are marked as deleted
   message.is_deleted = True
   message.save()
   
   # Filter in queries
   active_messages = Message.objects.filter(is_deleted=False)

Customization Settings
----------------------

SERIALIZERS
~~~~~~~~~~~

Override default serializers for custom behavior.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
           'MessageSerializer': 'myapp.serializers.CustomMessageSerializer',
       },
   }

:Type: ``dict``
:Default: Uses package's built-in serializers
:Description: Map of serializer names to custom serializer classes (as strings).

**Available Serializer Keys:**

- ``UserSerializer``
- ``OneToOneChatListSerializer``
- ``GroupChatListSerializer``
- ``ChannelListSerializer``
- ``RoomListPolymorphicSerializer``
- ``OneToOneChatSerializer``
- ``GroupChatSerializer``
- ``ChannelSerializer``
- ``RoomPolymorphicSerializer``
- ``ReadReceiptSerializer``
- ``ReactionSerializer``
- ``MessageMediaAssetSerializer``
- ``MessageSerializer``
- ``ChatNotificationSerializer``

**Example: Custom User Serializer**

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
           fields = ['id', 'username', 'email', 'avatar_url', 'is_online']

       def get_avatar_url(self, obj):
           return obj.profile.avatar.url if hasattr(obj, 'profile') else None

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
       },
   }

MODELS
~~~~~~

Override default models for custom functionality.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'MODELS': {
           'Message': 'myapp.models.CustomMessage',
       },
   }

:Type: ``dict``
:Default: Uses package's built-in models
:Description: Map of model names to custom model classes (as strings).

**Available Model Keys:**

- ``Room``
- ``OneToOneChat``
- ``GroupChat``
- ``Channel``
- ``Message``
- ``ReadReceipt``
- ``ChatNotification``
- ``Reaction``
- ``MessageMediaAsset``

.. important::
   When overriding models, you typically need to override related serializers and potentially permissions. See :doc:`customization/abstract-models` for details.

EVENT_HANDLERS
~~~~~~~~~~~~~~

Override default event handlers for custom business logic.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'EVENT_HANDLERS': {
           'create_message': 'myapp.handlers.custom_create_message',
       },
   }

:Type: ``dict``
:Default: Uses package's built-in handlers
:Description: Map of handler names to custom handler functions (as strings).

**Available Handler Keys:**

- ``get_and_group_chat_notifications``
- ``create_message``
- ``react_to_message``
- ``message_acknowledged``
- ``modify_message``
- ``create_read_receipt``
- ``create_room``
- ``list_rooms``
- ``retreive_room``
- ``add_members_to_room``
- ``remove_members_from_room``
- ``leave_room``
- ``join_room``
- ``retreive_messages``
- ``modify_room``

**Example: Custom Message Creation with File Upload**

.. code-block:: python

   # myapp/handlers.py
   from channels.db import database_sync_to_async
   from realtime_chat_messaging.utils.event_handlers import create_message as default_create_message
   import boto3

   @database_sync_to_async
   def custom_create_message(data, user):
       # Handle file upload to S3
       if 'file' in data:
           s3 = boto3.client('s3')
           file_url = upload_to_s3(data['file'])
           data['extra_fields'] = data.get('extra_fields', {})
           data['extra_fields']['media'] = [{
               'media_url': file_url,
               'media_type': 'file',
               'file_size': data['file'].size,
               'mime_type': data['file'].content_type,
           }]
           data.pop('file')
       
       # Call default handler
       return await default_create_message(data, user)

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'EVENT_HANDLERS': {
           'create_message': 'myapp.handlers.custom_create_message',
       },
   }

PERMISSIONS
~~~~~~~~~~~

Override permission checking functions.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.custom_room_permission',
       },
   }

:Type: ``dict``
:Default: Uses package's built-in permissions
:Description: Map of permission check names to custom functions (as strings).

**Available Permission Keys:**

- ``have_room_permission``
- ``have_message_permission``
- ``is_message_sender``
- ``have_room_permissions_to_add_or_remove_members``
- ``have_send_message_permission``
- ``have_admin_privileges``

.. important::
   Custom permission functions must have the same signature as the default functions and return the same types. See :doc:`customization/permissions` for details.

**Example: Custom Permission with Paid Tier**

.. code-block:: python

   # myapp/permissions.py
   from channels.db import database_sync_to_async
   from realtime_chat_messaging.permissions.helpers import have_room_permission as default_check

   @database_sync_to_async
   def custom_room_permission(user, room_id):
       # Check default permission
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           return False, room
       
       # Additional check: premium rooms require subscription
       if hasattr(room, 'is_premium') and room.is_premium:
           if not user.profile.is_subscribed:
               return False, room
       
       return True, room

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.custom_room_permission',
       },
   }

EVENT_MAPPER
~~~~~~~~~~~~

Extend or override the event-to-handler mapping.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'EVENT_MAPPER': 'myapp.consumers.custom_event_mapper',
   }

:Type: ``str`` (callable path)
:Default: ``realtime_chat_messaging.variables.consumers.map_event_type_to_handlers``
:Description: Function that returns a dictionary mapping event types to handler methods.

**Example: Adding Custom Events**

.. code-block:: python

   # myapp/consumers.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers

   def custom_event_mapper(consumer_instance):
       # Get default mappings
       handlers = map_event_type_to_handlers(consumer_instance)
       
       # Add custom events
       handlers.update({
           'user.status': consumer_instance.handle_user_status,
           'message.pin': consumer_instance.handle_message_pin,
       })
       
       # Override existing event
       handlers['message.typing'] = consumer_instance.custom_typing_handler
       
       return handlers

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'EVENT_MAPPER': 'myapp.consumers.custom_event_mapper',
   }

   # myapp/consumers.py (extend the consumer)
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from realtime_chat_messaging.utils.decorators import ExceptionHandler

   class CustomChatConsumer(ChatMessagingConsumer):
       @ExceptionHandler.exception_handler_decorator
       async def handle_user_status(self, data):
           # Custom implementation
           pass
       
       @ExceptionHandler.exception_handler_decorator
       async def handle_message_pin(self, data):
           # Custom implementation
           pass

EXCEPTION_HANDLER_CLASS
~~~~~~~~~~~~~~~~~~~~~~~

Override the exception handler class.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'EXCEPTION_HANDLER_CLASS': 'myapp.handlers.CustomExceptionHandler',
   }

:Type: ``str`` (class path)
:Default: ``realtime_chat_messaging.utils.exception_handlers.ExceptionHandler``
:Description: Custom exception handler class for WebSocket errors.

**Example: Custom Exception Handler with Logging**

.. code-block:: python

   # myapp/handlers.py
   from realtime_chat_messaging.utils.exception_handlers import ExceptionHandler
   import logging
   import sentry_sdk

   logger = logging.getLogger(__name__)

   class CustomExceptionHandler(ExceptionHandler):
       @classmethod
       async def send_error(cls, consumer, detail, func, exc, code=4003):
           # Log to external service
           logger.error(f"WebSocket error in {func.__name__}: {exc}")
           sentry_sdk.capture_exception(exc)
           
           # Call parent method
           return await super().send_error(consumer, detail, func, exc, code)

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'EXCEPTION_HANDLER_CLASS': 'myapp.handlers.CustomExceptionHandler',
   }

Configuration Examples
----------------------

Minimal Configuration
~~~~~~~~~~~~~~~~~~~~~

Using all defaults:

.. code-block:: python

   # No REALTIME_CHAT_MESSAGING needed - uses all defaults

Basic Customization
~~~~~~~~~~~~~~~~~~~

Adding soft delete and custom user serializer:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': True,
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
       },
   }

Advanced Customization
~~~~~~~~~~~~~~~~~~~~~~

Full customization with multiple overrides:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': True,
       
       'SERIALIZERS': {
           'UserSerializer': 'myapp.serializers.CustomUserSerializer',
           'MessageSerializer': 'myapp.serializers.CustomMessageSerializer',
       },
       
       'EVENT_HANDLERS': {
           'create_message': 'myapp.handlers.custom_create_message',
           'create_room': 'myapp.handlers.custom_create_room',
       },
       
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.custom_room_permission',
       },
       
       'EVENT_MAPPER': 'myapp.consumers.custom_event_mapper',
       'EXCEPTION_HANDLER_CLASS': 'myapp.handlers.CustomExceptionHandler',
   }

Environment-Specific Configuration
-----------------------------------

Development
~~~~~~~~~~~

.. code-block:: python

   # settings.py
   if DEBUG:
       REALTIME_CHAT_MESSAGING = {
           'MESSAGE_SOFT_DELETE': True,  # Keep all messages for debugging
       }

Production
~~~~~~~~~~

.. code-block:: python

   # settings.py
   if not DEBUG:
       REALTIME_CHAT_MESSAGING = {
           'MESSAGE_SOFT_DELETE': False,  # Hard delete to save space
           'EXCEPTION_HANDLER_CLASS': 'myapp.handlers.ProductionExceptionHandler',
       }

Common Patterns
---------------

WhatsApp-Style Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': True,  # Messages can be "deleted for me"
       'SERIALIZERS': {
           'MessageSerializer': 'myapp.serializers.WhatsAppMessageSerializer',
       },
   }

Slack-Style Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       'MESSAGE_SOFT_DELETE': False,  # Messages truly deleted
       'EVENT_HANDLERS': {
           'create_message': 'myapp.handlers.slack_style_message_handler',
       },
   }

Validating Configuration
------------------------

The package automatically validates settings on startup. Invalid configurations will raise ``ImproperlyConfigured``.

.. code-block:: python

   # This will raise an error
   REALTIME_CHAT_MESSAGING = {
       'SERIALIZERS': 'not-a-dict',  # Error: must be a dictionary
   }

Best Practices
--------------

1. **Start with defaults**: Only override what you need
2. **Test customizations**: Each override should have tests
3. **Document your overrides**: Comment why you override defaults
4. **Keep consistency**: If you override a serializer, consider related serializers
5. **Version control**: Track configuration changes carefully

Next Steps
----------

- :doc:`customization/serializers` - Learn to customize serializers
- :doc:`customization/event-handlers` - Override event handlers
- :doc:`customization/permissions` - Implement custom permissions
- :doc:`customization/abstract-models` - Extend models