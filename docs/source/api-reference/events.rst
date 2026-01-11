WebSocket Events Reference
===========================

Complete reference for all WebSocket events. Every event includes request format, response format, permissions required, and examples.

.. contents:: Table of Contents
   :local:
   :depth: 2

Event Structure
---------------

All WebSocket communication follows a consistent structure.

Outgoing (Client → Server)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
       "event_type": "string",
       "data": {
           // Event-specific data
       }
   }

Incoming (Server → Client)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
       "type": "broadcast_group",
       "eventType": "string.dispatch",
       "data": {
           // Event-specific response
       }
   }

.. note::
   The ``type`` field is used internally by Channels. Focus on ``eventType`` and ``data`` for your application logic.

Error Responses
~~~~~~~~~~~~~~~

When an error occurs, you'll receive:

.. code-block:: json

   {
       "error": {
           "code": 4003,
           "detail": "Validation error message"
       }
   }

.. note::

   The error message is intentionally minimal and not explicit for security reasons.
   You can override ``ExceptionHandlerClass`` in your settings to change this behavior.

Error Codes
^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 15 30 55

   * - Code
     - Meaning
     - Common Causes
   * - ``4001``
     - Authentication failed
     - Not logged in, invalid token
   * - ``4002``
     - Permission denied
     - Not a room member, insufficient privileges
   * - ``4003``
     - Validation error
     - Missing fields, invalid data types
   * - ``4004``
     - Resource not found
     - Room/message doesn't exist
   * - ``4005``
     - Integrity error
     - Duplicate OneToOneChat, constraint violation
   * - ``4006``
     - Internal server error
     - Unexpected server-side error
     - Some uncaught validation exception that don't need to be propagated to the client

Room Management Events
----------------------

room.create
~~~~~~~~~~~

Create a new chat room (OneToOneChat, GroupChat, or Channel).

**Request**

.. code-block:: json

   {
       "event_type": "room.create",
       "data": {
           "type": "OneToOneChat" | "GroupChat" | "Channel",
           "participants": [2, 3],
           "subscribers": [2, 3],
           "name": "string",
           "description": "string",
           "extra_fields": {
               "preferences": {},
               "max_participants": 100,
               "max_subscribers": 500,
               "is_public": true,
               "join_approval_required": false,
               "avatar": "https://example.com/avatar.jpg",
               "group_locked": false
           }
       }
   }

**Field Requirements**

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Field
     - OneToOneChat
     - GroupChat
     - Channel
   * - ``type``
     - ✅ Required
     - ✅ Required
     - ✅ Required
   * - ``participants``
     - ✅ Required (1 user)
     - ⚠️ Optional
     - ❌ Not used
   * - ``subscribers``
     - ❌ Not used
     - ❌ Not used
     - ⚠️ Optional
   * - ``name``
     - ❌ Not used
     - ✅ Required
     - ✅ Required
   * - ``description``
     - ❌ Not used
     - ⚠️ Optional
     - ⚠️ Optional

**Response**

.. code-block:: json

   {
       "eventType": "roomcreate.dispatch",
       "data": {
           "id": "550e8400-e29b-41d4-a716-446655440000",
           "type": "OneToOneChat",
           "participants": [
               {
                   "id": 1,
                   "username": "alice",
                   "email": "alice@example.com",
                   "first_name": "Alice",
                   "last_name": "Smith"
               },
               {
                   "id": 2,
                   "username": "bob",
                   "email": "bob@example.com",
                   "first_name": "Bob",
                   "last_name": "Johnson"
               }
           ],
           "created_at": "2024-01-10T12:00:00Z",
           "updated_at": "2024-01-10T12:00:00Z",
           "preferences": {}
       }
   }

**Broadcast**: All room members receive ``roomcreate.dispatch``

**Permissions**: Authenticated users only

**Errors**

* ``4003``: Validation error (invalid type, missing required fields)
* ``4005``: Chat already exists (OneToOneChat only)

**Examples**

OneToOneChat
^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.create',
       data: {
           type: 'OneToOneChat',
           participants: [2]  // Just the other user's ID
       }
   }));

GroupChat with Settings
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.create',
       data: {
           type: 'GroupChat',
           name: 'Project Alpha Team',
           description: 'Discussion for Project Alpha',
           participants: [2, 3, 4, 5],
           extra_fields: {
               max_participants: 20,
               join_approval_required: true,
               avatar: 'https://cdn.example.com/group-avatar.jpg',
               preferences: {
                   theme: 'dark',
                   notifications: 'mentions_only'
               }
           }
       }
   }));

Public Channel
^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.create',
       data: {
           type: 'Channel',
           name: 'Company Announcements',
           description: 'Official company-wide announcements',
           subscribers: [2, 3],  // Initial subscribers
           extra_fields: {
               is_public: true,
               max_subscribers: 1000,
               avatar: 'https://cdn.example.com/channel-logo.jpg'
           }
       }
   }));

room.list
~~~~~~~~~

Retrieve all rooms the current user is part of.

**Request**

.. code-block:: json

   {
       "event_type": "room.list",
       "data": {}
   }

**Response**

.. code-block:: json

   {
       "eventType": "roomlist.dispatch",
       "data": [
           {
               "id": "uuid",
               "type": "OneToOneChat",
               "peer": {
                   "id": 2,
                   "username": "bob",
                   "email": "bob@example.com",
                   "first_name": "Bob",
                   "last_name": "Johnson"
               },
               "last_message": {
                   "id": "msg-uuid",
                   "content": "Hey, how are you?",
                   "sender": {"id": 2, "username": "bob"},
                   "created_at": "2024-01-10T12:00:00Z"
               },
               "created_at": "2024-01-10T10:00:00Z",
               "updated_at": "2024-01-10T12:00:00Z"
           },
           {
               "id": "uuid",
               "type": "GroupChat",
               "name": "Project Alpha Team",
               "description": "Discussion for Project Alpha",
               "creator": {"id": 1, "username": "alice"},
               "last_message": {
                   "id": "msg-uuid",
                   "content": "Meeting at 3pm",
                   "sender": {"id": 3, "username": "charlie"},
                   "created_at": "2024-01-10T11:30:00Z"
               },
               "created_at": "2024-01-09T09:00:00Z",
               "updated_at": "2024-01-10T11:30:00Z"
           }
       ]
   }

**Broadcast**: Only to the requesting user

**Permissions**: Authenticated users only

**Notes**

* Rooms are ordered by ``last_message.created_at`` (most recent first)
* For OneToOneChat, only the ``peer`` is returned (the other participant)
* For GroupChat/Channel, participant/subscriber lists are excluded (use ``room.info`` to get full details)

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.list',
       data: {}
   }));

   socket.onmessage = function(e) {
       const response = JSON.parse(e.data);
       if (response.eventType === 'roomlist.dispatch') {
           console.log('User has', response.data.length, 'rooms');
           response.data.forEach(room => {
               console.log('Room:', room.type, room.name || room.peer.username);
           });
       }
   };

room.info
~~~~~~~~~

Get detailed information about a specific room, including all members.

**Request**

.. code-block:: json

   {
       "event_type": "room.info",
       "data": {
           "room_id": "uuid"
       }
   }

**Response (GroupChat)**

.. code-block:: json

   {
       "eventType": "roominfo.dispatch",
       "data": {
           "id": "uuid",
           "type": "GroupChat",
           "name": "Project Alpha Team",
           "description": "Discussion for Project Alpha",
           "creator": {"id": 1, "username": "alice"},
           "participants": [
               {"id": 1, "username": "alice"},
               {"id": 2, "username": "bob"},
               {"id": 3, "username": "charlie"}
           ],
           "admins": [
               {"id": 1, "username": "alice"}
           ],
           "max_participants": 50,
           "join_approval_required": false,
           "group_locked": false,
           "avatar": "https://cdn.example.com/avatar.jpg",
           "created_at": "2024-01-09T09:00:00Z",
           "updated_at": "2024-01-10T11:30:00Z",
           "preferences": {"theme": "dark"}
       }
   }

**Broadcast**: Only to the requesting user

**Permissions**: Must be a member of the room

**Errors**

* ``4004``: Room not found
* ``4002``: User not a member of this room

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.info',
       data: {
           room_id: '550e8400-e29b-41d4-a716-446655440000'
       }
   }));

room.join
~~~~~~~~~

Join a public channel. (GroupChats require admin invitation)

**Request**

.. code-block:: json

   {
       "event_type": "room.join",
       "data": {
           "room_id": "uuid"
       }
   }

**Response**

.. code-block:: json

   {
       "eventType": "roomaddmembers.dispatch",
       "data": {
           "room": {
               "id": "uuid",
               "type": "Channel",
               "name": "Company Announcements"
           },
           "new_members": ["your_username"],
           "added_by": "self"
       }
   }

**Broadcast**: All room members receive ``roomaddmembers.dispatch``

**Permissions**

* Channel must be public (``is_public=True``)
* Cannot join GroupChats (admin must add you, you can change this)
* Cannot join private Channels (moderator must add you)

**Errors**

* ``4003``: Cannot join GroupChat (ValidationError)
* ``4003``: Channel is private (ValidationError)
* ``4004``: Room not found

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.join',
       data: {
           room_id: 'channel-uuid'
       }
   }));

room.leave
~~~~~~~~~~

Leave a GroupChat or Channel. (Cannot leave OneToOneChat)

**Request**

.. code-block:: json

   {
       "event_type": "room.leave",
       "data": {
           "room_id": "uuid"
       }
   }

**Response (to you)**

.. code-block:: json

   {
       "eventType": "roomexit.dispatch",
       "data": {
           "room": {
               "id": "uuid",
               "type": "GroupChat",
               "name": "Project Alpha Team"
           },
           "message": "You left Project Alpha Team"
       }
   }

**Response (to others)**

.. code-block:: json

   {
       "eventType": "roomremovemembers.dispatch",
       "data": {
           "room": {"id": "uuid"},
           "removed_members": ["your_username"],
           "removed_by": "self"
       }
   }

**Broadcast**

* You receive ``roomexit.dispatch``
* Other room members receive ``roomremovemembers.dispatch``

**Permissions**: Must be a member of the room

**Errors**

* ``4003``: Cannot leave OneToOneChat (ValidationError)
* ``4002``: Not a member of this room

**Notes**

* If you're the room creator, you'll lose all privileges but remain the creator in the database
* If you're an admin/moderator, you'll be removed from that role
* If room has no members left after you leave, the room is automatically deleted

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.leave',
       data: {
           room_id: 'group-uuid'
       }
   }));

room.messages
~~~~~~~~~~~~~

Retrieve message history for a room with optional pagination.

**Request**

.. code-block:: json

   {
       "event_type": "room.messages",
       "data": {
           "room_id": "uuid",
           "paginate": {
               "page": 1,
               "size": 20
           }
       }
   }

**Response**

.. code-block:: json

   {
       "eventType": "roommessages.dispatch",
       "data": {
           "room_id": "uuid",
           "messages": [
               {
                   "id": "msg-uuid",
                   "sender": {
                       "id": 1,
                       "username": "alice"
                   },
                   "content": "Hello, world!",
                   "created_at": "2024-01-10T12:00:00Z",
                   "updated_at": "2024-01-10T12:00:00Z",
                   "is_edited": false,
                   "is_deleted": false,
                   "is_forwarded": false,
                   "parent_message": null,
                   "forwarded_from": null,
                   "reactions": [],
                   "read_receipts": [],
                   "attachments": [],
                   "delivered_to": ["bob", "charlie"]
               }
           ]
       },
       "has_next": true,
       "has_previous": false,
       "next_page_number": 2,
       "prev_page_number": null,
       "page": 1,
       "size": 20
   }

**Broadcast**: Only to the requesting user

**Permissions**: Must be a member of the room

**Notes**

* Messages are ordered by ``created_at`` descending (newest first)
* Recommended page size: 20-30 messages
* Pagination fields only appear if ``paginate`` is provided

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: "room.messages",
       data: {
           room_id: "room-uuid",
           paginate: {
               page: 1,
               size: 50
           }
       }
   }));

room.add_members
~~~~~~~~~~~~~~~~

Add members to a GroupChat or subscribers to a Channel. (Admins/Moderators only)

**Request**

.. code-block:: json

   {
       "event_type": "room.add_members",
       "data": {
           "room_id": "uuid",
           "members": [4, 5, 6]
       }
   }

**Response**

.. code-block:: json

   {
       "eventType": "roomaddmembers.dispatch",
       "data": {
           "room": {
               "id": "uuid",
               "type": "GroupChat",
               "name": "Project Alpha Team"
           },
           "new_members": ["david", "emma", "frank"],
           "added_by": "alice"
       }
   }

**Broadcast**: All room members (including new members) receive ``roomaddmembers.dispatch``

**Permissions**

* GroupChat: Must be creator, admin, or have ``can_add_new_participants`` permission
* Channel: Must be creator, moderator, or have ``can_add_new_subscribers`` permission

**Errors**

* ``4002``: Permission denied
* ``4003``: Maximum participants/subscribers exceeded

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.add_members',
       data: {
           room_id: 'group-uuid',
           members: [4, 5]
       }
   }));

room.remove_members
~~~~~~~~~~~~~~~~~~~

Remove members from a GroupChat or Channel. (Admins/Moderators only)

**Request**

.. code-block:: json

   {
       "event_type": "room.remove_members",
       "data": {
           "room_id": "uuid",
           "members": [4]
       }
   }

**Response (to removed user)**

.. code-block:: json

   {
       "eventType": "roomexit.dispatch",
       "data": {
           "room": {"id": "uuid"},
           "message": "You have been removed by alice"
       }
   }

**Response (to others)**

.. code-block:: json

   {
       "eventType": "roomremovemembers.dispatch",
       "data": {
           "room": {"id": "uuid"},
           "removed_members": ["david"],
           "removed_by": "alice"
       }
   }

**Broadcast**

* Removed users receive ``roomexit.dispatch``
* Remaining members receive ``roomremovemembers.dispatch``

**Permissions**

* GroupChat: Must be creator, admin, or have ``can_remove_participants`` permission
* Channel: Must be creator, moderator, or have ``can_remove_subscribers`` permission

**Notes**

* Cannot remove the room creator unless the creator removes themselves
* Removed users lose all permissions and admin/moderator status

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.remove_members',
       data: {
           room_id: 'group-uuid',
           members: [4]
       }
   }));

room.modify
~~~~~~~~~~~

Modify room settings, permissions, or admin/moderator roles. (Admins/Moderators only)

**Request**

.. code-block:: json

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "uuid",
           "action": "update" | "add_permission" | "remove_permission" | 
                     "add_admin" | "remove_admin" | "add_moderator" | "remove_moderator",
           "data": {
               "name": "New Name",
               "description": "New description",
               "preferences": {},
               "users": [2, 3],
               "permissions": ["can_add_new_participants"]
           }
       }
   }

**Actions**

update
^^^^^^

Update room name, description, or preferences.

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'update',
           data: {
               name: 'Updated Team Name',
               description: 'New description',
               preferences: {theme: 'light'}
           }
       }
   }));

add_permission / remove_permission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Grant or revoke permissions to specific users.

**GroupChat permissions:**

* ``can_add_new_participants``
* ``can_remove_participants``

**Channel permissions:**

* ``can_add_new_subscribers``
* ``can_remove_subscribers``
* ``can_send_messages``

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'add_permission',
           data: {
               users: [2, 3],
               permissions: ['can_add_new_participants', 'can_remove_participants']
           }
       }
   }));

add_admin / remove_admin
^^^^^^^^^^^^^^^^^^^^^^^^^

Promote or demote GroupChat admins.

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'add_admin',
           data: {
               users: [2]
           }
       }
   }));

add_moderator / remove_moderator
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Promote or demote Channel moderators.

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'channel-uuid',
           action: 'add_moderator',
           data: {
               users: [2]
           }
       }
   }));

**Response**

.. code-block:: json

   {
       "eventType": "roomupdate.dispatch",
       "data": {
           // Complete updated room object
       }
   }

**Broadcast**: All room members receive ``roomupdate.dispatch``

**Permissions**: Must be creator or admin/moderator

**Notes**

* Cannot modify permissions for the room creator
* Users must already be room members

Messaging Events
----------------

message.send
~~~~~~~~~~~~

Send a text message, reply, or forwarded message with optional media attachments.

**Request**

.. code-block:: json

   {
       "event_type": "message.send",
       "data": {
           "room_id": "uuid",
           "content": "Hello, world!",
           "extra_fields": {
               "parent_message_id": "uuid",
               "forwarded_from_id": "uuid",
               "media": [
                   {
                       "media_url": "https://cdn.example.com/image.jpg",
                       "media_type": "image",
                       "mime_type": "image/jpeg",
                       "file_size": 204800,
                       "caption": "Check this out!",
                       "metadata": {
                           "width": 1920,
                           "height": 1080,
                           "orientation": "landscape"
                       }
                   }
               ]
           }
       }
   }

**Fields**

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Required
     - Description
   * - ``room_id``
     - ✅ Yes
     - Room UUID
   * - ``content``
     - ✅ Yes
     - Message text (HTML sanitized)
   * - ``parent_message_id``
     - ⚠️ Optional
     - For reply messages (creates a thread)
   * - ``forwarded_from_id``
     - ⚠️ Optional
     - Original message ID (for forwarding)
   * - ``media``
     - ⚠️ Optional
     - Array of media attachments

**Response**

.. code-block:: json

   {
       "eventType": "message.dispatch",
       "data": {
           "id": "msg-uuid",
           "room": {"id": "room-uuid"},
           "sender": {
               "id": 1,
               "username": "alice"
           },
           "content": "Hello, world!",
           "created_at": "2024-01-10T12:00:00Z",
           "is_edited": false,
           "is_deleted": false,
           "is_forwarded": false,
           "parent_message": null,
           "forwarded_from": null,
           "reactions": [],
           "read_receipts": [],
           "attachments": [],
           "delivered_to": []
       }
   }

**Broadcast**: All room members receive ``message.dispatch``

**Permissions**

* OneToOneChat: Must be a participant
* GroupChat: Must be a participant (unless ``group_locked=True``, then only admins/creator)
* Channel: Must be creator, moderator, or have ``can_send_messages`` permission

**Notes**

* HTML content is sanitized (XSS protection)
* Allowed HTML tags: ``b``, ``i``, ``strong``, ``em``, ``a``, ``span``, ``p``, ``ul``, ``ol``, ``li``, ``br``
* Media files must be uploaded separately (to S3/Cloudinary/etc.) before sending
* If ``media`` is provided and ``content`` is empty, content defaults to "Media Files"

**Examples**

Simple Text Message
^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: 'Hello, everyone! 👋'
       }
   }));

Reply Message
^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: 'I agree with this!',
           extra_fields: {
                parent_message_id: 'original-message-uuid'
            }
       }
   }));

Message with Image
^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   // First, upload image to your CDN
   const imageUrl = await uploadToCDN(imageFile);

   // Then send message
   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: 'Check out this screenshot!',
           extra_fields: {
               media: [{
                   media_url: imageUrl,
                   media_type: 'image',
                   mime_type: 'image/png',
                   file_size: 512000,
                   metadata: {
                       width: 1920,
                       height: 1080
                   }
               }]
           }
       }
   }));

Forward Message
^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'different-room-uuid',
           content: 'Forwarded message content',
           extra_fields: {
               forwarded_from_id: 'original-message-uuid'
           }
       }
   }));

.. warning::
   **You cannot both reply AND forward the same message.** A message can be either a reply OR forwarded, not both. This is enforced by a database constraint.

message.acknowledged
~~~~~~~~~~~~~~~~~~~~

Mark messages as delivered to you. This is separate from read receipts.

**Request**

.. code-block:: json

   {
       "event_type": "message.acknowledged",
       "data": {
           "message_id": "uuid" | ["uuid1", "uuid2"]
       }
   }

**Response**

.. code-block:: json

   {
       "status": "successful"
   }

**Broadcast**: Only to the requesting user

**Permissions**: Must have access to the message

**Notes**

* This tracks delivery, not reads
* Used for "delivered to" status in UI
* Automatically removes user from ChatNotification recipients
* Can acknowledge single message or array of messages

**Example**

.. code-block:: javascript

   // Acknowledge single message
   socket.send(JSON.stringify({
       event_type: 'message.acknowledged',
       data: {
           message_id: 'msg-uuid'
       }
   }));

   // Acknowledge multiple messages
   socket.send(JSON.stringify({
       event_type: 'message.acknowledged',
       data: {
           message_id: ['msg-uuid-1', 'msg-uuid-2', 'msg-uuid-3']
       }
   }));

message.read
~~~~~~~~~~~~

Mark messages as read and create read receipts.

**Request**

.. code-block:: json

   {
       "event_type": "message.read",
       "data": {
           "message_id": "uuid" | ["uuid1", "uuid2"]
       }
   }

**Response**

.. code-block:: json

   {
       "eventType": "readreceipt.dispatch",
       "data": {
           // Updated message(s) with new read_receipts
       }
   }

**Broadcast**: All room members receive ``readreceipt.dispatch`` with updated message(s)

**Permissions**: Must have access to the message

**Notes**

* Read receipts only created if you're not the sender
* Can read single message or array
* Updates message's ``read_receipts`` array
* Also triggers ``message.acknowledged`` internally

**Example**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.read',
       data: {
           message_id: ['msg-1', 'msg-2']
       }
   }));

   socket.onmessage = function(e) {
       const response = JSON.parse(e.data);
       if (response.eventType === 'readreceipt.dispatch') {
           // response.data contains updated message(s)
           console.log('Read receipts updated:', response.data);
       }
   };

message.react
~~~~~~~~~~~~~

Add or remove an emoji reaction to a message.

**Request**

.. code-block:: json

   {
       "event_type": "message.react",
       "data": {
           "type": "add" | "remove",
           "message_id": "uuid",
           "reaction_content": "👍"
       }
   }

**Response**

.. code-block:: json

   {
       "eventType": "reaction.dispatch",
       "data": {
           "status": "successful",
           "type": "add",
           "message": {
               // Complete message with updated reactions array
           }
       }
   }

**Broadcast**: All room members receive ``reaction.dispatch``

**Permissions**: Must have access to the message

**Notes**

* Each user can have ONE reaction per message
* Adding a new reaction by the same user on the same message automatically removes the old one
* Reaction content can be any string (typically emoji)

**Examples**

Add Reaction
^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.react',
       data: {
           type: 'add',
           message_id: 'msg-uuid',
           reaction_content: '❤️'
       }
   }));

Remove Reaction
^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.react',
       data: {
           type: 'remove',
           message_id: 'msg-uuid',
           reaction_content: '❤️'
       }
   }));

message.typing
~~~~~~~~~~~~~~

Send typing indicator to other room members.

**Request**

.. code-block:: json

   {
       "event_type": "message.typing",
       "data": {
           "room_id": "uuid"
       }
   }

**Response**

.. code-block:: json

   {
       "eventType": "messagetyping.dispatch",
       "data": {
           "username": "alice"
       }
   }

**Broadcast**: All room members (except sender) receive ``messagetyping.dispatch``

**Permissions**: Same as ``message.send`` for this room

**Notes**

* No automatic timeout - frontend must handle timing
* Recommended: Debounce typing events (e.g., throttle to 1 per second)
* Does NOT create database records

**Example**

.. code-block:: javascript

   let typingTimeout;
   
   messageInput.oninput = function() {
       clearTimeout(typingTimeout);
       
       // Send typing event
       socket.send(JSON.stringify({
           event_type: 'message.typing',
           data: {
               room_id: currentRoomId
           }
       }));
       
       // Clear typing indicator after 3 seconds
       typingTimeout = setTimeout(() => {
           // Remove typing indicator from UI
       }, 3000);
   };

message.modify
~~~~~~~~~~~~~~

Edit or delete messages. (Only message sender can modify)

**Request**

.. code-block:: json

   {
       "event_type": "message.modify",
       "data": {
           "action": "update" | "delete",
           "message_id": "uuid" | ["uuid1", "uuid2"],
           "extra_fields": {
               "content": "Updated content"
           }
       }
   }

**Update Action**

.. code-block:: json

   {
       "event_type": "message.modify",
       "data": {
           "action": "update",
           "message_id": "uuid",
           "extra_fields": {
               "content": "This message has been edited"
           }
       }
   }

**Response (Update)**

.. code-block:: json

   {
       "eventType": "messagemodification.dispatch",
       "data": {
           "status": "successful",
           "action": "update",
           "message": {
               "id": "uuid",
               "content": "This message has been edited",
               "is_edited": true,
               // ... rest of message
           }
       }
   }

**Delete Action**

.. code-block:: json

   {
       "event_type": "message.modify",
       "data": {
           "action": "delete",
           "message_id": ["uuid1", "uuid2"]
       }
   }

**Response (Delete)**

.. code-block:: json

   {
       "eventType": "messagemodification.dispatch",
       "data": {
           "status": "successful",
           "action": "delete",
           "message_ids": ["uuid1", "uuid2"]
       }
   }

**Broadcast**: All room members receive ``messagemodification.dispatch``

**Permissions**: Must be the message sender

**Notes**

* Update: Can only update ONE message at a time
* Delete: Can delete multiple messages at once
* All deleted messages must be from the SAME room
* Soft delete (``MESSAGE_SOFT_DELETE=True``): Sets ``is_deleted=True``
* Hard delete (``MESSAGE_SOFT_DELETE=False``): Removes from database
* Only ``content`` field can be updated

**Examples**

Edit Message
^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.modify',
       data: {
           action: 'update',
           message_id: 'msg-uuid',
           extra_fields: {
               content: 'Edited: This is the corrected message'
           }
       }
   }));

Delete Single Message
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.modify',
       data: {
           action: 'delete',
           message_id: 'msg-uuid'
       }
   }));

Delete Multiple Messages
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.modify',
       data: {
           action: 'delete',
           message_id: ['msg-1', 'msg-2', 'msg-3']
       }
   }));

Media Attachments
-----------------

Media Upload Flow
~~~~~~~~~~~~~~~~~

The package does NOT handle file uploads. You must upload files to your storage service first:

1. **Upload file** to S3/Cloudinary/your CDN
2. **Get URL** from upload response
3. **Send message** with media URL

Example Upload Flow
^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   // Step 1: Upload to S3
   async function uploadFile(file) {
       const formData = new FormData();
       formData.append('file', file);
       
       const response = await fetch('/api/upload/', {
           method: 'POST',
           body: formData
       });
       
       const data = await response.json();
       return data.url;  // S3 URL
   }

   // Step 2: Send message with URL
   const imageUrl = await uploadFile(imageFile);
   
   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: roomId,
           content: 'Check this out!',
           extra_fields: {
               media: [{
                   media_url: imageUrl,
                   media_type: 'image',
                   mime_type: 'image/jpeg',
                   file_size: imageFile.size,
                   metadata: {
                       width: 1920,
                       height: 1080
                   }
               }]
           }
       }
   }));

Media Types
~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - ``media_type``
     - Usage
     - Supported ``mime_type``
   * - ``image``
     - Photos, screenshots
     - ``image/jpeg``, ``image/png``, ``image/gif``, ``image/webp``, ``image/bmp``, ``image/heic``
   * - ``video``
     - Videos, video notes
     - ``video/mp4``, ``video/quicktime``, ``video/webm``, ``video/ogg``, ``video/x-msvideo``, ``video/x-matroska``
   * - ``audio``
     - Audio files, voice notes
     - ``audio/mpeg``, ``audio/mp4``, ``audio/aac``, ``audio/ogg``, ``audio/wav``, ``audio/opus``
   * - ``file``
     - Documents, any file
     - ``application/pdf``, ``application/msword``, ``application/vnd.openxmlformats-officedocument.*``, ``text/plain``, ``text/csv``

Metadata Structure
~~~~~~~~~~~~~~~~~~

**Image Metadata**

.. code-block:: json

   {
       "width": 1920,
       "height": 1080,
       "orientation": "landscape" | "portrait"
   }

**Video Metadata**

.. code-block:: json

   {
       "duration": 15.2,
       "resolution": "1920x1080",
       "fps": 30,
       "orientation": "landscape",
       "video_codec": "h264",
       "audio_codec": "aac"
   }

**Audio/Voice Note Metadata**

.. code-block:: json

   {
       "duration": 2.8,
       "waveform": [0.2, 0.5, 0.1, 0.3, 0.7],
       "bitrate": 96000
   }

.. note::
   Metadata is optional and not enforced. Include what makes sense for your use case.

Complete Example: Image Message
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   async function sendImageMessage(roomId, imageFile, caption) {
       // 1. Upload to your CDN
       const uploadedUrl = await uploadToCDN(imageFile);
       
       // 2. Get image dimensions
       const img = new Image();
       img.src = URL.createObjectURL(imageFile);
       await img.decode();
       
       // 3. Send message
       socket.send(JSON.stringify({
           event_type: 'message.send',
           data: {
               room_id: roomId,
               content: caption || 'Image',
               extra_fields: {
                   media: [{
                       media_url: uploadedUrl,
                       media_type: 'image',
                       mime_type: imageFile.type,
                       file_size: imageFile.size,
                       caption: caption,
                       metadata: {
                           width: img.width,
                           height: img.height,
                           orientation: img.width > img.height ? 'landscape' : 'portrait'
                       }
                   }]
               }
           }
       }));
   }

.. note::
    You can also override _create_message() method on the default EVENT_HANDLER_CLASS to add necessary functionality see See :doc:`Consumer customization <../customization/consumers>`.


Event Summary Table
-------------------

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Event
     - Purpose
     - Response
   * - ``room.create``
     - Create new room
     - ``roomcreate.dispatch``
   * - ``room.list``
     - List all user's rooms
     - ``roomlist.dispatch``
   * - ``room.info``
     - Get room details
     - ``roominfo.dispatch``
   * - ``room.join``
     - Join public channel
     - ``roomaddmembers.dispatch``
   * - ``room.leave``
     - Leave room
     - ``roomexit.dispatch`` + ``roomremovemembers.dispatch``
   * - ``room.messages``
     - Get message history
     - ``roommessages.dispatch``
   * - ``room.add_members``
     - Add users to room
     - ``roomaddmembers.dispatch``
   * - ``room.remove_members``
     - Remove users from room
     - ``roomremovemembers.dispatch`` + ``roomexit.dispatch``
   * - ``room.modify``
     - Update room settings
     - ``roomupdate.dispatch``
   * - ``message.send``
     - Send message
     - ``message.dispatch``
   * - ``message.acknowledged``
     - Mark delivered
     - ``{status: "successful"}``
   * - ``message.read``
     - Mark as read
     - ``readreceipt.dispatch``
   * - ``message.react``
     - Add/remove reaction
     - ``reaction.dispatch``
   * - ``message.typing``
     - Typing indicator
     - ``messagetyping.dispatch``
   * - ``message.modify``
     - Edit/delete message
     - ``messagemodification.dispatch``

Best Practices
--------------

Connection Management
~~~~~~~~~~~~~~~~~~~~~

**Always handle reconnection:**

.. code-block:: javascript

   let socket;
   let reconnectAttempts = 0;
   const maxReconnectAttempts = 5;

   function connect() {
       socket = new WebSocket('ws://localhost:8000/messaging/');
       
       socket.onopen = () => {
           console.log('Connected');
           reconnectAttempts = 0;
           // Rejoin rooms, sync state
       };
       
       socket.onclose = (e) => {
           if (reconnectAttempts < maxReconnectAttempts) {
               setTimeout(() => {
                   reconnectAttempts++;
                   connect();
               }, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000));
           }
       };
   }

   connect();

State Management
~~~~~~~~~~~~~~~~

**Track connection state:**

.. code-block:: javascript

   const ConnectionState = {
       CONNECTING: 'connecting',
       CONNECTED: 'connected',
       DISCONNECTED: 'disconnected',
       RECONNECTING: 'reconnecting'
   };

   let connectionState = ConnectionState.CONNECTING;
   let messageQueue = [];

   function sendMessage(event) {
       if (connectionState === ConnectionState.CONNECTED) {
           socket.send(JSON.stringify(event));
       } else {
           messageQueue.push(event);
       }
   }

   socket.onopen = () => {
       connectionState = ConnectionState.CONNECTED;
       // Send queued messages
       messageQueue.forEach(sendMessage);
       messageQueue = [];
   };

Error Handling
~~~~~~~~~~~~~~

**Always handle errors:**

.. code-block:: javascript

   socket.onmessage = (e) => {
       const response = JSON.parse(e.data);
       
       if (response.error) {
           handleError(response.error);
           return;
       }
       
       handleEvent(response);
   };

   function handleError(error) {
       switch(error.code) {
           case 4001:
               // Redirect to login
               break;
           case 4002:
               // Show permission denied message
               break;
           case 4003:
               // Show validation error
               break;
           default:
               // Show generic error
       }
   }

Optimistic Updates
~~~~~~~~~~~~~~~~~~

**Update UI immediately, rollback on error:**

.. code-block:: javascript

   function sendMessage(content) {
       const tempMessage = {
           id: 'temp-' + Date.now(),
           content: content,
           sender: currentUser,
           created_at: new Date().toISOString(),
           status: 'sending'
       };
       
       // Add to UI immediately
       addMessageToUI(tempMessage);
       
       // Send to server
       socket.send(JSON.stringify({
           event_type: 'message.send',
           data: {room_id: roomId, content: content}
       }));
   }

   socket.onmessage = (e) => {
       const response = JSON.parse(e.data);
       
       if (response.eventType === 'message.dispatch') {
           // Replace temp message with real one
           replaceMessage(tempMessage.id, response.data);
       } else if (response.error) {
           // Remove temp message, show error
           removeMessage(tempMessage.id);
           showError(response.error);
       }
   };

Rate Limiting
~~~~~~~~~~~~~

**Debounce typing indicators:**

.. code-block:: javascript

   import debounce from 'lodash/debounce';

   const sendTypingIndicator = debounce(() => {
       socket.send(JSON.stringify({
           event_type: 'message.typing',
           data: {room_id: currentRoomId}
       }));
   }, 1000, {leading: true, trailing: false});

   messageInput.oninput = sendTypingIndicator;

See Also
--------

* :doc:`../user-guide/frontend-integration` - Complete frontend examples
* :doc:`../customization/consumers` - Add custom events
* :doc:`../troubleshooting` - Common issues and solutions
* :doc:`../advanced/performance` - Optimization tips