Room Events
===========

Complete reference for room management WebSocket events. These events handle creating, joining, leaving, and modifying chat rooms.

Room Creation
-------------

room.create
~~~~~~~~~~~

Create a new room (OneToOneChat, GroupChat, or Channel).

OneToOneChat Creation
~~~~~~~~~~~~~~~~~~~~~

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.create",
       "data": {
           "type": "OneToOneChat",
           "participants": [user1_id, user2_id],  // Exactly 2 users
           "extra_fields": {  // Optional
               "preferences": {
                   "wallpaper": "blue",
                   "muted": false
               }
           }
       }
   }

**Response Broadcast:**

Both participants receive:

.. code-block:: javascript

   {
       "eventType": "roomcreate.dispatch",
       "data": {
           "id": "room-uuid",
           "type": "OneToOneChat",
           "created_at": "2025-01-03T10:30:00Z",
           "updated_at": "2025-01-03T10:30:00Z",
           "preferences": {},
           "last_message": null,
           "participants": [
               {
                   "id": 1,
                   "username": "alice",
                   "email": "alice@example.com"
               },
               {
                   "id": 2,
                   "username": "bob",
                   "email": "bob@example.com"
               }
           ]
       }
   }

GroupChat Creation
~~~~~~~~~~~~~~~~~~

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.create",
       "data": {
           "type": "GroupChat",
           "name": "Project Team",  // Required
           "description": "Team collaboration space",  // Optional
           "participants": [user2_id, user3_id],  // Creator added automatically
           "extra_fields": {  // Optional
               "max_participants": 50,
               "avatar": "https://example.com/avatar.jpg",
               "group_locked": false,
               "join_approval_required": false,
               "preferences": {}
           }
       }
   }

**Response Broadcast:**

All participants (including creator) receive:

.. code-block:: javascript

   {
       "eventType": "roomcreate.dispatch",
       "data": {
           "id": "group-uuid",
           "type": "GroupChat",
           "name": "Project Team",
           "description": "Team collaboration space",
           "creator": {
               "id": 1,
               "username": "alice"
           },
           "participants": [
               {/* creator */},
               {/* user2 */},
               {/* user3 */}
           ],
           "admins": [
               {/* creator - added automatically */}
           ],
           "max_participants": 50,
           "avatar": "https://example.com/avatar.jpg",
           "join_approval_required": false,
           "group_locked": false,
           "created_at": "2025-01-03T10:30:00Z",
           // ... other fields
       }
   }

Channel Creation
~~~~~~~~~~~~~~~~

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.create",
       "data": {
           "type": "Channel",
           "name": "Announcements",  // Required
           "description": "Company updates",  // Optional
           "subscribers": [user2_id, user3_id],  // Creator added automatically
           "extra_fields": {  // Optional
               "is_public": true,
               "max_subscribers": 500,
               "avatar": "https://example.com/channel.jpg",
               "preferences": {}
           }
       }
   }

**Response Broadcast:**

All subscribers (including creator) receive:

.. code-block:: javascript

   {
       "eventType": "roomcreate.dispatch",
       "data": {
           "id": "channel-uuid",
           "type": "Channel",
           "name": "Announcements",
           "description": "Company updates",
           "creator": {
               "id": 1,
               "username": "alice"
           },
           "subscribers": [
               {/* creator */},
               {/* user2 */},
               {/* user3 */}
           ],
           "moderators": [
               {/* creator - added automatically */}
           ],
           "is_public": true,
           "max_subscribers": 500,
           "avatar": "https://example.com/channel.jpg",
           "created_at": "2025-01-03T10:30:00Z",
           // ... other fields
       }
   }

**Important Notes:**

- Creator automatically added as participant/subscriber
- Creator automatically added as admin/moderator
- Creator granted default permissions via signals
- System prevents duplicate OneToOneChat between same users

Room Listing
------------

room.list
~~~~~~~~~

Retrieve all rooms the user belongs to.

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.list",
       "data": {}  // Empty data object
   }

**Response:**

Only the requesting user receives:

.. code-block:: javascript

   {
       "eventType": "roomlist.dispatch",
       "data": [
           {
               "id": "room-uuid-1",
               "type": "OneToOneChat",
               "peer": {  // For OneToOneChat only
                   "id": 2,
                   "username": "bob"
               },
               "last_message": {
                   "id": "message-uuid",
                   "content": "Last message...",
                   "created_at": "2025-01-03T10:30:00Z"
               },
               "created_at": "2025-01-02T08:00:00Z",
               "updated_at": "2025-01-03T10:30:00Z"
           },
           {
               "id": "room-uuid-2",
               "type": "GroupChat",
               "name": "Project Team",
               "description": "Team space",
               "creator": {
                   "id": 1,
                   "username": "alice"
               },
               "last_message": {/* ... */},
               "created_at": "2025-01-01T10:00:00Z"
           },
           {
               "id": "room-uuid-3",
               "type": "Channel",
               "name": "Announcements",
               "is_public": true,
               "creator": {/* ... */},
               "last_message": {/* ... */},
               "created_at": "2025-01-01T09:00:00Z"
           }
       ]
   }

**Example:**

.. code-block:: javascript

   // Load user's rooms on connection
   ws.onopen = () => {
       ws.send(JSON.stringify({
           event_type: "room.list",
           data: {}
       }));
   };

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.eventType === 'roomlist.dispatch') {
           const rooms = response.data;
           displayRoomList(rooms);
       }
   };

**Notes:**

- Ordered by last message timestamp (most recent first)
- Includes simplified last_message for preview
- For OneToOneChat, includes ``peer`` (the other participant)
- Empty array returned if user has no rooms

Room Details
------------

room.info
~~~~~~~~~

Get detailed information about a specific room.

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.info",
       "data": {
           "room_id": "room-uuid"
       }
   }

**Response:**

Only the requesting user receives:

.. code-block:: javascript

   {
       "eventType": "roominfo.dispatch",
       "data": {
           // Full room object with all details
           "id": "room-uuid",
           "type": "GroupChat",
           "name": "Project Team",
           "description": "Team collaboration",
           "creator": {/* ... */},
           "participants": [/* full list */],
           "admins": [/* full list */],
           "max_participants": 100,
           "avatar": "https://example.com/avatar.jpg",
           "join_approval_required": false,
           "group_locked": false,
           "preferences": {},
           "created_at": "2025-01-01T10:00:00Z",
           "updated_at": "2025-01-03T10:30:00Z"
       }
   }

**Example:**

.. code-block:: javascript

   function getRoomInfo(roomId) {
       ws.send(JSON.stringify({
           event_type: "room.info",
           data: { room_id: roomId }
       }));
   }

   // Display room settings/info page
   getRoomInfo(currentRoomId);

Joining Rooms
-------------

room.join
~~~~~~~~~

Join a public channel or request to join a room.

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.join",
       "data": {
           "room_id": "room-uuid"
       }
   }

**Response Broadcast (Success):**

All room members receive:

.. code-block:: javascript

   {
       "eventType": "roomaddmembers.dispatch",
       "data": {
           "room": {/* updated room object */},
           "new_members": ["alice"],  // Username of joiner
           "added_by": "self"  // Indicates user joined themselves
       }
   }

**Behavior by Room Type:**

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Room Type
     - Allowed
     - Error if Not Allowed
   * - OneToOneChat
     - Never
     - "You can only join a channel/group chat"
   * - GroupChat
     - Never (by default)
     - "Ask an admin to add you to the group"
   * - Channel (public)
     - Yes
     - N/A
   * - Channel (private)
     - No
     - "Channel is private, ask a moderator"

**Example:**

.. code-block:: javascript

   // Join public channel
   function joinChannel(channelId) {
       ws.send(JSON.stringify({
           event_type: "room.join",
           data: { room_id: channelId }
       }));
   }

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.eventType === 'roomaddmembers.dispatch') {
           if (response.data.added_by === 'self') {
               console.log('Successfully joined!');
           }
       }
   };

**Error Handling:**

.. code-block:: javascript

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.error) {
           if (response.error.code === 4003) {
               // Validation error - can't join this room type
               showError(response.error.detail);
           }
       }
   };

Leaving Rooms
-------------

room.leave
~~~~~~~~~~

Leave a group chat or channel.

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.leave",
       "data": {
           "room_id": "room-uuid"
       }
   }

**Response to Leaver:**

Only the user who left receives:

.. code-block:: javascript

   {
       "eventType": "roomexit.dispatch",
       "data": {
           "room": {/* room object */},
           "message": "You left Project Team"
       }
   }

**Response to Remaining Members:**

All other room members receive:

.. code-block:: javascript

   {
       "eventType": "roomremovemembers.dispatch",
       "data": {
           "room": {/* updated room object */},
           "removed_members": ["alice"],
           "removed_by": "self"  // Indicates voluntary leave
       }
   }

**Example:**

.. code-block:: javascript

   function leaveRoom(roomId) {
       ws.send(JSON.stringify({
           event_type: "room.leave",
           data: { room_id: roomId }
       }));
   }

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.eventType === 'roomexit.dispatch') {
           // User successfully left
           navigateToRoomList();
       }
   };

**Important Notes:**

- Can only leave GroupChat or Channel
- Cannot leave OneToOneChat (2-participant rule)
- If last member leaves GroupChat/Channel, room is deleted (signal)
- Creator can leave their own room

Room Modification
-----------------

room.modify
~~~~~~~~~~~

Update room settings, permissions, or roles (admin/moderator only).

Update Room Details
~~~~~~~~~~~~~~~~~~~

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "room-uuid",
           "action": "update",
           "data": {
               "name": "Updated Team Name",
               "description": "New description",
               "preferences": {
                   "theme": "dark",
                   "notifications": true
               }
           }
       }
   }

**Response Broadcast:**

All room members receive:

.. code-block:: javascript

   {
       "eventType": "roomupdate.dispatch",
       "data": {
           // Full updated room object
           "id": "room-uuid",
           "name": "Updated Team Name",
           "description": "New description",
           // ... other fields
       }
   }

Add/Remove Permissions
~~~~~~~~~~~~~~~~~~~~~~

**Request (Add Permission):**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "group-uuid",
           "action": "add_permission",
           "data": {
               "users": [user_id1, user_id2],
               "permission": ["can_add_new_participants", "can_remove_participants"]
           }
       }
   }

**Request (Remove Permission):**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "channel-uuid",
           "action": "remove_permission",
           "data": {
               "users": [user_id],
               "permission": ["can_send_messages"]
           }
       }
   }

**Valid Permissions:**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Room Type
     - Available Permissions
   * - GroupChat
     - ``can_add_new_participants``, ``can_remove_participants``
   * - Channel
     - ``can_send_messages``, ``can_add_new_subscribers``, ``can_remove_subscribers``

Add/Remove Admins (GroupChat)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Request (Add Admin):**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "group-uuid",
           "action": "add_admin",
           "data": {
               "users": [user_id1, user_id2]
           }
       }
   }

**Request (Remove Admin):**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "group-uuid",
           "action": "remove_admin",
           "data": {
               "users": [user_id]
           }
       }
   }

Add/Remove Moderators (Channel)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Request (Add Moderator):**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "channel-uuid",
           "action": "add_moderator",
           "data": {
               "users": [user_id]
           }
       }
   }

**Request (Remove Moderator):**

.. code-block:: javascript

   {
       "event_type": "room.modify",
       "data": {
           "room_id": "channel-uuid",
           "action": "remove_moderator",
           "data": {
               "users": [user_id]
           }
       }
   }

**Notes on Role Management:**

- Creator cannot be removed from admins/moderators
- Creator is automatically excluded from role changes
- Adding as admin/moderator grants default permissions (via signals)
- Removing from admin/moderator revokes permissions (via signals)

**Example Implementation:**

.. code-block:: javascript

   class RoomManager {
       constructor(roomId, ws) {
           this.roomId = roomId;
           this.ws = ws;
       }

       // Update room details
       updateRoom(updates) {
           this.ws.send(JSON.stringify({
               event_type: "room.modify",
               data: {
                   room_id: this.roomId,
                   action: "update",
                   data: updates
               }
           }));
       }

       // Grant posting permission in channel
       grantPostPermission(userId) {
           this.ws.send(JSON.stringify({
               event_type: "room.modify",
               data: {
                   room_id: this.roomId,
                   action: "add_permission",
                   data: {
                       users: [userId],
                       permission: ["can_send_messages"]
                   }
               }
           }));
       }

       // Promote to admin (GroupChat)
       promoteToAdmin(userIds) {
           this.ws.send(JSON.stringify({
               event_type: "room.modify",
               data: {
                   room_id: this.roomId,
                   action: "add_admin",
                   data: { users: userIds }
               }
           }));
       }

       // Promote to moderator (Channel)
       promoteToModerator(userIds) {
           this.ws.send(JSON.stringify({
               event_type: "room.modify",
               data: {
                   room_id: this.roomId,
                   action: "add_moderator",
                   data: { users: userIds }
               }
           }));
       }
   }

   // Usage
   const roomManager = new RoomManager(roomId, ws);
   roomManager.updateRoom({
       name: "New Team Name",
       description: "Updated description"
   });

Permission Requirements
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Action
     - Required Permission
   * - ``room.create``
     - Authenticated user (any)
   * - ``room.list``
     - Authenticated user (any)
   * - ``room.info``
     - Room member
   * - ``room.join``
     - Public channel: any user; Private: must be added
   * - ``room.leave``
     - Room member
   * - ``room.modify``
     - Creator, admin (GroupChat), or moderator (Channel)

Error Responses
---------------

All room events can return errors:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,  // Validation error
           "detail": "Maximum number of group participants exceeded"
       }
   }

Common error codes:

- ``4001``: Authentication failed
- ``4002``: Permission denied
- ``4003``: Validation error (max participants, invalid room type, etc.)
- ``4004``: Resource not found (room doesn't exist)
- ``4005``: Integrity error (duplicate OneToOneChat, etc.)

Complete Example
----------------

.. code-block:: javascript

   class RoomService {
       constructor(ws) {
           this.ws = ws;
           this.rooms = [];
           this.setupListeners();
       }

       setupListeners() {
           this.ws.onmessage = (event) => {
               const response = JSON.parse(event.data);
               this.handleRoomEvent(response);
           };
       }

       handleRoomEvent(response) {
           switch (response.eventType) {
               case 'roomcreate.dispatch':
                   this.onRoomCreated(response.data);
                   break;
               case 'roomlist.dispatch':
                   this.onRoomsList(response.data);
                   break;
               case 'roominfo.dispatch':
                   this.onRoomInfo(response.data);
                   break;
               case 'roomaddmembers.dispatch':
                   this.onMembersAdded(response.data);
                   break;
               case 'roomremovemembers.dispatch':
                   this.onMembersRemoved(response.data);
                   break;
               case 'roomexit.dispatch':
                   this.onLeftRoom(response.data);
                   break;
               case 'roomupdate.dispatch':
                   this.onRoomUpdated(response.data);
                   break;
           }
       }

       // Create different room types
       createDirectMessage(userId) {
           this.ws.send(JSON.stringify({
               event_type: "room.create",
               data: {
                   type: "OneToOneChat",
                   participants: [userId]
               }
           }));
       }

       createGroup(name, description, memberIds) {
           this.ws.send(JSON.stringify({
               event_type: "room.create",
               data: {
                   type: "GroupChat",
                   name: name,
                   description: description,
                   participants: memberIds,
                   extra_fields: {
                       max_participants: 100
                   }
               }
           }));
       }

       createChannel(name, description, isPublic) {
           this.ws.send(JSON.stringify({
               event_type: "room.create",
               data: {
                   type: "Channel",
                   name: name,
                   description: description,
                   subscribers: [],
                   extra_fields: {
                       is_public: isPublic,
                       max_subscribers: 500
                   }
               }
           }));
       }

       // Load rooms
       loadRooms() {
           this.ws.send(JSON.stringify({
               event_type: "room.list",
               data: {}
           }));
       }

       // Get room details
       getRoomDetails(roomId) {
           this.ws.send(JSON.stringify({
               event_type: "room.info",
               data: { room_id: roomId }
           }));
       }

       // Join/leave
       joinRoom(roomId) {
           this.ws.send(JSON.stringify({
               event_type: "room.join",
               data: { room_id: roomId }
           }));
       }

       leaveRoom(roomId) {
           this.ws.send(JSON.stringify({
               event_type: "room.leave",
               data: { room_id: roomId }
           }));
       }

       // Event handlers
       onRoomCreated(room) {
           console.log('Room created:', room);
           this.rooms.push(room);
           this.renderRoomList();
       }

       onRoomsList(rooms) {
           this.rooms = rooms;
           this.renderRoomList();
       }

       onRoomInfo(room) {
           this.displayRoomSettings(room);
       }

       onMembersAdded(data) {
           console.log('Members added:', data.new_members);
           this.updateRoom(data.room);
       }

       onMembersRemoved(data) {
           console.log('Members removed:', data.removed_members);
           this.updateRoom(data.room);
       }

       onLeftRoom(data) {
           console.log('Left room:', data.message);
           this.rooms = this.rooms.filter(r => r.id !== data.room.id);
           this.renderRoomList();
       }

       onRoomUpdated(room) {
           const index = this.rooms.findIndex(r => r.id === room.id);
           if (index !== -1) {
               this.rooms[index] = room;
           }
           this.renderRoomList();
       }

       // Helper methods
       updateRoom(room) {
           const index = this.rooms.findIndex(r => r.id === room.id);
           if (index !== -1) {
               this.rooms[index] = room;
               this.renderRoomList();
           }
       }

       renderRoomList() {
           // Your UI rendering logic
       }

       displayRoomSettings(room) {
           // Your settings UI logic
       }
   }

   // Usage
   const roomService = new RoomService(ws);
   roomService.loadRooms();

Next Steps
----------

- :doc:`member-management` - Adding and removing room members
- :doc:`message-events` - Working with messages
- :doc:`error-codes` - Complete error reference
- :doc:`../frontend/best-practices` - Frontend implementation patterns