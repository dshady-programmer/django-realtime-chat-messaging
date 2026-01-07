Error Codes Reference
=====================

Complete reference for all error codes returned by Django Realtime Chat Messaging WebSocket API.

Error Response Format
---------------------

All errors follow this structure:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,                    // Error code (4001-4006)
           "detail": "Error message here"   // Human-readable description
       }
   }

Error Codes Overview
--------------------

.. list-table::
   :header-rows: 1
   :widths: 10 20 30 40

   * - Code
     - Name
     - Meaning
     - Common Causes
   * - 4001
     - Authentication Failed
     - User not authenticated
     - Not logged in, token expired
   * - 4002
     - Permission Denied
     - User lacks permission
     - Not room member, insufficient role
   * - 4003
     - Validation Error
     - Invalid data
     - Missing fields, constraint violation
   * - 4004
     - Resource Not Found
     - Resource doesn't exist
     - Room/message/user not found
   * - 4005
     - Integrity Error
     - Database constraint
     - Duplicate chat, foreign key error
   * - 4006
     - Internal Server Error
     - Unexpected error
     - Server bug, database issue

4001: Authentication Failed
---------------------------

**Meaning:** User is not authenticated or authentication is invalid.

**When It Happens:**

- WebSocket connection attempt with anonymous user
- Session expired
- JWT token expired or invalid
- Token not provided

**Connection Behavior:**

When authentication fails on connection, the WebSocket closes immediately with code 4001:

.. code-block:: javascript

   ws.onclose = (event) => {
       if (event.code === 4001) {
           console.log('Authentication failed');
           // Redirect to login or refresh token
       }
   };

**Examples:**

No token provided:

.. code-block:: javascript

   // Trying to connect without authentication
   const ws = new WebSocket('ws://localhost:8000/messaging/');
   // Connection closes with code 4001

Expired JWT token:

.. code-block:: javascript

   // Token expired
   const token = 'expired-jwt-token';
   const ws = new WebSocket(`ws://localhost:8000/messaging/?token=${token}`);
   // Connection closes with code 4001

**Solutions:**

1. **For Session Auth:**

   .. code-block:: javascript

      // Ensure user is logged in
      if (!isUserLoggedIn()) {
          window.location.href = '/login/';
          return;
      }
      
      // Then connect
      const ws = new WebSocket('ws://localhost:8000/messaging/');

2. **For JWT Auth:**

   .. code-block:: javascript

      function connectWithToken() {
          let token = localStorage.getItem('access_token');
          
          // Check if token is expired
          if (isTokenExpired(token)) {
              // Refresh token
              token = await refreshAccessToken();
              localStorage.setItem('access_token', token);
          }
          
          const ws = new WebSocket(
              `ws://localhost:8000/messaging/?token=${token}`
          );
          
          ws.onclose = (event) => {
              if (event.code === 4001) {
                  // Token refresh failed, re-login
                  window.location.href = '/login/';
              }
          };
      }

3. **Auto-Reconnect with Token Refresh:**

   .. code-block:: javascript

      async function connectWithAutoRefresh() {
          try {
              const token = await getValidToken();
              const ws = new WebSocket(
                  `ws://localhost:8000/messaging/?token=${token}`
              );
              
              ws.onclose = async (event) => {
                  if (event.code === 4001) {
                      // Try to refresh and reconnect
                      await refreshAccessToken();
                      setTimeout(connectWithAutoRefresh, 1000);
                  }
              };
              
              return ws;
          } catch (error) {
              // Refresh failed, redirect to login
              window.location.href = '/login/';
          }
      }

4002: Permission Denied
-----------------------

**Meaning:** User authenticated but lacks required permissions.

**When It Happens:**

- Not a room member
- Insufficient role (not admin/moderator)
- Missing object-level permission
- Trying to access another user's private data
- Room-specific restrictions (locked group, channel posting)

**Examples:**

Not a room member:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not authorized access this room"
       }
   }

Cannot send to channel:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not authorized to send message to this room"
       }
   }

Cannot add members:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not authorized to add new members to this room"
       }
   }

Cannot modify message:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not authorized to modify this message"
       }
   }

Not a room admin:

.. code-block:: javascript

   {
       "error": {
           "code": 4002,
           "detail": "User is not an admin of this room"
       }
   }

**Solutions:**

1. **Check Membership:**

   .. code-block:: javascript

      async function sendMessage(roomId, content) {
          // Check if user is room member first
          const isMember = await checkRoomMembership(roomId);
          
          if (!isMember) {
              showError('You must join this room first');
              return;
          }
          
          ws.send(JSON.stringify({
              event_type: "message.send",
              data: { room_id: roomId, content: content }
          }));
      }

2. **Request Permission:**

   .. code-block:: javascript

      function handlePermissionError(error, roomId) {
          if (error.code === 4002) {
              if (error.detail.includes('not authorized to send message')) {
                  showModal(
                      'You need posting permission',
                      'Ask a moderator to grant you posting rights'
                  );
              } else if (error.detail.includes('not authorized access this room')) {
                  showModal(
                      'Access Denied',
                      'Ask an admin to add you to this room'
                  );
              }
          }
      }

3. **UI Based on Permissions:**

   .. code-block:: javascript

      class RoomUI {
          constructor(room, currentUser) {
              this.room = room;
              this.currentUser = currentUser;
          }

          render() {
              // Show/hide based on permissions
              if (this.canSendMessages()) {
                  showMessageInput();
              } else {
                  showReadOnlyNotice();
              }

              if (this.canAddMembers()) {
                  showAddMemberButton();
              }

              if (this.canModifyRoom()) {
                  showSettingsButton();
              }
          }

          canSendMessages() {
              if (this.room.type === 'Channel') {
                  return (
                      this.currentUser.id === this.room.creator.id ||
                      this.room.moderators.some(m => m.id === this.currentUser.id) ||
                      this.hasPermission('can_send_messages')
                  );
              }

              if (this.room.type === 'GroupChat' && this.room.group_locked) {
                  return (
                      this.currentUser.id === this.room.creator.id ||
                      this.room.admins.some(a => a.id === this.currentUser.id)
                  );
              }

              return true;
          }

          hasPermission(perm) {
              // Check user's permissions for this room
          }
      }

4003: Validation Error
----------------------

**Meaning:** Request data is invalid or violates business rules.

**When It Happens:**

- Missing required fields
- Invalid data types
- Constraint violations (max participants, message length)
- Business rule violations (forwarded message can't be reply)
- Invalid choice values

**Examples:**

Missing required field:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": {
               "room_id": ["This field is required."]
           }
       }
   }

Maximum participants exceeded:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": "Maximum number of group participants exceeded"
       }
   }

Invalid message:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": {
               "content": ["This field may not be blank."]
           }
       }
   }

Invalid room type:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": "Invalid type"
       }
   }

Constraint violation:

.. code-block:: javascript

   {
       "error": {
           "code": 4003,
           "detail": "A one to one chat can only have 2 participants"
       }
   }

**Solutions:**

1. **Validate Before Sending:**

   .. code-block:: javascript

      function sendMessage(roomId, content) {
          // Client-side validation
          if (!content || content.trim().length === 0) {
              showError('Message cannot be empty');
              return;
          }

          if (content.length > 5000) {
              showError('Message too long (max 5000 characters)');
              return;
          }

          ws.send(JSON.stringify({
              event_type: "message.send",
              data: { room_id: roomId, content: content }
          }));
      }

2. **Handle Field Errors:**

   .. code-block:: javascript

      function handleValidationError(error) {
          if (typeof error.detail === 'object') {
              // Field-specific errors
              Object.keys(error.detail).forEach(field => {
                  const errors = error.detail[field];
                  showFieldError(field, errors.join(', '));
              });
          } else {
              // General validation error
              showError(error.detail);
          }
      }

3. **Respect Constraints:**

   .. code-block:: javascript

      async function addMembers(roomId, userIds) {
          const room = await getRoomInfo(roomId);
          
          // Check max participants
          const currentCount = room.participants.length;
          const newCount = currentCount + userIds.length;
          
          if (newCount > room.max_participants) {
              showError(
                  `Cannot add ${userIds.length} members. ` +
                  `Room has ${currentCount}/${room.max_participants} members.`
              );
              return;
          }

          ws.send(JSON.stringify({
              event_type: "room.add_members",
              data: { room_id: roomId, members: userIds }
          }));
      }

4004: Resource Not Found
------------------------

**Meaning:** Requested resource doesn't exist in database.

**When It Happens:**

- Room ID doesn't exist
- Message ID doesn't exist
- User ID doesn't exist
- Deleted resource

**Examples:**

Room not found:

.. code-block:: javascript

   {
       "error": {
           "code": 4004,
           "detail": "No Room matches the given query."
       }
   }

Message not found:

.. code-block:: javascript

   {
       "error": {
           "code": 4004,
           "detail": "No Message matches the given query."
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

**Solutions:**

1. **Validate IDs:**

   .. code-block:: javascript

      async function loadRoom(roomId) {
          try {
              ws.send(JSON.stringify({
                  event_type: "room.info",
                  data: { room_id: roomId }
              }));
          } catch (error) {
              if (error.code === 4004) {
                  showError('Room not found');
                  navigateToRoomList();
              }
          }
      }

2. **Handle Deletion:**

   .. code-block:: javascript

      // Listen for room deletion
      ws.onmessage = (event) => {
          const response = JSON.parse(event.data);

          if (response.error && response.error.code === 4004) {
              if (response.error.detail.includes('Room')) {
                  showNotification('This room was deleted');
                  navigateToRoomList();
              }
          }
      };

3. **Cache Validation:**

   .. code-block:: javascript

      class RoomCache {
          constructor() {
              this.rooms = new Map();
          }

          async getRoom(roomId) {
              // Check cache
              if (this.rooms.has(roomId)) {
                  return this.rooms.get(roomId);
              }

              // Fetch from server
              try {
                  const room = await fetchRoomInfo(roomId);
                  this.rooms.set(roomId, room);
                  return room;
              } catch (error) {
                  if (error.code === 4004) {
                      // Remove from cache if deleted
                      this.rooms.delete(roomId);
                  }
                  throw error;
              }
          }
      }

4005: Integrity Error
---------------------

**Meaning:** Database integrity constraint violated.

**When It Happens:**

- Duplicate OneToOneChat between same users
- Unique constraint violations
- Foreign key violations
- Constraint check failures

**Examples:**

Duplicate chat:

.. code-block:: javascript

   {
       "error": {
           "code": 4005,
           "detail": "Chat already exists"
       }
   }

**Solutions:**

1. **Check Before Creating:**

   .. code-block:: javascript

      async function startChatWithUser(userId) {
          // Check if chat already exists
          const existingChat = await findExistingChat(userId);

          if (existingChat) {
              navigateToRoom(existingChat.id);
              return;
          }

          // Create new chat
          ws.send(JSON.stringify({
              event_type: "room.create",
              data: {
                   type: "OneToOneChat",
                  participants: [userId]
              }
          }));
      }

      async function findExistingChat(userId) {
          const rooms = await getRoomList();
          return rooms.find(room => 
              room.type === 'OneToOneChat' &&
              room.peer.id === userId
          );
      }

2. **Handle Duplicates Gracefully:**

   .. code-block:: javascript

      ws.onmessage = (event) => {
          const response = JSON.parse(event.data);

          if (response.error && response.error.code === 4005) {
              if (response.error.detail === 'Chat already exists') {
                  // Fetch existing chat instead
                  fetchExistingChatAndNavigate();
              }
          }
      };

4006: Internal Server Error
---------------------------

**Meaning:** Unexpected error occurred on server.

**When It Happens:**

- Server bug
- Database connection error
- Unhandled exception
- Configuration error

**Example:**

.. code-block:: javascript

   {
       "error": {
           "code": 4006,
           "detail": "Internal server error."
       }
   }

**Solutions:**

1. **Retry Logic:**

   .. code-block:: javascript

      async function sendWithRetry(eventType, data, maxRetries = 3) {
          for (let i = 0; i < maxRetries; i++) {
              try {
                  ws.send(JSON.stringify({
                      event_type: eventType,
                      data: data
                  }));

                  // Wait for response
                  const response = await waitForResponse();

                  if (response.error && response.error.code === 4006) {
                      if (i < maxRetries - 1) {
                          // Wait before retry
                          await sleep(1000 * (i + 1));
                          continue;
                      }
                  }

                  return response;
              } catch (error) {
                  if (i === maxRetries - 1) throw error;
              }
          }
      }

2. **Error Reporting:**

   .. code-block:: javascript

      function handleInternalError(error) {
          // Log to external service
          Sentry.captureException(new Error('WebSocket Internal Error'), {
              extra: {
                  error: error,
                  timestamp: new Date().toISOString()
              }
          });

          // Show user-friendly message
          showError(
              'Something went wrong. Please try again later.'
          );
      }

Error Handling Best Practices
------------------------------

Complete Error Handler
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   class WebSocketErrorHandler {
       constructor(ws) {
           this.ws = ws;
           this.setupListeners();
       }

       setupListeners() {
           this.ws.onmessage = (event) => {
               const response = JSON.parse(event.data);

               if (response.error) {
                   this.handleError(response.error);
               }
           };

           this.ws.onclose = (event) => {
               this.handleClose(event);
           };
       }

       handleError(error) {
           switch (error.code) {
               case 4001:
                   this.handleAuthError(error);
                   break;
               case 4002:
                   this.handlePermissionError(error);
                   break;
               case 4003:
                   this.handleValidationError(error);
                   break;
               case 4004:
                   this.handleNotFoundError(error);
                   break;
               case 4005:
                   this.handleIntegrityError(error);
                   break;
               case 4006:
                   this.handleInternalError(error);
                   break;
               default:
                   this.handleUnknownError(error);
           }
       }

       handleAuthError(error) {
           console.error('Authentication failed:', error.detail);
           window.location.href = '/login/';
       }

       handlePermissionError(error) {
           console.warn('Permission denied:', error.detail);
           showNotification(error.detail, 'warning');
       }

       handleValidationError(error) {
           console.warn('Validation error:', error.detail);

           if (typeof error.detail === 'object') {
               // Field errors
               this.displayFieldErrors(error.detail);
           } else {
               showNotification(error.detail, 'error');
           }
       }

       handleNotFoundError(error) {
           console.warn('Resource not found:', error.detail);
           showNotification('Resource not found', 'error');
       }

       handleIntegrityError(error) {
           console.warn('Integrity error:', error.detail);
           showNotification(error.detail, 'error');
       }

       handleInternalError(error) {
           console.error('Internal server error:', error.detail);
           Sentry.captureException(error);
           showNotification(
               'Something went wrong. Please try again.',
               'error'
           );
       }

       handleUnknownError(error) {
           console.error('Unknown error:', error);
           Sentry.captureException(error);
       }

       handleClose(event) {
           if (event.code === 4001) {
               this.handleAuthError({ detail: 'Authentication failed' });
           } else {
               console.log('WebSocket closed:', event.code, event.reason);
           }
       }

       displayFieldErrors(fieldErrors) {
           Object.keys(fieldErrors).forEach(field => {
               const errors = fieldErrors[field];
               showFieldError(field, errors.join(', '));
           });
       }
   }

   // Usage
   const ws = new WebSocket('ws://localhost:8000/messaging/');
   const errorHandler = new WebSocketErrorHandler(ws);

User-Friendly Error Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   function getUserFriendlyMessage(errorCode, detail) {
       const messages = {
           4001: 'Please log in to continue',
           4002: 'You don\'t have permission for this action',
           4003: detail || 'Invalid input. Please check your data',
           4004: 'This item no longer exists',
           4005: detail || 'This action conflicts with existing data',
           4006: 'Something went wrong. Please try again later'
       };

       return messages[errorCode] || 'An error occurred';
   }

Next Steps
----------

- :doc:`message-events` - Message event reference
- :doc:`room-events` - Room event reference
- :doc:`../troubleshooting` - Troubleshooting guide