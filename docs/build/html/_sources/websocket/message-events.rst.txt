Message Events
==============

Complete reference for all message-related WebSocket events. These events handle sending, modifying, reacting to, and retrieving messages.

Event Structure
---------------

All events follow this structure:

**Sending to Server:**

.. code-block:: javascript

   {
       "event_type": "message.send",
       "data": {
           // Event-specific data
       }
   }

**Receiving from Server:**

.. code-block:: javascript

   {
       "eventType": "message.dispatch",
       "data": {
           // Event-specific data
       }
   }

Message Sending
---------------

message.send
~~~~~~~~~~~~

Send a new message to a room.

**Request:**

.. code-block:: javascript

   {
       "event_type": "message.send",
       "data": {
           "room_id": "uuid-string",  // Required
           "content": "Hello, world!",  // Required (unless sending media)
           "extra_fields": {  // Optional
               // Reply to another message
               "parent_message": "message-uuid",
               
               // Forward a message
               "is_forwarded": true,
               "forwarded_from_id": "original-message-uuid",
               
               // Attach media
               "media": [
                   {
                       "media_url": "https://example.com/file.pdf",
                       "media_type": "file",  // "image", "video", "audio", "file"
                       "file_size": 1024000,  // bytes
                       "mime_type": "application/pdf",
                       "caption": "Optional caption",  // Optional
                       "metadata": {}  // Optional
                   }
               ]
           }
       }
   }

**Response Broadcast:**

All room participants receive:

.. code-block:: javascript

   {
       "eventType": "message.dispatch",
       "data": {
           "id": "message-uuid",
           "room": {
               "id": "room-uuid"
           },
           "sender": {
               "id": 1,
               "username": "alice",
               "email": "alice@example.com"
           },
           "content": "Hello, world!",
           "created_at": "2025-01-03T10:30:00Z",
           "updated_at": "2025-01-03T10:30:00Z",
           "is_forwarded": false,
           "is_edited": false,
           "is_deleted": false,
           "parent_message": null,
           "forwarded_from": null,
           "read_receipts": [],
           "reactions": [],
           "attachments": [],
           "delivered_to": ["alice"]
       }
   }

**Examples:**

Simple message:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.send",
       data: {
           room_id: "123e4567-e89b-12d3-a456-426614174000",
           content: "Hello everyone!"
       }
   }));

Reply to message:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.send",
       data: {
           room_id: "123e4567-e89b-12d3-a456-426614174000",
           content: "Great idea!",
           extra_fields: {
               parent_message: "original-message-uuid"
           }
       }
   }));

Forward message:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.send",
       data: {
           room_id: "target-room-uuid",
           content: "Check this out",
           extra_fields: {
               is_forwarded: true,
               forwarded_from_id: "original-message-uuid"
           }
       }
   }));

Send with media:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.send",
       data: {
           room_id: "room-uuid",
           content: "Media Files",  // Will be overridden if media present
           extra_fields: {
               media: [
                   {
                       media_url: "https://cdn.example.com/image.jpg",
                       media_type: "image",
                       file_size: 524288,
                       mime_type: "image/jpeg",
                       metadata: {
                           width: 1920,
                           height: 1080,
                           orientation: "landscape"
                       }
                   }
               ]
           }
       }
   }));

**Constraints:**

- Forwarded messages cannot be replies (enforced by database constraint)
- ``room_id`` must exist and user must have permission to post
- HTML content is sanitized (allowed tags: b, i, strong, em, a, span, p, ul, ol, li, br)
- Media URLs are not uploaded by the package - handle upload separately

Message Modification
--------------------

message.modify
~~~~~~~~~~~~~~

Update or delete messages.

**Request (Update):**

.. code-block:: javascript

   {
       "event_type": "message.modify",
       "data": {
           "action": "update",
           "message_id": "message-uuid",  // Single ID for update
           "extra_fields": {
               "content": "Updated message content"
           }
       }
   }

**Request (Delete):**

.. code-block:: javascript

   {
       "event_type": "message.modify",
       "data": {
           "action": "delete",
           "message_id": ["uuid1", "uuid2", "uuid3"]  // Can be array or single ID
       }
   }

**Response Broadcast (Update):**

.. code-block:: javascript

   {
       "eventType": "messagemodification.dispatch",
       "data": {
           "status": "successful",
           "action": "update",
           "message": {
               // Full updated message object
               "id": "message-uuid",
               "content": "Updated message content",
               "is_edited": true,
               // ... other fields
           }
       }
   }

**Response Broadcast (Delete):**

.. code-block:: javascript

   {
       "eventType": "messagemodification.dispatch",
       "data": {
           "status": "successful",
           "action": "delete",
           "message_ids": ["uuid1", "uuid2", "uuid3"]
       }
   }

**Examples:**

Edit message:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.modify",
       data: {
           action: "update",
           message_id: "123e4567-e89b-12d3-a456-426614174000",
           extra_fields: {
               content: "Corrected typo: Hello everyone!"
           }
       }
   }));

Delete single message:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.modify",
       data: {
           action: "delete",
           message_id: "message-uuid"
       }
   }));

Delete multiple messages:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.modify",
       data: {
           action: "delete",
           message_id: [
               "message-uuid-1",
               "message-uuid-2",
               "message-uuid-3"
           ]
       }
   }));

**Constraints:**

- Only message sender can modify their messages
- All messages for bulk delete must be from the same room
- Update action accepts only one message at a time
- Deletion behavior depends on ``MESSAGE_SOFT_DELETE`` setting

Message Reactions
-----------------

message.react
~~~~~~~~~~~~~

Add or remove reactions from messages.

**Request (Add Reaction):**

.. code-block:: javascript

   {
       "event_type": "message.react",
       "data": {
           "type": "add",
           "message_id": "message-uuid",
           "reaction_content": "👍"  // Any emoji or text up to 128 chars
       }
   }

**Request (Remove Reaction):**

.. code-block:: javascript

   {
       "event_type": "message.react",
       "data": {
           "type": "remove",
           "message_id": "message-uuid"
       }
   }

**Response Broadcast:**

.. code-block:: javascript

   {
       "eventType": "reaction.dispatch",
       "data": {
           "status": "successful",
           "type": "add",  // or "remove"
           "message": {
               // Full message object with updated reactions
               "id": "message-uuid",
               "content": "Original message",
               "reactions": [
                   {
                       "id": "reaction-uuid",
                       "user": {
                           "id": 1,
                           "username": "alice"
                       },
                       "reaction_content": "👍",
                       "created_at": "2025-01-03T10:30:00Z"
                   }
               ],
               // ... other fields
           }
       }
   }

**Examples:**

Add reaction:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.react",
       data: {
           type: "add",
           message_id: "message-uuid",
           reaction_content: "❤️"
       }
   }));

Remove reaction:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.react",
       data: {
           type: "remove",
           message_id: "message-uuid"
       }
   }));

**Constraints:**

- One reaction per user per message (enforced by database constraint)
- Adding a different reaction updates the existing one
- Removing non-existent reaction returns failed status
- Maximum 128 characters for reaction content

Typing Indicators
-----------------

message.typing
~~~~~~~~~~~~~~

Notify room participants that user is typing.

**Request:**

.. code-block:: javascript

   {
       "event_type": "message.typing",
       "data": {
           "room_id": "room-uuid"
       }
   }

**Response Broadcast:**

All room participants (except sender) receive:

.. code-block:: javascript

   {
       "eventType": "messagetyping.dispatch",
       "data": {
           "username": "alice"
       }
   }

**Example Implementation:**

.. code-block:: javascript

   let typingTimer;
   const TYPING_TIMER_LENGTH = 3000; // 3 seconds

   messageInput.addEventListener('input', () => {
       // Send typing indicator
       ws.send(JSON.stringify({
           event_type: "message.typing",
           data: { room_id: currentRoomId }
       }));

       // Reset timer
       clearTimeout(typingTimer);
       typingTimer = setTimeout(() => {
           // User stopped typing (handle in UI)
       }, TYPING_TIMER_LENGTH);
   });

   // Listen for typing indicators
   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.eventType === 'messagetyping.dispatch') {
           showTypingIndicator(`${response.data.username} is typing...`);
           
           // Hide after 3 seconds
           setTimeout(() => {
               hideTypingIndicator();
           }, 3000);
       }
   };

**Implementation Notes:**

- Backend does not track typing state or timeouts
- Frontend must implement debouncing and timeout logic
- Sender does not receive their own typing events
- No persistence - purely real-time events

Read Receipts
-------------

message.read
~~~~~~~~~~~~

Mark message(s) as read.

**Request (Single Message):**

.. code-block:: javascript

   {
       "event_type": "message.read",
       "data": {
           "message_id": "message-uuid"
       }
   }

**Request (Multiple Messages):**

.. code-block:: javascript

   {
       "event_type": "message.read",
       "data": {
           "message_id": ["uuid1", "uuid2", "uuid3"]
       }
   }

**Response Broadcast:**

All room participants receive:

.. code-block:: javascript

   {
       "eventType": "readreceipt.dispatch",
       "data": {
           // For single message
           "id": "message-uuid",
           "content": "Message content",
           "read_receipts": [
               {
                   "reader": {
                       "id": 2,
                       "username": "bob"
                   },
                   "read_at": "2025-01-03T10:35:00Z"
               }
           ],
           // ... other message fields
       }
   }

For multiple messages, response structure varies:

.. code-block:: javascript

   {
       "eventType": "readreceipt.dispatch",
       "data": {
           "room-uuid-1": [
               {/* message 1 */},
               {/* message 2 */}
           ],
           "room-uuid-2": [
               {/* message 3 */}
           ]
       }
   }

**Examples:**

Mark single message as read:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "message.read",
       data: {
           message_id: "message-uuid"
       }
   }));

Mark all visible messages as read:

.. code-block:: javascript

   const visibleMessageIds = getVisibleMessageIds(); // Your logic
   
   ws.send(JSON.stringify({
       event_type: "message.read",
       data: {
           message_id: visibleMessageIds
       }
   }));

**Implementation Pattern:**

.. code-block:: javascript

   // Mark messages as read when they come into view
   const observer = new IntersectionObserver((entries) => {
       const visibleMessages = entries
           .filter(entry => entry.isIntersecting)
           .map(entry => entry.target.dataset.messageId);

       if (visibleMessages.length > 0) {
           ws.send(JSON.stringify({
               event_type: "message.read",
               data: { message_id: visibleMessages }
           }));
       }
   }, { threshold: 0.5 });

   // Observe each message element
   document.querySelectorAll('.message').forEach(el => {
       observer.observe(el);
   });

**Constraints:**

- Users cannot mark their own messages as read
- Read receipts are unique per user per message (database constraint)
- Updates ``ChatNotification`` to remove user from recipients

Message Delivery
----------------

message.acknowledged
~~~~~~~~~~~~~~~~~~~~

Confirm message delivery to user's device.

**Request:**

.. code-block:: javascript

   {
       "event_type": "message.acknowledged",
       "data": {
           "message_id": "message-uuid"  // Can be array
       }
   }

**Response:**

.. code-block:: javascript

   {
       "status": "successful"
   }

No broadcast - delivery confirmation is tracked internally.

**Example:**

.. code-block:: javascript

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.eventType === 'message.dispatch') {
           const message = response.data;
           
           // Display message in UI
           displayMessage(message);
           
           // Acknowledge delivery
           ws.send(JSON.stringify({
               event_type: "message.acknowledged",
               data: {
                   message_id: message.id
               }
           }));
       }
   };

**Difference from Read Receipts:**

- **acknowledged**: Message delivered to device
- **read**: User viewed the message

Retrieving Messages
-------------------

room.messages
~~~~~~~~~~~~~

Fetch messages for a room with optional pagination.

**Request (All Messages):**

.. code-block:: javascript

   {
       "event_type": "room.messages",
       "data": {
           "room_id": "room-uuid"
       }
   }

**Request (Paginated):**

.. code-block:: javascript

   {
       "event_type": "room.messages",
       "data": {
           "room_id": "room-uuid",
           "paginate": {
               "page": 1,
               "size": 50
           }
       }
   }

**Response:**

.. code-block:: javascript

   {
       "eventType": "roommessages.dispatch",
       "data": {
           // Pagination metadata (if paginated)
           "has_next": true,
           "has_previous": false,
           "next_page_number": 2,
           "prev_page_number": null,
           "page": 1,
           "size": 50,
           
           // Message data
           "data": {
               "room_id": "room-uuid",
               "messages": [
                   {/* message 1 */},
                   {/* message 2 */},
                   // ... up to 'size' messages
               ]
           }
       }
   }

**Examples:**

Load initial messages:

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.messages",
       data: {
           room_id: currentRoomId,
           paginate: {
               page: 1,
               size: 50
           }
       }
   }));

Load more (infinite scroll):

.. code-block:: javascript

   function loadMoreMessages(currentPage) {
       ws.send(JSON.stringify({
           event_type: "room.messages",
           data: {
               room_id: currentRoomId,
               paginate: {
                   page: currentPage + 1,
                   size: 50
               }
           }
       }));
   }

**Implementation Pattern:**

.. code-block:: javascript

   let currentPage = 1;
   let hasMore = true;

   function loadMessages() {
       if (!hasMore) return;

       ws.send(JSON.stringify({
           event_type: "room.messages",
           data: {
               room_id: currentRoomId,
               paginate: { page: currentPage, size: 50 }
           }
       }));
   }

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       
       if (response.eventType === 'roommessages.dispatch') {
           const { messages } = response.data.data;
           hasMore = response.data.has_next;
           currentPage = response.data.page;
           
           displayMessages(messages);
           
           if (hasMore) {
               showLoadMoreButton();
           }
       }
   };

**Constraints:**

- Both ``page`` and ``size`` required if using pagination
- Messages ordered by ``created_at`` descending (newest first)
- No default pagination - fetches all messages if not specified
- Recommended to always use pagination for performance

Complete Example
----------------

Here's a complete message handling implementation:

.. code-block:: javascript

   class ChatManager {
       constructor(roomId, ws) {
           this.roomId = roomId;
           this.ws = ws;
           this.setupListeners();
       }

       setupListeners() {
           this.ws.onmessage = (event) => {
               const response = JSON.parse(event.data);
               this.handleEvent(response);
           };
       }

       handleEvent(response) {
           switch (response.eventType) {
               case 'message.dispatch':
                   this.onNewMessage(response.data);
                   break;
               case 'messagemodification.dispatch':
                   this.onMessageModified(response.data);
                   break;
               case 'reaction.dispatch':
                   this.onReaction(response.data);
                   break;
               case 'messagetyping.dispatch':
                   this.onTyping(response.data);
                   break;
               case 'readreceipt.dispatch':
                   this.onReadReceipt(response.data);
                   break;
           }
       }

       // Send message
       sendMessage(content) {
           this.ws.send(JSON.stringify({
               event_type: "message.send",
               data: {
                   room_id: this.roomId,
                   content: content
               }
           }));
       }

       // Reply to message
       replyToMessage(content, parentMessageId) {
           this.ws.send(JSON.stringify({
               event_type: "message.send",
               data: {
                   room_id: this.roomId,
                   content: content,
                   extra_fields: {
                       parent_message: parentMessageId
                   }
               }
           }));
       }

       // Edit message
       editMessage(messageId, newContent) {
           this.ws.send(JSON.stringify({
               event_type: "message.modify",
               data: {
                   action: "update",
                   message_id: messageId,
                   extra_fields: { content: newContent }
               }
           }));
       }

       // Delete message(s)
       deleteMessages(messageIds) {
           this.ws.send(JSON.stringify({
               event_type: "message.modify",
               data: {
                   action: "delete",
                   message_id: Array.isArray(messageIds) ? messageIds : [messageIds]
               }
           }));
       }

       // React to message
       reactToMessage(messageId, emoji) {
           this.ws.send(JSON.stringify({
               event_type: "message.react",
               data: {
                   type: "add",
                   message_id: messageId,
                   reaction_content: emoji
               }
           }));
       }

       // Mark as read
       markAsRead(messageIds) {
           this.ws.send(JSON.stringify({
               event_type: "message.read",
               data: {
                   message_id: Array.isArray(messageIds) ? messageIds : [messageIds]
               }
           }));
       }

       // Load messages
       loadMessages(page = 1, size = 50) {
           this.ws.send(JSON.stringify({
               event_type: "room.messages",
               data: {
                   room_id: this.roomId,
                   paginate: { page, size }
               }
           }));
       }

       // Event handlers
       onNewMessage(message) {
           console.log('New message:', message);
           // Acknowledge delivery
           this.ws.send(JSON.stringify({
               event_type: "message.acknowledged",
               data: { message_id: message.id }
           }));
       }

       onMessageModified(data) {
           console.log('Message modified:', data);
       }

       onReaction(data) {
           console.log('Reaction:', data);
       }

       onTyping(data) {
           console.log(`${data.username} is typing...`);
       }

       onReadReceipt(data) {
           console.log('Read receipt:', data);
       }
   }

   // Usage
   const chat = new ChatManager(roomId, ws);
   chat.sendMessage("Hello!");

Next Steps
----------

- :doc:`room-events` - Managing rooms and membership
- :doc:`member-management` - Adding and removing users
- :doc:`error-codes` - Handling errors
- :doc:`../frontend/event-payloads` - Complete payload reference