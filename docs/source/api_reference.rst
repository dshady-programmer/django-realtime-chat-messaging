API Reference
=============

This page documents the public interfaces of every major component. Use this as
a reference when subclassing or extending the package.

EventHandler
------------

``realtime_chat_messaging.utils.handlers.EventHandler``

The aggregate handler combining all domain mixins. Each operation exists as an
async/sync pair. **Override the async method** for extensions, side effects, and
async integrations. **Override the sync helper** only when you need to replace or
heavily modify the core DB logic. See :doc:`custom_handlers` for full guidance.

**Message methods**

.. list-table::
   :header-rows: 1
   :widths: 42 42 16

   * - Async method *(extend here)*
     - Sync helper *(replace here)*
     - Returns
   * - ``create_message(data, user)``
     - ``_create_message(data, user)``
     - ``dict``
   * - ``react_to_message(data, user)``
     - ``_react_to_message(data, user)``
     - ``dict``
   * - ``message_acknowledged(user, message_id)``
     - ``_message_acknowledged(user, message_id)``
     - ``dict``
   * - ``modify_message(data)``
     - ``_modify_message(data)``
     - ``dict``
   * - ``create_read_receipt(user, message_id)``
     - ``_create_read_receipt(user, message_id)``
     - ``tuple``
   * - ``retreive_messages(room, data)``
     - ``_retreive_messages(room, data)``
     - ``dict``

**Room methods**

.. list-table::
   :header-rows: 1
   :widths: 42 42 16

   * - Async method *(extend here)*
     - Sync helper *(replace here)*
     - Returns
   * - ``create_room(user, data)``
     - ``_create_room(user, data)``
     - ``dict``
   * - ``list_rooms(user)``
     - ``_list_rooms(user)``
     - ``list``
   * - ``retreive_room(room)``
     - ``_retreive_room(room)``
     - ``dict``
   * - ``add_members_to_room(user_ids, room)``
     - ``_add_members_to_room(user_ids, room)``
     - ``tuple``
   * - ``remove_members_from_room(user_ids, room, session_user)``
     - ``_remove_members_from_room(user_ids, room, session_user)``
     - ``tuple``
   * - ``leave_room(user, room)``
     - ``_leave_room(user, room)``
     - ``dict | None``
   * - ``join_room(user, room_id)``
     - ``_join_room(user, room_id)``
     - ``dict``
   * - ``modify_room(data, room)``
     - ``_modify_room(data, room)``
     - ``dict``

**Session methods**

.. list-table::
   :header-rows: 1
   :widths: 42 42 16

   * - Async method *(extend here)*
     - Sync helper *(replace here)*
     - Returns
   * - ``register_session(user, channel_name)``
     - ``_register_session(user, channel_name)``
     - ``Session``
   * - ``get_active_sessions(user_id)``
     - ``_get_active_sessions(user_id)``
     - ``list[str]``
   * - ``get_expired_sessions(user_id)``
     - ``_get_expired_sessions(user_id)``
     - ``list[str]``
   * - ``update_session(session)``
     - ``_update_session(session)``
     - ``None``

**Notification methods**

.. list-table::
   :header-rows: 1
   :widths: 42 42 16

   * - Async method *(extend here)*
     - Sync helper *(replace here)*
     - Returns
   * - ``get_and_group_chat_notifications(user)``
     - ``_get_and_group_chat_notifications(user)``
     - ``dict``
   * - ``create_chat_notification(message, type, user)`` *(static)*
     - called synchronously inside ``_create_message``
     - ``list | None``
   * - ``update_chat_notification(message_id, user, many)`` *(static)*
     - called synchronously inside ``_message_acknowledged``
     - ``QuerySet``

PermissionHandler
-----------------

``realtime_chat_messaging.permissions.handlers.PermissionHandler``

All methods are async wrappers around synchronous ``_have_*`` helpers. All
return ``(bool, Room)`` except ``have_message_permission`` which returns ``bool``.

.. list-table::
   :header-rows: 1
   :widths: 55 45

   * - Async method
     - Returns
   * - ``have_room_permission(user, room_id)``
     - ``(bool, Room)``
   * - ``have_message_permission(user, message_id)``
     - ``bool``
   * - ``is_message_sender(user, message_id)``
     - ``(bool, Room)``
   * - ``have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase)``
     - ``(bool, Room)``
   * - ``have_send_message_permission(user, data)``
     - ``(bool, Room)``
   * - ``have_admin_privileges(user, room_id, action)``
     - ``(bool, Room)``

ExceptionHandler
----------------

``realtime_chat_messaging.utils.decorators.ExceptionHandler``

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Method
     - Description
   * - ``exception_handler_decorator(func)`` *(classmethod)*
     - Decorator wrapping async consumer methods. Catches all Django/DRF exceptions and sends structured error JSON.
   * - ``send_error(consumer, detail, func, exc, code=4003)``
     - Send a structured error payload to the client and log the traceback.

**Exception → code mapping**:

- ``DRFValidationError`` → ``4003``
- ``DjangoValidationError`` → ``4003``
- ``IntegrityError`` → ``4005``
- ``ObjectDoesNotExist`` → ``4004``
- ``Http404`` → ``4004``
- ``PermissionDenied`` → ``4002``
- ``Exception`` (all others) → ``4006``

ChatMessagingConsumer
---------------------

``realtime_chat_messaging.consumers.ChatMessagingConsumer``

**Lifecycle methods** (always call ``super()`` when overriding):

- ``connect()`` — authenticate, cleanup expired sessions, set up groups
- ``disconnect(close_code)`` — cleanup expired sessions
- ``receive(text_data, bytes_data)`` — parse JSON, route via EVENT_MAPPER

**Group helpers**:

- ``send_group(group, event_type, data)`` — broadcast to a channel group
- ``add_channel_to_group(group, user_id=None)`` — add all user sessions to a group
- ``discard_channel_from_group(group, user_id=None)`` — remove all user sessions from a group

**Session helpers**:

- ``channel_setup()`` — restore group memberships and register session
- ``channel_cleanup()`` — remove expired sessions from groups

**Consumer attributes** (available after ``connect()``):

- ``self.user`` — authenticated Django user
- ``self.session`` — current ``Session`` instance
- ``self.channel_name`` — this connection's channel name
- ``self.channel_layer`` — Django Channels layer

Loader Utilities
----------------

``realtime_chat_messaging.utils.loader``

Functions for dynamically resolving configured models and serializers:

.. code-block:: python

   from realtime_chat_messaging.utils.loader import get_model, get_serializer

   Message = get_model("Message")        # Returns configured Message class
   Serializer = get_serializer("MessageSerializer")  # Returns configured class

- ``get_model(name: str) → Model`` — look up a model by its settings key
- ``get_serializer(name: str) → Serializer`` — look up a serializer by its settings key
- ``import_and_verify_type_class(klass, repr, class_instance=None)`` — import and validate a class from a dotted path
- ``import_and_verify_type_function(func, repr)`` — import and validate a function from a dotted path
- ``clear_caches()`` — clear model and serializer caches (used in tests)

Settings
--------

``realtime_chat_messaging.conf.realtime_chat_settings``

The global settings instance. Access any setting as an attribute:

.. code-block:: python

   from realtime_chat_messaging.conf import realtime_chat_settings

   threshold = realtime_chat_settings.INACTIVITY_THRESHOLD
   soft_delete = realtime_chat_settings.MESSAGE_SOFT_DELETE

See :doc:`settings` for all available settings and their defaults.

Cache Utilities
---------------

``realtime_chat_messaging.utils.cache_utils``

Async-safe functions for user group membership cache:

.. code-block:: python

   from realtime_chat_messaging.utils.cache_utils import (
       fetch_user_groups,
       update_user_groups,
       add_group_to_user_groups,
       remove_group_from_user_groups,
   )

All functions are decorated with ``@sync_to_async`` and accept ``user_id`` as a
string. Cache keys follow the format ``user:<user_id>:groups`` with no
expiration. Values are JSON-serialised lists of group name strings.

WebSocket Close Codes
----------------------

See :doc:`error_codes` for the full table. Summary:

- ``4001`` — unauthenticated (connection closed)
- ``4002`` — permission denied
- ``4003`` — validation error
- ``4004`` — resource not found
- ``4005`` — integrity/constraint error
- ``4006`` — internal server error