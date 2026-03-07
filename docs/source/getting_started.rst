Getting Started
===============

This page covers the core concepts you need before building with the package.
By the end you will understand the event protocol, the three room types, and
what the package handles automatically so you do not have to.

The Single Endpoint
-------------------

The entire package is accessed through one WebSocket connection::

   ws://<host>/messaging/

There are no REST endpoints. Every interaction happens over this connection
using structured JSON events.

The Event Protocol
------------------

Client to server events use snake_case:

.. code-block:: json

   {
     "event_type": "message.send",
     "data": {}
   }

Server to client dispatches use camelCase:

.. code-block:: json

   {
     "eventType": "message.dispatch",
     "data": {}
   }

Most dispatches are broadcast to all room members. Some go only to the
requesting user (room.list, room.messages). The websocket_events reference
marks which is which for every event.

The Three Room Types
--------------------

OneToOneChat -- exactly two participants, enforced by the database. Cannot
be left; the room persists until a user account is deleted. Pass only the
other user's ID when creating -- the creator is added automatically:

.. code-block:: json

   {
     "event_type": "room.create",
     "data": { "type": "OneToOneChat", "participants": [2] }
   }

GroupChat -- multi-user room with admins, a member cap (default 100), and a
group_locked flag that restricts posting to admins only. Users join by
invitation from an admin via room.add_members:

.. code-block:: json

   {
     "event_type": "room.create",
     "data": {
       "type": "GroupChat",
       "name": "Project Team",
       "participants": [2, 3, 4]
     }
   }

Channel -- broadcast room. Only moderators and users with explicit
can_send_messages permission can post. Set is_public: true to allow open
joining via room.join. Default cap is 300 subscribers:

.. code-block:: json

   {
     "event_type": "room.create",
     "data": {
       "type": "Channel",
       "name": "Announcements",
       "extra_fields": { "is_public": true }
     }
   }

What Happens Automatically
---------------------------

These require no code from you:

- **Creator membership** -- the creating user is added as a participant and
  given admin/moderator status automatically.
- **Object-level permissions** -- granted and revoked via signals whenever admins
  or moderators are added or removed.
- **Pending notifications** -- on every connection, undelivered notifications
  are pushed immediately as a ``chat.notifications`` event.
- **Multi-device support** -- all active connections for a user receive every
  message simultaneously.
- **Session cleanup** -- expired sessions are removed from channel groups on
  the next reconnect, preventing delivery to dead connections.
- **Reaction deduplication** -- adding a reaction replaces the previous one for
  that user. One reaction per user per message.
- **Notification cleanup** -- when all recipients acknowledge a message the
  notification is deleted. When a message is deleted its notifications go too.

Your First Conversation
------------------------

.. code-block:: javascript

   const ws = new WebSocket(`ws://localhost:8000/messaging/?token=${token}`);

   ws.onopen = () => {
     ws.send(JSON.stringify({
       event_type: "room.create",
       data: { type: "OneToOneChat", participants: [2] }
     }));
   };

   ws.onmessage = (e) => {
     const msg = JSON.parse(e.data);

     if (msg.eventType === "roomcreate.dispatch") {
       ws.send(JSON.stringify({
         event_type: "message.send",
         data: { room_id: msg.data.id, content: "Hello!" }
       }));
     }

     if (msg.eventType === "message.dispatch") {
       ws.send(JSON.stringify({
         event_type: "message.acknowledged",
         data: { message_id: [msg.data.id] }
       }));
     }

     if (msg.error) {
       console.error(msg.error.code, msg.error.detail);
     }
   };

   // Heartbeat every 20 seconds
   setInterval(() => {
     ws.send(JSON.stringify({ event_type: "session.heartbeat", data: {} }));
   }, 20000);

Key Behaviours to Know
-----------------------

**Content is sanitised** -- message text is processed by ``bleach`` before
saving. Tags outside the allowed set are stripped.

**Media is URLs not uploads** -- upload files to your own CDN first, then pass
the URL in the ``media`` array inside ``extra_fields``.

**Forwarded messages cannot be replies** -- a message is either a forward or a
reply, never both. A database constraint enforces this.

**Soft delete is opt-in** -- deleting a message removes it permanently by
default. Set ``MESSAGE_SOFT_DELETE: True`` in settings for recoverable deletes.

**Heartbeat is required** -- sessions expire after ``INACTIVITY_THRESHOLD``
seconds (default 60). Send ``session.heartbeat`` every 15 to 30 seconds.

Next Steps
----------

- :doc:`websocket_events` -- every event and dispatch documented
- :doc:`rooms` -- room types, fields, and signals in detail
- :doc:`messages` -- lifecycle, reactions, read receipts, media
- :doc:`settings` -- all configuration options
- :doc:`custom_models` -- extending models without modifying the package
