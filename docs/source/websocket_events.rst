WebSocket Events
================

All communication with the server happens over a single WebSocket connection.
Client-to-server messages are called **events**; server-to-client messages are
called **dispatches**.

Connection
----------

Connect to::

   ws://<host>/messaging/

Authentication is handled by your ASGI middleware. Unauthenticated connections
are closed immediately with code ``4001``.

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

Note the difference in casing: ``event_type`` (snake_case) for client events,
``eventType`` (camelCase) for server dispatches.

On Connect
----------

``chat.notifications``
~~~~~~~~~~~~~~~~~~~~~~

Dispatched automatically to the connecting user immediately after a successful
connection (when ``ENABLE_NOTIFICATION`` is ``True``).

.. code-block:: javascript

   {
     "eventType": "chat.notifications",
     "data": {
       "<room_uuid>": [
         {
           "id": "<notification_uuid>",
           "notification_type": "NEW_MESSAGE",
           "message": { ... }
         }
       ]
     }
   }

Data is keyed by room UUID. Each value is a list of notification objects for that
room. An empty object (``{}``) means no pending notifications.

Message Events
--------------

``message.send``
~~~~~~~~~~~~~~~~

Send a new message to a room. Requires room membership and send permission.

**Client payload**::

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<room_uuid>",
       "content": "Hello!",
       "extra_fields": {
         "parent_message_id": "<uuid>",   // optional — creates a reply
         "forwarded_from_id": "<uuid>",   // optional — creates a forward
         "media": [                        // optional — attach files
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
   A message cannot be both a reply and a forward.

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "message.dispatch",
     "data": { ... }  // full Message object
   }

``message.acknowledged``
~~~~~~~~~~~~~~~~~~~~~~~~

Inform the server that the client received one or more messages. Updates
``delivered_to`` on each message and removes the user from notification
recipients.

**Client payload**::

   {
     "event_type": "message.acknowledged",
     "data": {
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

**Server dispatch** (sent only to the original message sender(s))::

   {
     "eventType": "messagedelivered.dispatch",
     "data": [ ... ]  // list of updated message objects
   }

``message.read``
~~~~~~~~~~~~~~~~

Mark one or more messages as read.

**Client payload**::

   {
     "event_type": "message.read",
     "data": {
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "readreceipt.dispatch",
     "data": { ... }  // updated message(s) with read_receipts
   }

``message.react``
~~~~~~~~~~~~~~~~~

Add or remove a reaction. One reaction per user per message — adding a new one
replaces the old.

**Client payload (add)**::

   {
     "event_type": "message.react",
     "data": {
       "type": "add",
       "message_id": "<uuid>",
       "reaction_content": "👍"
     }
   }

**Client payload (remove)**::

   {
     "event_type": "message.react",
     "data": {
       "type": "remove",
       "message_id": "<uuid>",
       "reaction_content": "👍"
     }
   }

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "reaction.dispatch",
     "data": {
       "status": "successful",
       "type": "add",
       "message": { ... }
     }
   }

``message.typing``
~~~~~~~~~~~~~~~~~~

Signal that the current user is typing. Not persisted.

**Client payload**::

   {
     "event_type": "message.typing",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "messagetyping.dispatch",
     "data": {
       "username": "alice"
     }
   }

``message.modify``
~~~~~~~~~~~~~~~~~~

Edit or delete messages. Only the original sender can modify their messages.

**Update (single message only)**::

   {
     "event_type": "message.modify",
     "data": {
       "action": "update",
       "message_id": "<uuid>",
       "extra_fields": {
         "content": "Updated content"
       }
     }
   }

**Delete (single or bulk)**::

   {
     "event_type": "message.modify",
     "data": {
       "action": "delete",
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

All messages in a bulk delete must come from the **same room**.

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "messagemodification.dispatch",
     "data": {
       "status": "successful",
       "action": "update",   // or "delete"
       "message": { ... }    // for update; "message_ids": [...] for delete
     }
   }

Room Events
-----------

``room.create``
~~~~~~~~~~~~~~~

Create a new room. The creator is automatically added as a member.

**OneToOneChat**::

   {
     "event_type": "room.create",
     "data": {
       "type": "OneToOneChat",
       "participants": [2]
     }
   }

.. note::

   For ``OneToOneChat``, ``participants`` should contain **only the other user's
   ID**. The creator is added automatically. The total count will be 2.

**GroupChat**::

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

**Channel**::

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

**Server dispatch** (broadcast to all initial members)::

   {
     "eventType": "roomcreate.dispatch",
     "data": { ... }  // full room object with type field
   }

``room.list``
~~~~~~~~~~~~~

Retrieve all rooms the current user belongs to.

**Client payload**::

   {
     "event_type": "room.list",
     "data": {}
   }

**Server dispatch** (sent only to requesting user)::

   {
     "eventType": "roomlist.dispatch",
     "data": [
       {
         "type": "OneToOneChat",
         "id": "<uuid>",
         "peer": { ... },
         "last_message": { ... }
       },
       {
         "type": "GroupChat",
         "id": "<uuid>",
         "name": "Project Team",
         "creator": { ... },
         "last_message": { ... }
       }
     ]
   }

The ``type`` field in each room object identifies the concrete room type.

``room.info``
~~~~~~~~~~~~~

Retrieve full details for a specific room.

**Client payload**::

   {
     "event_type": "room.info",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch** (sent only to requesting user)::

   {
     "eventType": "roominfo.dispatch",
     "data": {
       "type": "GroupChat",
       "id": "<uuid>",
       "name": "...",
       "participants": [...],
       "admins": [...],
       "creator": {...},
       "property": {"preferences": {}},
       ...
     }
   }

``room.messages``
~~~~~~~~~~~~~~~~~

Retrieve messages for a room with optional pagination.

**Client payload**::

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

Omit ``paginate`` to retrieve all messages. Response is sent only to the
requesting user.

**Server dispatch**::

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
         "messages": [ ... ]
       }
     }
   }

``room.join``
~~~~~~~~~~~~~

Join a room. For Channels: allowed if ``is_public`` is ``True``. For GroupChats:
raises an error by default (admin must add you). See :doc:`custom_handlers` to
implement custom approval flows.

**Client payload**::

   {
     "event_type": "room.join",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "roomaddmembers.dispatch",
     "data": {
       "room": { ... },
       "new_members": ["alice"],
       "added_by": "self"
     }
   }

``room.leave``
~~~~~~~~~~~~~~

Leave a room. Not available for ``OneToOneChat``.

**Client payload**::

   {
     "event_type": "room.leave",
     "data": {
       "room_id": "<uuid>"
     }
   }

**Server dispatches**:

Sent to the leaving user::

   {
     "eventType": "roomexit.dispatch",
     "data": {
       "room": { ... },
       "message": "You left Project Team"
     }
   }

Broadcast to remaining members::

   {
     "eventType": "roomremovemembers.dispatch",
     "data": {
       "room": { ... },
       "removed_members": ["alice"],
       "removed_by": "self"
     }
   }

If the room is deleted because it becomes empty::

   {
     "eventType": "roomdelete.dispatch",
     "data": {
       "room_id": "<uuid>"
     }
   }

``room.add_members``
~~~~~~~~~~~~~~~~~~~~

Add users to a room. Requires ``can_add_new_participants`` (GroupChat) or
``can_add_new_subscribers`` (Channel) permission.

**Client payload**::

   {
     "event_type": "room.add_members",
     "data": {
       "room_id": "<uuid>",
       "members": [5, 6, 7]
     }
   }

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "roomaddmembers.dispatch",
     "data": {
       "room": { ... },
       "new_members": ["carol", "dave", "eve"],
       "added_by": "alice"
     }
   }

``room.remove_members``
~~~~~~~~~~~~~~~~~~~~~~~

Remove users from a room. Requires ``can_remove_participants`` (GroupChat) or
``can_remove_subscribers`` (Channel) permission. Room creator cannot be removed
by another admin.

**Client payload**::

   {
     "event_type": "room.remove_members",
     "data": {
       "room_id": "<uuid>",
       "members": [5, 6]
     }
   }

**Server dispatches**:

Sent to each removed user::

   {
     "eventType": "roomexit.dispatch",
     "data": {
       "room": { ... },
       "message": "You have been removed by alice"
     }
   }

Broadcast to remaining members::

   {
     "eventType": "roomremovemembers.dispatch",
     "data": {
       "room": { ... },
       "removed_members": ["carol", "dave"],
       "removed_by": "alice"
     }
   }

``room.modify``
~~~~~~~~~~~~~~~

Admin/moderator-only room management. Requires admin status for most actions;
only the room creator can delete.

**Update room details**::

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

**Delete room** (creator only for GroupChat/Channel)::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "delete"
     }
   }

**Add/remove admin** (GroupChat only)::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_admin",
       "data": {"users": [5, 6]}
     }
   }

**Add/remove moderator** (Channel only)::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_moderator",
       "data": {"users": [8]}
     }
   }

**Grant/revoke permissions**::

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

Valid actions: ``update``, ``delete``, ``add_admin``, ``remove_admin``,
``add_moderator``, ``remove_moderator``, ``add_permission``,
``remove_permission``.

**Server dispatch** (broadcast to all room members)::

   {
     "eventType": "roomupdate.dispatch",
     "data": { ... }  // full updated room object
   }

For delete::

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

Keep the session alive. Send every 15–30 seconds.

**Client payload**::

   {
     "event_type": "session.heartbeat",
     "data": {}
   }

**Server response** (to requesting user only)::

   {"status": "success"}

Display Logic Tips
-------------------

Several dispatch events include context fields to help the frontend display the
right message:

- ``removed_by: "self"`` — the user left voluntarily → display "Alice left"
- ``removed_by: "<username>"`` — the user was removed → display "Bob removed Alice"
- ``added_by: "self"`` — the user joined voluntarily → display "Alice joined"
- ``added_by: "<username>"`` — the user was added by someone → display "Bob added Alice"
