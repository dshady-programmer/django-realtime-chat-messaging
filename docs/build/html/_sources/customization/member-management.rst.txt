Member Management
=================

Complete reference for managing room members via WebSocket. These events handle adding and removing users from groups and channels.

Overview
--------

Member management events allow:

- Adding users to GroupChat or Channel
- Removing users from GroupChat or Channel  
- Tracking who performed the action
- Broadcasting changes to all affected users

.. note::
   OneToOneChat has exactly 2 participants and does not support member management events.

Adding Members
--------------

room.add_members
~~~~~~~~~~~~~~~~

Add users to a GroupChat or Channel.

**Permissions Required:**

- Must be room member
- **GroupChat**: Creator, admin, or user with ``can_add_new_participants`` permission
- **Channel**: Creator, moderator, or user with ``can_add_new_subscribers`` permission

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.add_members",
       "data": {
           "room_id": "room-uuid",  // Required
           "members": [user_id1, user_id2, user_id3]  // Required, array of user IDs
       }
   }

**Response Broadcast:**

All room members (including newly added) receive:

.. code-block:: javascript

   {
       "eventType": "roomaddmembers.dispatch",
       "data": {
           "room": {
               // Full updated room object with new members
               "id": "room-uuid",
               "type": "GroupChat",  // or "Channel"
               "name": "Project Team",
               "participants": [  // or "subscribers" for Channel
                   {/* existing member */},
                   {/* existing member */},
                   {/* newly added member 1 */},
                   {/* newly added member 2 */}
               ],
               // ... other room fields
           },
           "new_members": ["alice", "bob"],  // Usernames of added users
           "added_by": "john"  // Username of user who added them (or "self" if user joined via room.join)
       }
   }

**Examples:**

Add single user:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.add_members",
       data: {
           room_id: "123e4567-e89b-12d3-a456-426614174000",
           members: [42]  // Single user ID in array
       }
   }));

Add multiple users:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.add_members",
       data: {
           room_id: "room-uuid",
           members: [10, 15, 23, 45]  // Multiple user IDs
       }
   }));

**Frontend Implementation:**

.. code-block:: javascript

   class MemberManager {
       constructor(roomId, ws) {
           this.roomId = roomId;
           this.ws = ws;
           this.setupListeners();
       }

       setupListeners() {
           this.ws.onmessage = (event) => {
               const response = JSON.parse(event.data);
               
               if (response.eventType === 'roomaddmembers.dispatch') {
                   this.onMembersAdded(response.data);
               }
           };
       }

       addMembers(userIds) {
           this.ws.send(JSON.stringify({
               event_type: "room.add_members",
               data: {
                   room_id: this.roomId,
                   members: userIds
               }
           }));
       }

       onMembersAdded(data) {
           const { room, new_members, added_by } = data;
           
           // Update UI
           if (added_by === 'self') {
               // User joined themselves
               console.log(`${new_members[0]} joined the room`);
           } else {
               // Someone added users
               console.log(`${added_by} added ${new_members.join(', ')}`);
           }
           
           // Update member list
           this.updateMemberList(room.participants || room.subscribers);
       }

       updateMemberList(members) {
           // Your UI update logic
       }
   }

   // Usage
   const manager = new MemberManager(currentRoomId, ws);
   manager.addMembers([userId1, userId2]);

**Behavior:**

1. **Duplicate Prevention**: Users already in room are skipped (no error)
2. **Partial Success**: If some users don't exist, valid users are still added
3. **Signal Effects**: 
   - New members automatically added to room
   - Admins/moderators get default permissions (via signal)
4. **Notifications**: New members receive notification about being added

**Constraints:**

- Maximum members enforced (``max_participants`` or ``max_subscribers``)
- Enforced via signal - raises ``ValidationError`` if exceeded
- User IDs must exist in database (404 error if not found)
- Cannot add to OneToOneChat (raises error)

**Error Responses:**

Maximum participants exceeded:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": "Maximum number of group participants exceeded"
       }
   }

Permission denied:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not authorized to add new members to this room"
       }
   }

User not found:

.. code-block:: javascript

   {
       "error": {
           "code": 4004,
           "detail": "No User matches the given query."
       }
   }

Removing Members
----------------

room.remove_members
~~~~~~~~~~~~~~~~~~~

Remove users from a GroupChat or Channel.

**Permissions Required:**

- Must be room member
- **GroupChat**: Creator, admin, or user with ``can_remove_participants`` permission
- **Channel**: Creator, moderator, or user with ``can_remove_subscribers`` permission

**Special Rules:**

- Cannot remove room creator (unless they remove themselves)
- Admins cannot remove other admins (unless they are creator)
- Moderators cannot remove other moderators (unless they are creator)

**Request:**

.. code-block:: javascript

   {
       "event_type": "room.remove_members",
       "data": {
           "room_id": "room-uuid",  // Required
           "members": [user_id1, user_id2]  // Required, array of user IDs
       }
   }

**Response to Removed Users:**

Each removed user receives:

.. code-block:: javascript

   {
       "eventType": "roomexit.dispatch",
       "data": {
           "room": {
               // Room object
               "id": "room-uuid",
               "name": "Project Team",
               // ... other fields
           },
           "message": "You have been removed by john"
       }
   }

**Response to Remaining Members:**

All remaining room members receive:

.. code-block:: javascript

   {
       "eventType": "roomremovemembers.dispatch",
       "data": {
           "room": {
               // Updated room object without removed members
               "id": "room-uuid",
               "participants": [  // or "subscribers"
                   // Remaining members only
               ],
               // ... other fields
           },
           "removed_members": ["alice", "bob"],  // Usernames of removed users
           "removed_by": "john"  // Username of remover (or "self" if voluntary leave)
       }
   }

**Examples:**

Remove single user:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.remove_members",
       data: {
           room_id: "room-uuid",
           members: [42]
       }
   }));

Remove multiple users:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.remove_members",
       data: {
           room_id: "room-uuid",
           members: [10, 15, 23]
       }
   }));

**Frontend Implementation:**

.. code-block:: javascript

   class MemberManager {
       // ... previous code ...

       removeMembers(userIds) {
           this.ws.send(JSON.stringify({
               event_type: "room.remove_members",
               data: {
                   room_id: this.roomId,
                   members: userIds
               }
           }));
       }

       setupListeners() {
           this.ws.onmessage = (event) => {
               const response = JSON.parse(event.data);
               
               if (response.eventType === 'roomremovemembers.dispatch') {
                   this.onMembersRemoved(response.data);
               } else if (response.eventType === 'roomexit.dispatch') {
                   this.onSelfRemoved(response.data);
               }
           };
       }

       onMembersRemoved(data) {
           const { room, removed_members, removed_by } = data;
           
           if (removed_by === 'self') {
               console.log(`${removed_members[0]} left the room`);
           } else {
               console.log(`${removed_by} removed ${removed_members.join(', ')}`);
           }
           
           // Update member list
           this.updateMemberList(room.participants || room.subscribers);
       }

       onSelfRemoved(data) {
           // Current user was removed
           console.log(data.message);
           
           // Navigate away or show notification
           this.handleRemoval(data.room);
       }

       handleRemoval(room) {
           // Redirect to room list or show modal
           showNotification(`You were removed from ${room.name}`);
           navigateToRoomList();
       }
   }

**Behavior:**

1. **Creator Protection**: Cannot remove creator unless self-removal
2. **Partial Removal**: If user tries to remove creator, creator is skipped but others are removed
3. **Signal Effects**: 
   - Room deleted if no members remain (via signal)
   - Removed users lose all permissions (via signal)
4. **Notifications**: Removed users get notification about removal

**Constraints:**

- Cannot remove from OneToOneChat (2-participant rule)
- Users not in room are silently skipped
- Must have at least 1 member remaining (or room is deleted)

**Error Responses:**

Permission denied:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not authorized to remove members from this room"
       }
   }

Invalid room type:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": "Invalid room, Can only add or remove members from Groups/Channels"
       }
   }

Member List Management
----------------------

Best Practices
~~~~~~~~~~~~~~

**1. Real-Time UI Updates**

.. code-block:: javascript

   class RoomMemberList {
       constructor(roomId, ws) {
           this.roomId = roomId;
           this.ws = ws;
           this.members = [];
       }

       initialize() {
           // Load initial members
           this.ws.send(JSON.stringify({
               event_type: "room.info",
               data: { room_id: this.roomId }
           }));
       }

       onRoomInfo(room) {
           this.members = room.participants || room.subscribers;
           this.render();
       }

       onMembersAdded(data) {
           // Update local state
           const newMembers = data.new_members.map(username => ({
               username: username,
               // ... fetch full user data if needed
           }));
           
           this.members.push(...newMembers);
           this.render();
           
           // Show notification
           this.showNotification(
               `${data.new_members.join(', ')} joined`,
               'success'
           );
       }

       onMembersRemoved(data) {
           // Update local state
           this.members = this.members.filter(
               m => !data.removed_members.includes(m.username)
           );
           this.render();
           
           // Show notification
           this.showNotification(
               `${data.removed_members.join(', ')} left`,
               'info'
           );
       }

       render() {
           const memberList = document.getElementById('member-list');
           memberList.innerHTML = this.members.map(m => `
               <div class="member">
                   <img src="${m.avatar}" alt="${m.username}">
                   <span>${m.username}</span>
                   ${this.canRemove(m) ? `
                       <button onclick="removeMember('${m.id}')">Remove</button>
                   ` : ''}
               </div>
           `).join('');
       }

       canRemove(member) {
           // Check if current user can remove this member
           // Based on permissions, roles, etc.
       }
   }

**2. Batch Operations**

.. code-block:: javascript

   // Add multiple users at once
   function inviteMultipleUsers(userIds) {
       if (userIds.length === 0) return;
       
       // Single request for efficiency
       ws.send(JSON.stringify({
           event_type: "room.add_members",
           data: {
               room_id: currentRoomId,
               members: userIds
           }
       }));
   }

   // Remove multiple users
   function removeMultipleUsers(userIds) {
       if (userIds.length === 0) return;
       
       // Confirm before removing
       if (confirm(`Remove ${userIds.length} members?`)) {
           ws.send(JSON.stringify({
               event_type: "room.remove_members",
               data: {
                   room_id: currentRoomId,
                   members: userIds
               }
           }));
       }
   }

**3. Permission-Based UI**

.. code-block:: javascript

   class MemberActions {
       constructor(currentUser, room) {
           this.currentUser = currentUser;
           this.room = room;
       }

       canAddMembers() {
           if (this.room.type === 'OneToOneChat') {
               return false;
           }
           
           if (this.room.type === 'GroupChat') {
               // Check if user is creator, admin, or has permission
               return (
                   this.currentUser.id === this.room.creator.id ||
                   this.room.admins.some(a => a.id === this.currentUser.id) ||
                   this.hasPermission('can_add_new_participants')
               );
           }
           
           if (this.room.type === 'Channel') {
               return (
                   this.currentUser.id === this.room.creator.id ||
                   this.room.moderators.some(m => m.id === this.currentUser.id) ||
                   this.hasPermission('can_add_new_subscribers')
               );
           }
           
           return false;
       }

       canRemoveMember(member) {
           // Cannot remove creator
           if (member.id === this.room.creator.id && 
               member.id !== this.currentUser.id) {
               return false;
           }
           
           // Check permissions similar to canAddMembers
           // ...
       }

       hasPermission(permissionName) {
           // Check if user has specific permission
           // Query from room.permissions or user.permissions
       }
   }

   // Use in UI
   const actions = new MemberActions(currentUser, room);
   
   if (actions.canAddMembers()) {
       showAddMemberButton();
   }

Common Patterns
---------------

Pattern 1: Invite Link System
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   // Generate invite link (custom implementation)
   async function generateInviteLink(roomId) {
       const token = await createInviteToken(roomId, expiresIn='7d');
       return `https://app.com/invite/${token}`;
   }

   // Accept invite
   async function acceptInvite(inviteToken) {
       const roomId = await validateInviteToken(inviteToken);
       
       if (roomId) {
           // Join room
           ws.send(JSON.stringify({
               event_type: "room.join",  // For public channels
               data: { room_id: roomId }
           }));
       }
   }

Pattern 2: Member Approval Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   // User requests to join
   function requestToJoin(roomId) {
       fetch('/api/join-requests/', {
           method: 'POST',
           body: JSON.stringify({ room_id: roomId })
       });
   }

   // Admin approves and adds member
   function approveJoinRequest(requestId, userId, roomId) {
       // Approve in your system
       fetch(`/api/join-requests/${requestId}/approve/`, {
           method: 'POST'
       });
       
       // Add to room
       ws.send(JSON.stringify({
           event_type: "room.add_members",
           data: {
               room_id: roomId,
               members: [userId]
           }
       }));
   }

Pattern 3: Bulk Import from CSV
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   async function importMembersFromCSV(file, roomId) {
       const users = await parseCSV(file);
       const userIds = [];
       
       // Look up user IDs
       for (const email of users) {
           const user = await fetch(`/api/users/?email=${email}`);
           if (user) userIds.push(user.id);
       }
       
       // Add in batches of 50
       for (let i = 0; i < userIds.length; i += 50) {
           const batch = userIds.slice(i, i + 50);
           
           ws.send(JSON.stringify({
               event_type: "room.add_members",
               data: {
                   room_id: roomId,
                   members: batch
               }
           }));
           
           // Wait for response before next batch
           await waitForMemberAddResponse();
       }
   }

Troubleshooting
---------------

Issue: Member Added But Not Receiving Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: User not connected to WebSocket

**Solution**: Ensure user connects after being added, or system sends notification to connect

Issue: Cannot Remove Admin/Moderator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: Trying to remove with insufficient permissions

**Solution**: 
- Only creator can remove admins/moderators
- Or have creator remove admin/moderator role first, then remove as regular member

Issue: Room Disappeared After Removing Last Member
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: Signal automatically deletes empty rooms

**Solution**: This is expected behavior. If you need to prevent this, override the signal or add a "archived" state instead of deletion

Next Steps
----------

- :doc:`room-events` - Creating and managing rooms
- :doc:`message-events` - Sending and receiving messages
- :doc:`error-codes` - Complete error reference
- :doc:`../customization/permissions` - Custom member management permissions