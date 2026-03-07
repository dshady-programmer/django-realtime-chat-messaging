Architecture
============

Understanding how the package is structured will help you know exactly where to
hook in your customisations and what happens at each stage of a WebSocket event.

High-Level Overview
-------------------

.. code-block:: text

   Client (browser / mobile)
        │
        │  WebSocket  ws://<host>/messaging/
        ▼
   ASGI Stack (Daphne / Uvicorn)
        │
        │  Authentication middleware populates scope["user"]
        ▼
   ChatMessagingConsumer   (channels.generic.websocket.AsyncWebsocketConsumer)
        │
        ├── receive()  ──►  EVENT_MAPPER  ──►  handler method
        │
        ├── Permission Decorators  (can_send_message_to_room, can_access_room, …)
        │        │
        │        └── PermissionHandler  (async wrapper)
        │                   └── PermissionHelperMixin  (sync DB logic)
        │
        └── EventHandler  (async wrapper)
                   ├── MessageHandlerMixin  (async)
                   │        └── MessageHelperMixins  (sync DB logic)
                   ├── RoomHandlerMixin  (async)
                   │        └── RoomHelperMixins  (sync DB logic)
                   ├── SessionHandlerMixin  (async)
                   │        └── SessionHelperMixins  (sync DB logic)
                   └── ChatNotificationHandlerMixin  (async)
                            └── ChatNotificationHelperMixins  (sync DB logic)

Request Lifecycle
-----------------

Every client message follows this exact path:

1. **Receive** — ``ChatMessagingConsumer.receive()`` parses the JSON payload and
   reads ``event_type``.

2. **Route** — The ``EVENT_MAPPER`` function returns a dictionary mapping event
   type strings to consumer methods. The correct method is looked up and called.

3. **Permission check** — Most handler methods are decorated with one or more
   permission decorators (e.g. ``@can_send_message_to_room``). These decorators
   call the async ``PermissionHandler``, which wraps synchronous DB checks with
   ``sqlite_safe_db_sync_to_async``. If the check fails, ``PermissionDenied`` is
   raised and the ``ExceptionHandler`` decorator converts it to a structured error
   response (code ``4002``). If the check passes, the resolved ``room`` object is
   injected into the handler as a keyword argument.

4. **Exception handling** — Every handler method is also decorated with
   ``@ExceptionHandler.exception_handler_decorator``. This catches all Django,
   DRF, and generic exceptions and converts them into structured JSON error
   responses so the WebSocket connection stays open.

5. **Business logic** — The handler method calls the relevant ``EventHandler``
   method (e.g. ``EventHandler.create_message()``). The ``EventHandler`` is an
   aggregate of async handler mixins, each of which wraps synchronous helper
   mixins with ``sqlite_safe_db_sync_to_async``.

6. **Broadcast** — The result is broadcast via ``send_group()``, which calls
   ``channel_layer.group_send()``. The ``broadcast_group()`` consumer method
   receives the message from the channel layer and forwards it to the client
   WebSocket.



The Polymorphic Room Model
--------------------------

All room types (``OneToOneChat``, ``GroupChat``, ``Channel``) inherit from a
single ``Room`` base model that uses ``django-polymorphic``. This means you can
query all rooms a user belongs to in a single database query:

.. code-block:: python

   from realtime_chat_messaging.models import Room

   rooms = Room.objects.filter(
       Q(onetoonechat__participants=user) |
       Q(groupchat__participants=user) |
       Q(channel__subscribers=user)
   )
   # Returns OneToOneChat, GroupChat, and Channel instances correctly typed

The ``RoomListPolymorphicSerializer`` and ``RoomPolymorphicSerializer`` handle
serialization across room types using ``django-rest-polymorphic``, adding a
``"type"`` field (``"OneToOneChat"``, ``"GroupChat"``, or ``"Channel"``) to every
serialized room so clients can render them appropriately.

The Settings System
-------------------

Settings are loaded lazily via a ``Settings`` proxy object. On first access of
any attribute the user's ``REALTIME_CHAT_MESSAGING`` dictionary is read from
Django settings, validated, merged with defaults, and cached. Subsequent accesses
use the cached value. During tests, Django's ``setting_changed`` signal triggers a
full reload so ``@override_settings`` works correctly.

All model paths are also registered as individual Django settings (e.g.
``settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL``) so Django's swappable model
system can reference them in migrations.

Async/Sync Boundary
--------------------

Django Channels consumers run in an async event loop. All database operations
must be run synchronously in a thread pool. The package wraps every DB function
with ``sqlite_safe_db_sync_to_async``, a thin wrapper around
``database_sync_to_async`` that also calls ``connection.ensure_connection()``
before execution. This prevents a specific ``AttributeError`` on SQLite when
running under Django 6.0 where the connection object can be ``None`` at the
start of a thread.

This wrapper is harmless on PostgreSQL and MySQL. If you override any helper
methods that hit the database, wrap them the same way:

.. code-block:: python

   from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async

   @sqlite_safe_db_sync_to_async
   def my_db_function(arg):
       return MyModel.objects.get(pk=arg)
