Custom Consumer
===============

The ``ChatMessagingConsumer`` handles the WebSocket lifecycle and event routing.
Extend it to add new event types, override connection behaviour, or add
cross-cutting concerns like rate limiting, analytics, or logging.

Creating a Custom Consumer
---------------------------

Subclass ``ChatMessagingConsumer``:

.. code-block:: python

   # myapp/consumers.py
   from realtime_chat_messaging.consumers import ChatMessagingConsumer


   class CustomChatConsumer(ChatMessagingConsumer):
       pass

Register it in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "CHAT_CONSUMER_CLASS": "myapp.consumers.CustomChatConsumer",
   }

Available Methods to Override
------------------------------

The following methods are available on ``ChatMessagingConsumer``. Understanding
each one is important before deciding which to override.

**Lifecycle methods**

Always call ``super()`` when overriding any lifecycle method. These methods
handle authentication, session registration, group membership, and notification
dispatch. Omitting ``super()`` breaks the connection entirely.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Method
     - What it does
   * - ``connect()``
     - Authenticates the user, registers the session in the DB, fetches
       ``user_groups`` from cache and adds the new channel name to each group,
       dispatches pending ``chat.notifications``. This is the entry point for
       the entire connection setup.
   * - ``disconnect(close_code)``
     - Cleans up expired sessions and removes their channel names from all
       channel layer groups. Called whether the client or server closes the
       connection.
   * - ``receive(text_data, bytes_data)``
     - Parses the incoming JSON payload, extracts ``event_type``, looks it up
       in the event map returned by ``EVENT_MAPPER``, and calls the matching
       handler method. Override this to intercept all events before routing
       (e.g. rate limiting, logging).

**Built-in event handler methods**

These are the methods the consumer calls internally when a matching event
arrives. Each is async and decorated with
``@ExceptionHandler.exception_handler_decorator``. You can override any of
them to intercept specific events, but it is usually better to override the
corresponding ``EventHandler`` method instead (see :doc:`custom_handlers`).

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Method
     - Handles event
   * - ``receive_message_send(data)``
     - ``message.send``
   * - ``receive_message_acknowledged(data)``
     - ``message.acknowledged``
   * - ``receive_message_read(data)``
     - ``message.read``
   * - ``receive_message_react(data)``
     - ``message.react``
   * - ``receive_message_typing(data)``
     - ``message.typing``
   * - ``receive_message_modify(data)``
     - ``message.modify``
   * - ``receive_room_create(data)``
     - ``room.create``
   * - ``receive_room_list(data)``
     - ``room.list``
   * - ``receive_room_info(data)``
     - ``room.info``
   * - ``receive_room_messages(data)``
     - ``room.messages``
   * - ``receive_room_join(data)``
     - ``room.join``
   * - ``receive_room_leave(data)``
     - ``room.leave``
   * - ``receive_room_add_members(data)``
     - ``room.add_members``
   * - ``receive_room_remove_members(data)``
     - ``room.remove_members``
   * - ``receive_room_modify(data)``
     - ``room.modify``
   * - ``receive_session_heartbeat(data)``
     - ``session.heartbeat``

**Group and channel helpers**

These are utility methods available on the consumer instance. Call them inside
custom handler methods to broadcast to groups or manage channel membership.

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Method
     - What it does
   * - ``send_group(group, event_type, data)``
     - Broadcast a payload to every channel name in a channel layer group.
       The client receives ``{"eventType": event_type, "data": data}``.
   * - ``add_channel_to_group(group, user_id=None)``
     - Query all active sessions for ``user_id`` (or the current user if
       omitted) and add each session's channel name to ``group``. This is
       what wires a user into a room for real-time delivery.
   * - ``discard_channel_from_group(group, user_id=None)``
     - Remove all active sessions for a user from ``group``.
   * - ``channel_setup()``
     - Fetch ``user_groups`` from cache and add the current channel name to
       each group. Called internally by ``connect()``.
   * - ``channel_cleanup()``
     - Find and remove expired sessions from all their groups. Called
       internally by ``connect()`` and ``disconnect()``.

**Consumer attributes**

These attributes are available on ``self`` after ``connect()`` completes:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Attribute
     - Value
   * - ``self.user``
     - The authenticated Django user for this connection.
   * - ``self.session``
     - The current ``Session`` model instance.
   * - ``self.channel_name``
     - The unique channel name Django Channels assigned to this connection.
       Changes on every reconnect.
   * - ``self.channel_layer``
     - The configured channel layer instance (in-memory or Redis).
   * - ``self.permission_handler``
     - An instance of the configured ``PermissionHandler`` class, ready to
       use inside custom handler methods.

The Event Mapper
-----------------

The event mapper is a function that returns a dictionary mapping event type
strings to the handler methods that should be called when that event arrives.
When ``receive()`` is called with an incoming payload, it calls the mapper to
get the current event map, then looks up the ``event_type`` key and calls the
corresponding method.

The default mapper is ``map_event_type_to_handlers`` from
``realtime_chat_messaging.variables.consumers``. It returns the following
mapping:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Event type string
     - Handler method called
   * - ``"message.send"``
     - ``consumer.receive_message_send``
   * - ``"message.acknowledged"``
     - ``consumer.receive_message_acknowledged``
   * - ``"message.read"``
     - ``consumer.receive_message_read``
   * - ``"message.react"``
     - ``consumer.receive_message_react``
   * - ``"message.typing"``
     - ``consumer.receive_message_typing``
   * - ``"message.modify"``
     - ``consumer.receive_message_modify``
   * - ``"room.create"``
     - ``consumer.receive_room_create``
   * - ``"room.list"``
     - ``consumer.receive_room_list``
   * - ``"room.info"``
     - ``consumer.receive_room_info``
   * - ``"room.messages"``
     - ``consumer.receive_room_messages``
   * - ``"room.join"``
     - ``consumer.receive_room_join``
   * - ``"room.leave"``
     - ``consumer.receive_room_leave``
   * - ``"room.add_members"``
     - ``consumer.receive_room_add_members``
   * - ``"room.remove_members"``
     - ``consumer.receive_room_remove_members``
   * - ``"room.modify"``
     - ``consumer.receive_room_modify``
   * - ``"session.heartbeat"``
     - ``consumer.receive_session_heartbeat``

Customizing the Event Mapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provide a custom mapper function to add new events, restrict existing ones, or
replace a built-in handler with your own. The function receives the consumer
instance and must return a dictionary.

Always call ``map_event_type_to_handlers(consumer)`` first to get the default
map, then modify it. This ensures new events added in future releases are
picked up automatically.

**Adding new events:**

.. code-block:: python

   # myapp/events.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers


   def custom_event_mapper(consumer):
       events = map_event_type_to_handlers(consumer)

       # Register custom handler methods on the consumer
       events["message.pin"]  = consumer.receive_message_pin
       events["message.flag"] = consumer.receive_message_flag

       return events

**Restricting events (blocking a built-in event entirely):**

.. code-block:: python

   def custom_event_mapper(consumer):
       events = map_event_type_to_handlers(consumer)

       # Prevent clients from joining rooms via the WebSocket
       # (e.g. joins are handled through your REST API instead)
       del events["room.join"]

       return events

**Replacing a built-in handler with a custom one:**

.. code-block:: python

   def custom_event_mapper(consumer):
       events = map_event_type_to_handlers(consumer)

       # Replace the default room.create handler with your own
       events["room.create"] = consumer.receive_room_create_custom

       return events

Register the mapper in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "CHAT_CONSUMER_CLASS": "myapp.consumers.CustomChatConsumer",
       "EVENT_MAPPER": "myapp.events.custom_event_mapper",
   }

.. note::

   Any event type not present in the map is silently ignored when received.
   This means deleting a key from the map is a safe and clean way to disable
   a built-in event without raising errors on the client.

Overriding ``connect`` and ``disconnect``
------------------------------------------

Always call ``super()`` to preserve authentication, session setup, and
notification dispatch:

.. code-block:: python

   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from django.utils import timezone
   import logging

   logger = logging.getLogger(__name__)


   class CustomChatConsumer(ChatMessagingConsumer):

       async def connect(self):
           await super().connect()   # authentication + session setup
           self.connected_at = timezone.now()
           logger.info(f"User {self.user.username} connected")

       async def disconnect(self, code):
           if hasattr(self, "connected_at"):
               duration = (timezone.now() - self.connected_at).total_seconds()
               logger.info(f"User {self.user.username} disconnected after {duration:.0f}s")
           await super().disconnect(code)

Adding New Event Handlers
--------------------------

New event handler methods must be ``async`` and follow the same signature
pattern as the built-in handlers. Use ``@ExceptionHandler.exception_handler_decorator``
for consistent error handling, and add permission checks as appropriate:

.. code-block:: python

   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from realtime_chat_messaging.utils.decorators import ExceptionHandler
   from channels.db import database_sync_to_async


   class CustomChatConsumer(ChatMessagingConsumer):

       @ExceptionHandler.exception_handler_decorator
       async def receive_message_pin(self, data):
           """
           Pin a message in a room.
           Event: message.pin
           Data: {"room_id": "<uuid>", "message_id": "<uuid>"}
           """
           room_id    = data.get("room_id")
           message_id = data.get("message_id")

           is_permitted, room = await self.permission_handler.have_admin_privileges(
               self.user, room_id, "pin"
           )
           if not is_permitted:
               from django.core.exceptions import PermissionDenied
               raise PermissionDenied("Only admins can pin messages")

           await self._pin_message(message_id)

           await self.send_group(f"group-{room_id}", "message.pinned", {
               "message_id": message_id,
               "pinned_by": self.user.username,
           })

       @database_sync_to_async
       def _pin_message(self, message_id):
           from realtime_chat_messaging.utils.loader import get_model
           get_model("Message").objects.filter(pk=message_id).update(is_pinned=True)

Then register the new event in your custom mapper:

.. code-block:: python

   # myapp/events.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers

   def custom_event_mapper(consumer):
       events = map_event_type_to_handlers(consumer)
       events["message.pin"] = consumer.receive_message_pin
       return events

Adding Rate Limiting
---------------------

Override ``receive()`` to intercept all events before routing:

.. code-block:: python

   import json
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from django.utils import timezone


   class CustomChatConsumer(ChatMessagingConsumer):

       RATE_LIMIT = 30      # max events
       RATE_WINDOW = 60     # per 60 seconds

       async def connect(self):
           await super().connect()
           self._timestamps = []

       async def receive(self, text_data=None, bytes_data=None):
           data = json.loads(text_data)

           if data.get("event_type") == "message.send":
               if not self._check_rate():
                   await self.send(text_data=json.dumps({
                       "error": {
                           "code": 4029,
                           "detail": f"Rate limit: max {self.RATE_LIMIT} messages per {self.RATE_WINDOW}s"
                       }
                   }))
                   return

           await super().receive(text_data)

       def _check_rate(self):
           now    = timezone.now().timestamp()
           cutoff = now - self.RATE_WINDOW
           self._timestamps = [t for t in self._timestamps if t > cutoff]
           if len(self._timestamps) >= self.RATE_LIMIT:
               return False
           self._timestamps.append(now)
           return True

Using ``send_group`` in Custom Handlers
----------------------------------------

The ``send_group`` helper broadcasts to a channel layer group. Use the group
naming convention the package already uses so your custom events fit the same
delivery model:

.. code-block:: python

   # Broadcast to all members of a room
   await self.send_group(f"group-{room_id}", "custom.event", {"key": "value"})

   # Send to all active connections of a specific user (all their devices)
   await self.send_group(f"user-{self.user.id}", "custom.event", {"key": "value"})

The client receives:

.. code-block:: json

   {
     "eventType": "custom.event",
     "data": {"key": "value"}
   }