WebSocket Events
================

All communication with the server happens over a single persistent WebSocket
connection. There are two directions of communication:

- **Events** — messages sent *from the client to the server* to trigger an action
  (create a room, send a message, react, etc.)
- **Dispatches** — messages sent *from the server to the client* in response to
  events. Some dispatches go only to the user who sent the event (private);
  others are broadcast to every member of the relevant room (broadcast).

Understanding which dispatches you will receive for a given event — and who else
receives them — is essential for building your frontend correctly.

Connection
----------

Connect to::

   ws://<host>/messaging/

Authentication is handled by your ASGI middleware. Pass your JWT access token
as a query parameter — do not omit it, as unauthenticated connections are closed
immediately with code ``4001``::

   ws://localhost:8000/messaging/?token=<your_access_token>

Payload Format
--------------

Every client event follows this structure:

.. code-block:: javascript

   {
     "event_type": "<event_name>",
     "data": { ... }
   }

Every server dispatch follows this structure:

.. code-block:: javascript

   {
     "eventType": "<dispatch_name>",
     "data": { ... }
   }

Note the casing difference: ``event_type`` (snake_case) for client events,
``eventType`` (camelCase) for server dispatches. This is intentional — it makes
it trivial to tell which direction a message is travelling.

Events and Dispatches — Full Reference Table
---------------------------------------------

The table below lists every client event, the dispatch(es) it produces, and who
receives each dispatch. Read this table before working through the detailed
sections — it gives you the complete picture at a glance.

**Broadcast** means all current members of the relevant room receive the dispatch,
including the user who sent the event. **Private** means only the user who sent
the event receives the dispatch. **Targeted** means the dispatch is sent to a
specific subset of users (e.g. only the message sender, or only the removed
members).

.. list-table::
   :header-rows: 1
   :widths: 24 28 12 36

   * - Client event
     - Server dispatch
     - Delivery
     - Notes
   * - *(on connect)*
     - ``chat.notifications``
     - Private
     - Dispatched automatically on every successful connection. Contains all
       pending notifications grouped by room. Only fires when
       ``ENABLE_NOTIFICATION`` is ``True``.
   * - ``message.send``
     - ``message.dispatch``
     - Broadcast
     - Full message object sent to every room member in real time.
   * - ``message.acknowledged``
     - ``messagedelivered.dispatch``
     - Targeted
     - Sent only to the original sender(s) of the acknowledged messages,
       informing them their message was delivered.
   * - ``message.read``
     - ``readreceipt.dispatch``
     - Broadcast
     - Sent to all room members so every client can update read state.
   * - ``message.react``
     - ``reaction.dispatch``
     - Broadcast
     - Sent to all room members with the updated message including reactions.
   * - ``message.typing``
     - ``messagetyping.dispatch``
     - Broadcast
     - Sent to all room members. Not persisted — purely real time.
   * - ``message.modify`` (update)
     - ``messagemodification.dispatch``
     - Broadcast
     - Sent to all room members with the updated message.
   * - ``message.modify`` (delete)
     - ``messagemodification.dispatch``
     - Broadcast
     - Sent to all room members with the list of deleted message IDs.
   * - ``room.create``
     - ``roomcreate.dispatch``
     - Broadcast
     - Sent to all initial members (creator + participants/subscribers).
   * - ``room.list``
     - ``roomlist.dispatch``
     - Private
     - Sent only to the requesting user. Contains all their rooms.
   * - ``room.info``
     - ``roominfo.dispatch``
     - Private
     - Sent only to the requesting user. Full details for one room.
   * - ``room.messages``
     - ``roommessages.dispatch``
     - Private
     - Sent only to the requesting user. Paginated message history.
   * - ``room.join``
     - ``roomaddmembers.dispatch``
     - Broadcast
     - Sent to all existing members notifying them of the new joiner.
   * - ``room.leave``
     - ``roomexit.dispatch``
     - Targeted (leaver)
     - Sent to the leaving user confirming they left.
   * - ``room.leave``
     - ``roomremovemembers.dispatch``
     - Broadcast
     - Sent to remaining members notifying them someone left.
   * - ``room.leave`` *(if room becomes empty)*
     - ``roomdelete.dispatch``
     - Broadcast
     - Sent to all members if the room is deleted after becoming empty.
   * - ``room.add_members``
     - ``roomaddmembers.dispatch``
     - Broadcast
     - Sent to all room members (including newly added ones) with the list of
       who was added and by whom.
   * - ``room.remove_members``
     - ``roomexit.dispatch``
     - Targeted (removed)
     - Sent individually to each removed user informing them they were removed.
   * - ``room.remove_members``
     - ``roomremovemembers.dispatch``
     - Broadcast
     - Sent to remaining members with the list of who was removed and by whom.
   * - ``room.modify`` (update/permissions/admin)
     - ``roomupdate.dispatch``
     - Broadcast
     - Sent to all room members with the full updated room object.
   * - ``room.modify`` (delete)
     - ``roomdelete.dispatch``
     - Broadcast
     - Sent to all room members notifying them the room was deleted.
   * - ``session.heartbeat``
     - *(status response)*
     - Private
     - Returns ``{"status": "success"}`` to the requesting user. Not a formal
       dispatch event.

On Connect
----------

When a client connects successfully, two things happen automatically before any
event is sent:

1. **Session registration** — the connection is registered and the client is
   added to the channel groups for every room the user belongs to. This is what
   enables real-time delivery: once connected, the user will receive broadcasts
   from all their rooms immediately, even if they were offline when messages were
   sent.

2. **Notification dispatch** — if ``ENABLE_NOTIFICATION`` is ``True``, all
   pending notifications are fetched and dispatched immediately so the client can
   show unread counts or missed message badges without sending any event first.

``chat.notifications``
~~~~~~~~~~~~~~~~~~~~~~

Dispatched automatically to the connecting user on every successful connection
(when ``ENABLE_NOTIFICATION`` is ``True``).

**Delivery:** Private — only the connecting user receives this.

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
             "sender": {"id": 2, "username": "bob"},
             "content": "Hey, are you there?",
             "created_at": "2026-01-01T10:00:00Z"
           }
         }
       ],
       "<room_uuid_2>": [
         {
           "id": "<notification_uuid>",
           "notification_type": "REACTION",
           "message": { ... }
         }
       ]
     }
   }

The data object is keyed by room UUID so your frontend can display per-room
unread counts without any additional processing. An empty object (``{}``) means
no pending notifications. Notification types are ``NEW_MESSAGE``, ``REPLY``, and
``REACTION``.

Message Events
--------------

``message.send``
~~~~~~~~~~~~~~~~

Send a new message to a room. The sender must be a member of the room and must
have send permission.

**Delivery:** Broadcast — all room members receive ``message.dispatch`` in real
time, including the sender (so the sender can confirm delivery without special
handling).

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<room_uuid>",
       "content": "Hello!",
       "extra_fields": {
         "parent_message_id": "<uuid>",    // optional — reply to a message
         "forwarded_from_id": "<uuid>",    // optional — forward a message
         "media": [                         // optional — attach files
           {
             "media_url": "https://cdn.example.com/file.jpg",
             "media_type": "image",
             "file_size": 204800,
             "mime_type": "image/jpeg",
             "metadata": {}
           }
         ]
       }
     }
   }

.. note::

   ``parent_message_id`` and ``forwarded_from_id`` are mutually exclusive.
   A message cannot be both a reply and a forward at the same time.

**Server dispatch** — ``message.dispatch``:

.. code-block:: javascript

   {
     "eventType": "message.dispatch",
     "data": {
       "id": "<message_uuid>",
       "room": {"id": "<room_uuid>"},
       "sender": {"id": 1, "username": "alice"},
       "content": "Hello!",
       "is_deleted": false,
       "is_edited": false,
       "is_forwarded": false,
       "forwarded_from": null,
       "parent_message": null,
       "delivered_to": ["alice"],
       "read_receipts": [],
       "reactions": [],
       "attachments": [],
       "created_at": "2026-01-01T12:00:00Z",
       "updated_at": "2026-01-01T12:00:00Z"
     }
   }

``message.acknowledged``
~~~~~~~~~~~~~~~~~~~~~~~~

Inform the server that the client has received one or more messages. This
updates ``delivered_to`` on each message and removes the user from the
notification recipients list for each one (clearing their pending notifications).

Send this event as soon as messages are rendered on screen so senders see
accurate delivery status.

**Delivery:** Targeted — only the original sender(s) of the acknowledged
messages receive ``messagedelivered.dispatch``. The acknowledging user receives
nothing (the server updates the record silently on their behalf).

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "message.acknowledged",
     "data": {
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

**Server dispatch** — ``messagedelivered.dispatch`` (to original sender(s) only):

.. code-block:: javascript

   {
     "eventType": "messagedelivered.dispatch",
     "data": [
       {
         "id": "<message_uuid>",
         "delivered_to": ["alice", "bob"],
         ...
       }
     ]
   }

``message.read``
~~~~~~~~~~~~~~~~

Mark one or more messages as read. Creates a ``ReadReceipt`` for the current
user against each message. All room members are notified so every client can
update its read state display (e.g. showing "Seen by Alice").

**Delivery:** Broadcast — all room members receive ``readreceipt.dispatch``.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "message.read",
     "data": {
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

**Server dispatch** — ``readreceipt.dispatch``:

.. code-block:: javascript

   {
     "eventType": "readreceipt.dispatch",
     "data": {
       "id": "<message_uuid>",
       "read_receipts": [
         {"reader": {"id": 2, "username": "bob"}, "read_at": "2026-01-01T12:01:00Z"}
       ],
       ...
     }
   }

``message.react``
~~~~~~~~~~~~~~~~~

Add or remove a reaction on a message. Each user can have at most one reaction
per message — if a user adds a new reaction, it automatically replaces their
existing one. To remove a reaction, send ``"type": "remove"`` with the same
``reaction_content``.

**Delivery:** Broadcast — all room members receive ``reaction.dispatch`` with
the updated message.

**Client payload (add):**

.. code-block:: javascript

   {
     "event_type": "message.react",
     "data": {
       "type": "add",
       "message_id": "<uuid>",
       "reaction_content": "👍"
     }
   }

**Client payload (remove):**

.. code-block:: javascript

   {
     "event_type": "message.react",
     "data": {
       "type": "remove",
       "message_id": "<uuid>",
       "reaction_content": "👍"
     }
   }

**Server dispatch** — ``reaction.dispatch``:

.. code-block:: javascript

   {
     "eventType": "reaction.dispatch",
     "data": {
       "status": "successful",
       "type": "add",
       "message": {
         "id": "<message_uuid>",
         "reactions": [
           {"user": {"id": 1, "username": "alice"}, "reaction_content": "👍", "created_at": "..."}
         ],
         ...
       }
     }
   }

``message.typing``
~~~~~~~~~~~~~~~~~~

Signal to room members that the current user is typing. This event is not
persisted — it exists purely to drive typing indicators on the frontend. Send it
each time the user types a character (or use a debounce). There is no
corresponding "stopped typing" event — stop sending ``message.typing`` and the
indicator should fade after a client-side timeout.

**Delivery:** Broadcast — all room members receive ``messagetyping.dispatch``.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "message.typing",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch** — ``messagetyping.dispatch``:

.. code-block:: javascript

   {
     "eventType": "messagetyping.dispatch",
     "data": {
       "username": "alice"
     }
   }

``message.modify``
~~~~~~~~~~~~~~~~~~

Edit or delete a message. Only the original sender can modify their own
messages. Bulk delete is supported; bulk update is not (update is always single
message).

**Delivery:** Broadcast — all room members receive
``messagemodification.dispatch`` for both update and delete.

**Update (single message only):**

.. code-block:: javascript

   {
     "event_type": "message.modify",
     "data": {
       "action": "update",
       "message_id": "<uuid>",
       "extra_fields": {
         "content": "Corrected message content"
       }
     }
   }

**Delete (single or bulk):**

.. code-block:: javascript

   {
     "event_type": "message.modify",
     "data": {
       "action": "delete",
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

.. note::

   All messages in a bulk delete must belong to the **same room**. The server
   validates this and raises an error if messages span multiple rooms.

**Server dispatch — update** — ``messagemodification.dispatch``:

.. code-block:: javascript

   {
     "eventType": "messagemodification.dispatch",
     "data": {
       "status": "successful",
       "action": "update",
       "message": {
         "id": "<message_uuid>",
         "content": "Corrected message content",
         "is_edited": true,
         ...
       }
     }
   }

**Server dispatch — delete** — ``messagemodification.dispatch``:

.. code-block:: javascript

   {
     "eventType": "messagemodification.dispatch",
     "data": {
       "status": "successful",
       "action": "delete",
       "message_ids": ["<uuid1>", "<uuid2>"]
     }
   }

Room Events
-----------

``room.create``
~~~~~~~~~~~~~~~

Create a new room. The creator is automatically added as a member. The room type
determines which fields are required and which are optional.

**Delivery:** Broadcast — all initial members (creator plus participants or
subscribers) receive ``roomcreate.dispatch``.

**OneToOneChat:**

.. code-block:: javascript

   {
     "event_type": "room.create",
     "data": {
       "type": "OneToOneChat",
       "participants": [2]
     }
   }

.. note::

   For ``OneToOneChat``, ``participants`` must contain **only the other user's
   ID**. The creator is added automatically, making the total exactly 2
   participants. Providing more than one ID or providing your own ID will raise
   a validation error.

**GroupChat:**

.. code-block:: javascript

   {
     "event_type": "room.create",
     "data": {
       "type": "GroupChat",
       "name": "Project Team",
       "description": "Discussion for Project X",
       "participants": [2, 3, 4],
       "extra_fields": {
         "join_approval_required": false,
         "group_locked": false,
         "property": {
           "preferences": {
             "notifications": true
           }
         }
       }
     }
   }

**Channel:**

.. code-block:: javascript

   {
     "event_type": "room.create",
     "data": {
       "type": "Channel",
       "name": "Announcements",
       "description": "Company-wide updates",
       "subscribers": [2, 3],
       "extra_fields": {
         "is_public": true,
         "property": {
           "preferences": {}
         }
       }
     }
   }

**Server dispatch** — ``roomcreate.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roomcreate.dispatch",
     "data": {
       "type": "GroupChat",
       "id": "<room_uuid>",
       "name": "Project Team",
       "creator": {"id": 1, "username": "alice"},
       "participants": [...],
       "admins": [],
       "property": {"preferences": {"notifications": true}},
       ...
     }
   }

The ``type`` field in the dispatch identifies the concrete room type so your
frontend can render the correct UI without additional queries.

``room.list``
~~~~~~~~~~~~~

Retrieve all rooms the current user belongs to. Each entry includes the room
type, basic details, and the last message for preview display.

**Delivery:** Private — sent only to the requesting user.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.list",
     "data": {}
   }

**Server dispatch** — ``roomlist.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roomlist.dispatch",
     "data": [
       {
         "type": "OneToOneChat",
         "id": "<uuid>",
         "peer": {"id": 2, "username": "bob"},
         "last_message": {"content": "Hello!", "created_at": "..."}
       },
       {
         "type": "GroupChat",
         "id": "<uuid>",
         "name": "Project Team",
         "creator": {"id": 1, "username": "alice"},
         "last_message": {"content": "Meeting at 3pm", "created_at": "..."}
       },
       {
         "type": "Channel",
         "id": "<uuid>",
         "name": "Announcements",
         "last_message": {"content": "New release out", "created_at": "..."}
       }
     ]
   }

``room.info``
~~~~~~~~~~~~~

Retrieve full details for a specific room, including all members, admins,
permissions, and room properties. Useful for rendering a room settings screen
or member list.

**Delivery:** Private — sent only to the requesting user.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.info",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch** — ``roominfo.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roominfo.dispatch",
     "data": {
       "type": "GroupChat",
       "id": "<uuid>",
       "name": "Project Team",
       "description": "Discussion for Project X",
       "creator": {"id": 1, "username": "alice"},
       "participants": [
         {"id": 1, "username": "alice"},
         {"id": 2, "username": "bob"}
       ],
       "admins": [{"id": 1, "username": "alice"}],
       "property": {"preferences": {"notifications": true}},
       "join_approval_required": false,
       "group_locked": false,
       ...
     }
   }

``room.messages``
~~~~~~~~~~~~~~~~~

Retrieve message history for a room with optional pagination. Send this when
the user opens a room to load the initial message history. Use the pagination
fields in the response to implement infinite scroll (load more on demand).

**Delivery:** Private — sent only to the requesting user.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.messages",
     "data": {
       "room_id": "<uuid>",
       "paginate": {
         "page": 1,
         "size": 50
       }
     }
   }

Omit ``paginate`` to retrieve all messages at once (not recommended for rooms
with long history).

**Server dispatch** — ``roommessages.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roommessages.dispatch",
     "data": {
       "has_next": true,
       "has_previous": false,
       "next_page_number": 2,
       "prev_page_number": null,
       "page": 1,
       "size": 50,
       "data": {
         "room_id": "<uuid>",
         "messages": [
           {
             "id": "<message_uuid>",
             "sender": {"id": 2, "username": "bob"},
             "content": "Meeting at 3pm",
             "created_at": "2026-01-01T11:00:00Z",
             ...
           }
         ]
       }
     }
   }

Use ``has_next`` and ``next_page_number`` to determine whether more pages exist.
When the user scrolls to the top, request page 2, then page 3, and so on.

``room.join``
~~~~~~~~~~~~~

Join an existing room. The behaviour depends on room type:

- **Channel** — allowed if ``is_public`` is ``True``. Private channels raise a
  validation error.
- **GroupChat** — raises a validation error by default ("ask an admin to add
  you"). Override ``_join_room`` in a custom ``EventHandler`` to implement
  approval flows or open joining (see :doc:`custom_handlers`).
- **OneToOneChat** — cannot be joined; raises a validation error always.

**Delivery:** Broadcast — all existing room members receive
``roomaddmembers.dispatch`` notifying them of the new joiner.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.join",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch** — ``roomaddmembers.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roomaddmembers.dispatch",
     "data": {
       "room": {"id": "<uuid>", "name": "Announcements", ...},
       "new_members": ["alice"],
       "added_by": "self"
     }
   }

``room.leave``
~~~~~~~~~~~~~~

Leave a room voluntarily. Not available for ``OneToOneChat`` — calling
``room.leave`` on a one-to-one chat raises a validation error.

This event produces up to three dispatches depending on what happens after the
user leaves.

**Delivery:**

- ``roomexit.dispatch`` → Private (the leaving user only)
- ``roomremovemembers.dispatch`` → Broadcast (remaining members)
- ``roomdelete.dispatch`` → Broadcast (all members, only if the room is deleted
  because it became empty after the user left)

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.leave",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch 1** — ``roomexit.dispatch`` (to the leaving user):

.. code-block:: javascript

   {
     "eventType": "roomexit.dispatch",
     "data": {
       "room": {"id": "<uuid>", "name": "Project Team", ...},
       "message": "You left Project Team"
     }
   }

**Server dispatch 2** — ``roomremovemembers.dispatch`` (to remaining members):

.. code-block:: javascript

   {
     "eventType": "roomremovemembers.dispatch",
     "data": {
       "room": {"id": "<uuid>", ...},
       "removed_members": ["alice"],
       "removed_by": "self"
     }
   }

**Server dispatch 3** — ``roomdelete.dispatch`` (if room becomes empty):

.. code-block:: javascript

   {
     "eventType": "roomdelete.dispatch",
     "data": {
       "room_id": "<uuid>"
     }
   }

``room.add_members``
~~~~~~~~~~~~~~~~~~~~

Add one or more users to a room. Requires ``can_add_new_participants`` permission
for GroupChats or ``can_add_new_subscribers`` for Channels. Admins have this
permission by default.

**Delivery:** Broadcast — all room members (including the newly added ones)
receive ``roomaddmembers.dispatch``.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.add_members",
     "data": {
       "room_id": "<uuid>",
       "members": [5, 6, 7]
     }
   }

**Server dispatch** — ``roomaddmembers.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roomaddmembers.dispatch",
     "data": {
       "room": {"id": "<uuid>", "name": "Project Team", ...},
       "new_members": ["carol", "dave", "eve"],
       "added_by": "alice"
     }
   }

``room.remove_members``
~~~~~~~~~~~~~~~~~~~~~~~

Remove one or more users from a room. Requires ``can_remove_participants``
(GroupChat) or ``can_remove_subscribers`` (Channel) permission. The room creator
cannot be removed by another admin — only the creator themselves can leave.

This event produces two dispatches: one to each removed user, and one to the
remaining members.

**Delivery:**

- ``roomexit.dispatch`` → Targeted (each removed user receives their own copy)
- ``roomremovemembers.dispatch`` → Broadcast (remaining members)

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "room.remove_members",
     "data": {
       "room_id": "<uuid>",
       "members": [5, 6]
     }
   }

**Server dispatch 1** — ``roomexit.dispatch`` (to each removed user):

.. code-block:: javascript

   {
     "eventType": "roomexit.dispatch",
     "data": {
       "room": {"id": "<uuid>", ...},
       "message": "You have been removed by alice"
     }
   }

**Server dispatch 2** — ``roomremovemembers.dispatch`` (to remaining members):

.. code-block:: javascript

   {
     "eventType": "roomremovemembers.dispatch",
     "data": {
       "room": {"id": "<uuid>", ...},
       "removed_members": ["carol", "dave"],
       "removed_by": "alice"
     }
   }

``room.modify``
~~~~~~~~~~~~~~~

Manage room settings, membership roles, and permissions. Most actions require
admin (GroupChat) or moderator (Channel) status. Only the room creator can
delete a GroupChat or Channel.

**Delivery:** Broadcast — all room members receive ``roomupdate.dispatch`` for
all actions except delete, which sends ``roomdelete.dispatch``.

**Update room details:**

.. code-block:: javascript

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "update",
       "data": {
         "name": "New Room Name",
         "description": "Updated description",
         "avatar": "https://cdn.example.com/avatar.jpg",
         "group_locked": true,            // GroupChat only
         "join_approval_required": true,  // GroupChat only
         "is_public": false,              // Channel only
         "property": {
           "preferences": {"theme": "dark"}
         }
       }
     }
   }

**Delete room** (creator only):

.. code-block:: javascript

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "delete"
     }
   }

**Add or remove admin** (GroupChat only):

.. code-block:: javascript

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_admin",
       "data": {"users": [5, 6]}
     }
   }

Use ``"action": "remove_admin"`` to demote. The room creator cannot be demoted.

**Add or remove moderator** (Channel only):

.. code-block:: javascript

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_moderator",
       "data": {"users": [8]}
     }
   }

Use ``"action": "remove_moderator"`` to demote.

**Grant or revoke permissions:**

.. code-block:: javascript

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_permission",
       "data": {
         "users": [3],
         "permission": ["can_send_messages"]
       }
     }
   }

Use ``"action": "remove_permission"`` to revoke. The room creator is silently
excluded from permission removals — their permissions cannot be revoked.

Valid ``action`` values: ``update``, ``delete``, ``add_admin``,
``remove_admin``, ``add_moderator``, ``remove_moderator``,
``add_permission``, ``remove_permission``.

**Server dispatch — all actions except delete** — ``roomupdate.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roomupdate.dispatch",
     "data": {
       "type": "GroupChat",
       "id": "<uuid>",
       "name": "New Room Name",
       "admins": [...],
       ...
     }
   }

**Server dispatch — delete** — ``roomdelete.dispatch``:

.. code-block:: javascript

   {
     "eventType": "roomdelete.dispatch",
     "data": {
       "room_id": "<uuid>"
     }
   }

Session Events
--------------

``session.heartbeat``
~~~~~~~~~~~~~~~~~~~~~

Keep the WebSocket session alive and prevent it from being marked as expired.
Send this event every 15–30 seconds from the client. If heartbeats stop arriving
for longer than ``INACTIVITY_THRESHOLD`` (default: 60 seconds), the session is
considered inactive. Inactive sessions are cleaned up on the next connection
event.

**Delivery:** Private — the server responds directly to the requesting user only.
This response is not a formal dispatch event — it does not carry an ``eventType``
field.

**Client payload:**

.. code-block:: javascript

   {
     "event_type": "session.heartbeat",
     "data": {}
   }

**Server response:**

.. code-block:: javascript

   {"status": "success"}

.. warning::

   Failing to send heartbeats regularly has a side effect beyond session
   expiry: if your session expires and you then trigger any event that adds
   you to a new group (such as ``room.create``), your channel will not be
   added to that group because ``add_channel_to_group`` only operates on
   active sessions. Broadcasts to that group will never reach you — with no
   error. Send ``session.heartbeat`` every 15–30 seconds to keep your session
   active. See :doc:`troubleshooting` for a full explanation.

Display Logic Tips
-------------------

Several dispatches include context fields specifically to help your frontend
display accurate status messages without additional logic:

- ``"removed_by": "self"`` — the user left voluntarily → display *"Alice left"*
- ``"removed_by": "<username>"`` — the user was removed by someone else →
  display *"Bob removed Alice"*
- ``"added_by": "self"`` — the user joined voluntarily → display *"Alice joined"*
- ``"added_by": "<username>"`` — the user was added by someone else →
  display *"Bob added Alice"*

Use these values to drive system messages in your chat UI rather than
hard-coding logic on the client side.

.. _why-am-i-not-receiving-broadcasts:

Why Am I Not Receiving Broadcasts?
------------------------------------

This is one of the most common issues new users encounter. The symptoms are
confusing: you send an event, the server responds (so the connection is clearly
working), but the broadcast never arrives on the other client. No error is
raised. Nothing in the logs explains it.

There are two root causes, both related to how the package manages group
membership.

How Group Membership Works
~~~~~~~~~~~~~~~~~~~~~~~~~~

When a user connects, the consumer calls ``channel_setup()`` which does two
things: it registers the session, and it adds the user's current
``channel_name`` to every channel group corresponding to the rooms they belong
to. This is what makes real-time delivery possible — the user's connection is
subscribed to each room's group, so broadcasts reach them instantly.

The key detail is that this group membership is **not stored in the database**.
It lives in the channel layer (in-memory or Redis). If the channel layer loses
its state, or if the session that recorded the user's ``channel_name`` is no
longer considered active, the user's connection is effectively invisible to the
broadcast system — even though the WebSocket is still open and responding.

Cause 1 — In-Memory Cache Cleared on Restart
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The in-memory channel layer (``channels.layers.InMemoryChannelLayer``) and the
in-memory Django cache (``django.core.cache.backends.locmem.LocMemCache``) both
live in the server process's memory. When the server restarts, both are wiped
completely.

The cache stores which channel groups each user belongs to. When a new event
arrives that involves adding the user to a group (e.g. ``room.create``,
``room.add_members``), the package calls ``add_channel_to_group``, which first
queries the cache for the user's active sessions to find their current
``channel_name``. If the cache was cleared by a restart, those session records
are gone — so the method finds nothing to add and the user never gets subscribed
to the new group.

The user is still connected. They can still send events and receive private
responses. But they will not receive any broadcasts to that room until they
disconnect and reconnect (which triggers ``channel_setup()`` again and
re-registers everything).

.. note::

   This is expected behaviour in development and not a bug. It becomes a real
   problem the moment you deploy to a multi-process or restarting environment
   without switching to a persistent cache. Use Redis for both ``CHANNEL_LAYERS``
   and ``CACHES`` in any environment where this matters — see :doc:`deployment`.

Cause 2 — Session Expired Due to Missed Heartbeats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The package tracks active sessions using ``INACTIVITY_THRESHOLD`` (default: 60
seconds). A session is considered active as long as heartbeat events keep
arriving. When ``add_channel_to_group`` is called, it queries for the user's
**active** sessions only — sessions whose last heartbeat is within the threshold
— to find the ``channel_name`` values to add to a group.

If heartbeats stop (network hiccup, tab backgrounded, client bug, heartbeat
interval too long), the session crosses the inactivity threshold and is no
longer returned by the active session query. Any subsequent broadcast that
requires adding the user to a new group silently skips them — because from the
package's perspective, they have no active session.

Again, the WebSocket may still be open. The user can still send events. But they
will not receive broadcasts to newly joined or created rooms until they
reconnect.

The fix is to send ``session.heartbeat`` reliably every 15–30 seconds from the
client and to set ``INACTIVITY_THRESHOLD`` to a value comfortably above your
heartbeat interval:

.. code-block:: javascript

   // Send a heartbeat every 20 seconds
   setInterval(() => {
     if (ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify({ event_type: "session.heartbeat", data: {} }));
     }
   }, 20000);

.. code-block:: python

   # settings.py — give yourself a comfortable margin above the interval
   REALTIME_CHAT_MESSAGING = {
       "INACTIVITY_THRESHOLD": 60,  # seconds — default
   }

Summary and Checklist
~~~~~~~~~~~~~~~~~~~~~~

If a client is connected but not receiving broadcasts, work through this list:

- Did the server restart since the client connected? → Disconnect and reconnect
  the client to re-register the session.
- Are you using the in-memory channel layer or in-memory cache in a
  multi-process or restarting environment? → Switch to Redis for both
  ``CHANNEL_LAYERS`` and ``CACHES``.
- Is the client sending ``session.heartbeat`` every 15–30 seconds? → Add it if
  not, and confirm it is being sent reliably (check the network tab).
- Is ``INACTIVITY_THRESHOLD`` set lower than the heartbeat interval? → Raise it
  so sessions do not expire between heartbeats.
- Is the user actually a member of the room being broadcast to? → Confirm with
  ``room.list`` or ``room.info``.