Notifications
=============

The package includes a push notification scaffolding system built around the
``ChatNotification`` model. It does not send push notifications itself — it
tracks *which users have not yet received which messages* so your own push
notification service (Firebase, AWS SNS, OneSignal, etc.) can pick up the data
and act on it.

How Notifications Work
----------------------

The notification lifecycle has four stages:

1. **Message sent** — When a message is created, a ``ChatNotification`` record
   is created with all room participants (excluding the sender) as ``recipients``.
   The notification type reflects the message type: ``NEW_MESSAGE``, ``REPLY``,
   or ``REACTION``.

2. **Delivery acknowledged** — When a recipient connects and sends
   ``message.acknowledged``, they are removed from the ``recipients`` M2M field.

3. **Auto-deletion** — A ``m2m_changed`` signal monitors ``recipients``. When the
   list becomes empty (all recipients acknowledged), the notification is deleted
   automatically.

4. **On connect dispatch** — If ``ENABLE_NOTIFICATION`` is ``True``, all
   pending notifications for the connecting user are fetched and sent immediately
   as a ``chat.notifications`` event.

Notification Types
------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Type
     - When created
   * - ``NEW_MESSAGE``
     - Standard message sent to any room
   * - ``REPLY``
     - Message with a ``parent_message_id`` (reply)
   * - ``REACTION``
     - Reaction added to a message

The ``chat.notifications`` Event
----------------------------------

On every successful WebSocket connection (when ``ENABLE_NOTIFICATION`` is
``True``), the server dispatches pending notifications:

.. code-block:: javascript

   {
     "eventType": "chat.notifications",
     "data": {
       "<room_uuid_1>": [
         {
           "id": "<notification_uuid>",
           "notification_type": "NEW_MESSAGE",
           "message": {
             "id": "<message_uuid>",
             "room": {"id": "<room_uuid_1>"},
             "sender": {"id": 2, "username": "bob", ...},
             "content": "Hey, are you there?",
             "created_at": "2026-01-01T10:00:00Z",
             ...
           }
         }
       ],
       "<room_uuid_2>": [
         ...
       ]
     }
   }

Notifications are grouped by room ID so the client can display unread counts or
badge indicators per room without additional processing.

Enabling and Disabling
-----------------------

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "ENABLE_NOTIFICATION": True   # default
   }

When ``ENABLE_NOTIFICATION`` is ``False``:

- ``ChatNotification`` records are **never created** for new messages.
- The ``chat.notifications`` event is **not dispatched** on connect.
- The ``message.acknowledged`` event still updates ``delivered_to`` on messages
  but does not touch notifications (since none exist).

Integrating with a Push Service
---------------------------------

There are multiple ways to hook into the notification flow and trigger an external
push service. Here are two easy approaches:

**Approach 1 — Django signal on ChatNotification**

Hook into the ``m2m_changed`` signal on ``ChatNotification.recipients``. This
keeps your push logic decoupled from the package entirely and works well when
you want the push service to live in its own app:

.. code-block:: python

   # myapp/signals.py
   from django.db.models.signals import m2m_changed
   from django.dispatch import receiver
   from realtime_chat_messaging.models import ChatNotification

   @receiver(m2m_changed, sender=ChatNotification.recipients.through)
   def send_push_notification(sender, instance, action, pk_set, **kwargs):
       if action == "post_add" and pk_set:
           from django.contrib.auth import get_user_model
           User = get_user_model()
           recipients = User.objects.filter(pk__in=pk_set)
           for user in recipients:
               # Call your push service here
               # firebase_send(user.fcm_token, instance.message.content)
               pass

The notification holds a ``message`` foreign key so you have full access to
the message content, sender, room, and type for building your push payload.

**Approach 2 — Override ``create_chat_notification`` in a custom EventHandler**

If you already have a custom ``EventHandler``, override ``create_chat_notification``
directly. This is the tighter integration path — the notification object,
message, recipients, and type are all resolved and handed to you with no
additional queries needed:

.. code-block:: python

   # myapp/handlers.py
   from realtime_chat_messaging.utils.handlers import EventHandler


   class CustomEventHandler(EventHandler):

       def create_chat_notification(self, message, notification_type, user):
            # Call super() first to create the ChatNotification record as normal
            recipients = super().create_chat_notification(
               message, notification_type, user
            )

            for recipient in recipients:
              # Call your push service here — you have full context:
              # notification_type, message.content,
              # message.room, recipient.fcm_token, etc.
              # firebase_send(recipient.fcm_token, message.content)
              pass

            return recipients
            # Ensure ENABLE_NOTIFICATION is True in settings for this to work




Register it in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler",
   }

**Which method to prefer**

Use the signal approach when your push logic lives outside any custom handler
and you want clean decoupling. Use the ``create_chat_notification`` override
when you already have a custom ``EventHandler`` in place — it avoids an extra
signal round-trip and gives you richer context without re-querying.

Overriding the On-Connect Dispatch
------------------------------------

When a user connects, the consumer calls
``dispatch_chat_notifications()`` on the ``ChatMessagingConsumer`` to fetch pending
notifications and dispatch the ``chat.notifications`` event. If you have custom
notification logic — a different data structure, a different event name, or you
want to suppress the dispatch entirely in favour of your own flow — you can
override this method in your custom ``ChatMessagingConsumer`` 
or consider a custom event handler approach and override the 
``get_and_group_chat_notifications`` method.

.. code-block:: python

   # myapp/consumers.py
   from realtime_chat_messaging.consumers import ChatMessagingConsumer


   class CustomChatMessagingConsumer(ChatMessagingConsumer):

       async def dispatch_chat_notifications(self, user):
           """
           Override to customise or suppress the on-connect notification dispatch.
           """
           pass
           # Add custom behaviour here, e.g. fetch notifications differently, change event structure,
           # or skip dispatching entirely.


Deleted Messages
----------------

When a message is deleted (via ``message.modify`` with ``action: "delete"``),
all associated ``ChatNotification`` records are deleted immediately, regardless
of remaining recipients. This prevents push notifications for messages that no
longer exist.