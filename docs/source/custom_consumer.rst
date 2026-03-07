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
   import json


   class CustomChatConsumer(ChatMessagingConsumer):

       @ExceptionHandler.exception_handler_decorator
       async def receive_message_pin(self, data):
           """
           Pin a message in a room.
           Event: message.pin
           Data: {"room_id": "<uuid>", "message_id": "<uuid>"}
           """
           room_id = data.get("room_id")
           message_id = data.get("message_id")

           # Permission check
           is_permitted, room = await self.permission_handler.have_admin_privileges(
               self.user, room_id, "pin"
           )
           if not is_permitted:
               from django.core.exceptions import PermissionDenied
               raise PermissionDenied("Only admins can pin messages")

           # Business logic
           await self._pin_message(room_id, message_id)

           # Broadcast to room
           group = f"group-{room_id}"
           await self.send_group(group, "message.pinned", {
               "message_id": message_id,
               "pinned_by": self.user.username,
           })

       @database_sync_to_async
       def _pin_message(self, room_id, message_id):
           from realtime_chat_messaging.utils.loader import get_model
           Message = get_model("Message")
           Message.objects.filter(pk=message_id).update(is_pinned=True)

Registering New Events with the Event Mapper
---------------------------------------------

New handler methods must also be registered in a custom event mapper so the
consumer's ``receive()`` method can route them:

.. code-block:: python

   # myapp/events.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers


   def custom_event_mapper(consumer):
       """Extend default event map with custom events."""
       events = map_event_type_to_handlers(consumer)

       # Add new events
       events["message.pin"] = consumer.receive_message_pin
       events["message.flag"] = consumer.receive_message_flag

       # Remove events you want to block
       # del events["room.join"]

       return events

Register the mapper:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "CHAT_CONSUMER_CLASS": "myapp.consumers.CustomChatConsumer",
       "EVENT_MAPPER": "myapp.events.custom_event_mapper",
   }

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
           now = timezone.now().timestamp()
           cutoff = now - self.RATE_WINDOW
           self._timestamps = [t for t in self._timestamps if t > cutoff]
           if len(self._timestamps) >= self.RATE_LIMIT:
               return False
           self._timestamps.append(now)
           return True

Using ``send_group`` in Custom Handlers
----------------------------------------

The ``send_group`` helper broadcasts to a channel layer group and uses the
``broadcast_group`` receiver to forward the message to connected clients:

.. code-block:: python

   # Broadcast to all room members
   await self.send_group(f"group-{room_id}", "custom.event", {"key": "value"})

   # Send only to the current user (all their devices)
   await self.send_group(f"user-{self.user.id}", "custom.event", {"key": "value"})

The resulting client payload:

.. code-block:: json

   {
     "eventType": "custom.event",
     "data": {"key": "value"}
   }

Full Custom Consumer Example
-----------------------------

A complete example combining custom events, rate limiting, analytics, and
moderation features is shown below. This demonstrates the full pattern for a
production-ready consumer extension:

.. code-block:: python

   # myapp/consumers.py
   import json
   import logging
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from realtime_chat_messaging.utils.decorators import ExceptionHandler
   from realtime_chat_messaging.permissions.handlers import PermissionHandler
   from channels.db import database_sync_to_async
   from django.utils import timezone

   logger = logging.getLogger(__name__)
   permission_handler = PermissionHandler()


   class CustomChatConsumer(ChatMessagingConsumer):

       RATE_LIMIT = 30
       RATE_WINDOW = 60

       async def connect(self):
           await super().connect()
           self._timestamps = []
           logger.info(f"Connected: {self.scope['user'].username}")

       async def disconnect(self, code):
           logger.info(f"Disconnected: {self.scope['user'].username}")
           await super().disconnect(code)

       async def receive(self, text_data=None, bytes_data=None):
           data = json.loads(text_data)
           if data.get("event_type") == "message.send" and not self._check_rate():
               await self.send(text_data=json.dumps({
                   "error": {"code": 4029, "detail": "Rate limit exceeded"}
               }))
               return
           await super().receive(text_data)

       @ExceptionHandler.exception_handler_decorator
       async def receive_message_pin(self, data):
           """Handle message.pin event."""
           room_id = data.get("room_id")
           message_id = data.get("message_id")

           is_permitted, room = await permission_handler.have_admin_privileges(
               self.user, room_id, "update"
           )
           if not is_permitted:
               from django.core.exceptions import PermissionDenied
               raise PermissionDenied("Only admins can pin messages")

           await self._do_pin(message_id)
           await self.send_group(f"group-{room_id}", "message.pinned", {
               "message_id": message_id,
               "pinned_by": self.user.username,
           })

       @database_sync_to_async
       def _do_pin(self, message_id):
           from realtime_chat_messaging.utils.loader import get_model
           get_model("Message").objects.filter(pk=message_id).update(is_pinned=True)

       def _check_rate(self):
           now = timezone.now().timestamp()
           self._timestamps = [t for t in self._timestamps
                                if t > now - self.RATE_WINDOW]
           if len(self._timestamps) >= self.RATE_LIMIT:
               return False
           self._timestamps.append(now)
           return True
