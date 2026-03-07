Custom Handlers
===============

The ``EventHandler`` class contains all of the business logic for chat
operations. It is an aggregate of four handler mixins — message, room, session,
and notification — each of which wraps synchronous helper methods with
``sqlite_safe_db_sync_to_async``.

Every domain operation exists as a pair: an **async method** (e.g.
``create_message``) and a **sync helper** (e.g. ``_create_message``).

Creating a Custom EventHandler
-------------------------------

Subclass ``EventHandler`` and override the methods you need:

.. code-block:: python

   # myapp/handlers.py
   from realtime_chat_messaging.utils.handlers import EventHandler


   class CustomEventHandler(EventHandler):
       pass

Register it in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler",
   }

Choosing Which Layer to Override
----------------------------------

Each operation has two entry points. The async method is your primary
customisation surface. The sync helper is the lower-level escape hatch.

**Start with the async method** (e.g. ``create_message``) for the majority of
use cases:

- Side effects after the core logic — push notifications, webhooks, analytics
- Transforming the return value before it reaches the consumer
- Calling external async services (HTTP clients, queues, etc.)
- Lightweight extensions that do not need to touch the DB layer directly

.. code-block:: python

   class CustomEventHandler(EventHandler):

       async def create_message(self, data, user):
           # Core logic runs first — message is created and serialized
           message = await super().create_message(data, user)

           # Your extension runs after — async, no DB concerns
           await self._fire_webhook(message)
           await self._track_analytics("message_sent", user.id)

           return message

**Override the sync helper** (e.g. ``_create_message``) only when you need to:

- Completely replace or heavily restructure the core DB logic
- Run additional synchronous database operations in the same sync context
- Enforce validation that must happen before the record is written
- Discard the default handler logic entirely and reimplement from scratch

.. code-block:: python

   class CustomEventHandler(EventHandler):

       def _create_message(self, data, user):
           # Synchronous context — Django ORM calls are safe here
           content = data.get("content", "")
           if self._is_prohibited(content):
               from django.core.exceptions import ValidationError
               raise ValidationError("Message contains prohibited content")

           # Call super() to retain default logic, or omit to replace it fully
           return super()._create_message(data, user)

.. note::

   Think of the async method as the **extension point** and the sync helper as
   the **replacement point**. If you are adding behaviour, override the async
   method. If you are changing how the core logic works, override the sync helper.
   The sync helper is intentionally lower-level — it is closer to the database
   and further from the consumer.

Async Method Examples
----------------------

Webhook on message send
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import httpx
   from realtime_chat_messaging.utils.handlers import EventHandler


   class CustomEventHandler(EventHandler):

       async def create_message(self, data, user):
           message = await super().create_message(data, user)

           async with httpx.AsyncClient() as client:
               await client.post(
                   "https://hooks.example.com/message",
                   json={
                       "room":   message["room"]["id"],
                       "sender": message["sender"]["username"],
                   },
                   timeout=2.0,
               )

           return message

Analytics on room join
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomEventHandler(EventHandler):

       async def join_room(self, user, room_id):
           result = await super().join_room(user, room_id)
           await self._track_event("room_joined", user.id, room_id)
           return result

       async def _track_event(self, event, user_id, room_id):
           pass  # send to your analytics service

Sync Helper Examples
---------------------

Content moderation in ``_create_message``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from django.core.exceptions import ValidationError
   from realtime_chat_messaging.utils.handlers import EventHandler


   class CustomEventHandler(EventHandler):

       def _create_message(self, data, user):
           content = data.get("content", "")
           banned_words = ["spam", "buy now", "click here"]
           if any(word in content.lower() for word in banned_words):
               raise ValidationError("Message contains prohibited content")
           return super()._create_message(data, user)

Custom join logic in ``_join_room``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The default raises a ``ValidationError`` for GroupChats. Override to implement
approval flows, invite codes, or open joining:

.. code-block:: python

   from django.shortcuts import get_object_or_404
   from django.core.exceptions import ValidationError
   from realtime_chat_messaging.utils.handlers import EventHandler


   class CustomEventHandler(EventHandler):

       def _join_room(self, user, room_id):
           from realtime_chat_messaging.utils.loader import get_model, get_serializer
           Room      = get_model("Room")
           GroupChat = get_model("GroupChat")
           Channel   = get_model("Channel")

           room = get_object_or_404(Room, pk=room_id)

           if isinstance(room, GroupChat):
               if room.join_approval_required:
                   self._create_join_request(user, room)
                   raise ValidationError("Join request submitted. Awaiting approval.")
               room.participants.add(user)

           elif isinstance(room, Channel):
               if not room.is_public:
                   raise ValidationError("Channel is private.")
               room.subscribers.add(user)

           else:
               raise ValidationError("Cannot join a one-to-one chat.")

           return get_serializer("RoomPolymorphicSerializer")(room).data

Custom actions in ``_modify_room``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add support for extra ``action`` types on a custom room model:

.. code-block:: python

   class CustomEventHandler(EventHandler):

       def _modify_room(self, data, room):
           action     = data.get("action")
           field_data = data.get("data", {})

           if action == "set_welcome_message":
               if hasattr(room, "welcome_message"):
                   room.welcome_message = field_data.get("welcome_message", "")
                   room.save()
               from realtime_chat_messaging.utils.loader import get_serializer
               return get_serializer("RoomPolymorphicSerializer")(room).data

           # Fall back to default for all standard actions
           return super()._modify_room(data, room)

Adding Sync DB Calls Inside an Async Override
----------------------------------------------

If you override an async method and need to make additional DB calls inside it,
wrap them with ``sqlite_safe_db_sync_to_async``:

.. code-block:: python

   from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async


   class CustomEventHandler(EventHandler):

       async def create_message(self, data, user):
           message = await super().create_message(data, user)
           room_name = await self._get_room_name(message["room"]["id"])
           return message

       @sqlite_safe_db_sync_to_async
       def _get_room_name(self, room_id):
           from realtime_chat_messaging.utils.loader import get_model
           return get_model("Room").objects.get(pk=room_id).name

Customising the ExceptionHandler
----------------------------------

Override to catch custom exception types or change the error response format:

.. code-block:: python

   # myapp/exceptions.py
   from realtime_chat_messaging.utils.decorators import ExceptionHandler
   from functools import wraps


   class CustomExceptionHandler(ExceptionHandler):

       @classmethod
       def exception_handler_decorator(cls, func):
           wrapped = super().exception_handler_decorator(func)

           @wraps(func)
           async def wrapper(self, *args, **kwargs):
               try:
                   return await wrapped(self, *args, **kwargs)
               except MyCustomException as exc:
                   await cls.send_error(self, str(exc), func, exc, code=4007)
           return wrapper

Register it:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EXCEPTION_HANDLER_CLASS": "myapp.exceptions.CustomExceptionHandler",
   }

The ``send_error`` classmethod signature::

   ExceptionHandler.send_error(consumer, detail, func, exc, code=4003)

- ``consumer`` — the WebSocket consumer instance.
- ``detail`` — string, list, or dict shown to the client.
- ``func`` — the function where the error originated (for logging).
- ``exc`` — the exception instance (full traceback is logged).
- ``code`` — custom WebSocket application close code (default ``4003``).

Available Methods to Override
------------------------------

All async/sync pairs are listed below. For each operation, **prefer overriding
the async method** for extensions and side effects. Override the sync helper
only when you need to replace or heavily modify the core DB logic.

**Message**

.. list-table::
   :header-rows: 1
   :widths: 40 40 20

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

**Room**

.. list-table::
   :header-rows: 1
   :widths: 40 40 20

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

**Session**

.. list-table::
   :header-rows: 1
   :widths: 40 40 20

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

**Notification**

.. list-table::
   :header-rows: 1
   :widths: 40 40 20

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