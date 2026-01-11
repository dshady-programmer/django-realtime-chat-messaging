Messages Guide
==============

Complete guide to message features: sending, replies, forwarding, media attachments, editing, deleting, and more.

.. contents:: Table of Contents
   :local:
   :depth: 2

Message Basics
--------------

Every message in the system has these core properties:

.. code-block:: python

   class Message(models.Model):
       id = UUIDField(primary_key=True)
       room = ForeignKey(Room, on_delete=CASCADE)
       sender = ForeignKey(User, on_delete=CASCADE)
       content = TextField()  # HTML sanitized
       created_at = DateTimeField(auto_now_add=True)
       updated_at = DateTimeField(auto_now=True)
       
       # Features
       parent_message = ForeignKey('self', null=True)  # For replies
       is_forwarded = BooleanField(default=False)
       forwarded_from = ForeignKey('self', null=True)
       is_edited = BooleanField(default=False)
       is_deleted = BooleanField(default=False)
       
       # Engagement
       delivered_to = ManyToManyField(User)  # Who received it
       reactions = [Reaction objects]         # Emoji reactions
       read_receipts = [ReadReceipt objects]  # Who read it
       attachments = [MessageMediaAsset objects]  # Media files

Sending Messages
----------------

Simple Text Message
~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: 'Hello, world!'
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "message.dispatch",
       "data": {
           "id": "msg-uuid",
           "room": {"id": "room-uuid"},
           "sender": {
               "id": 1,
               "username": "alice",
               "email": "alice@example.com"
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
           "delivered_to": []
       }
   }

HTML in Messages
~~~~~~~~~~~~~~~~

Messages support limited HTML for rich text:

**Allowed Tags:**

* ``<b>``, ``<strong>`` - Bold text
* ``<i>``, ``<em>`` - Italic text
* ``<a href="...">`` - Links
* ``<span>`` - Styled text
* ``<p>`` - Paragraphs
* ``<ul>``, ``<ol>``, ``<li>`` - Lists
* ``<br>`` - Line breaks

**Allowed Attributes:**

* ``href``, ``title``, ``target`` on ``<a>``
* ``class``, ``id`` on all tags

**Example:**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: '<p>Check out <a href="https://example.com">this link</a>!</p><p><strong>Important:</strong> Read by EOD.</p>'
       }
   }));

.. warning::
   **XSS Protection**: HTML is automatically sanitized by `bleach <https://bleach.readthedocs.io/>`_. Any disallowed tags or attributes are stripped.

Message Threads (Replies)
--------------------------

Create threaded conversations by replying to messages.

Sending a Reply
~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: 'I agree with this!',
           parent_message_id: 'original-message-uuid'
       }
   }));

Response includes the parent message:

.. code-block:: json

   {
       "eventType": "message.dispatch",
       "data": {
           "id": "reply-uuid",
           "content": "I agree with this!",
           "parent_message": {
               "id": "original-message-uuid",
               "content": "Original message content",
               "sender": {"username": "bob"},
               "created_at": "2024-01-10T11:00:00Z"
           },
           "sender": {"username": "alice"},
           "created_at": "2024-01-10T12:00:00Z"
       }
   }

Displaying Threads
~~~~~~~~~~~~~~~~~~

Frontend should show reply context:

.. code-block:: javascript

   function displayMessage(message) {
       let html = '';
       
       // Show parent if it's a reply
       if (message.parent_message) {
           html += `
               <div class="reply-context">
                   <span class="reply-to">Replying to ${message.parent_message.sender.username}</span>
                   <p class="reply-content">${message.parent_message.content}</p>
               </div>
           `;
       }
       
       // Show actual message
       html += `
           <div class="message">
               <span class="sender">${message.sender.username}</span>
               <p>${message.content}</p>
           </div>
       `;
       
       return html;
   }

Deep Threading
~~~~~~~~~~~~~~

Replies can be nested infinitely:

.. code-block:: text

   Message A
   └── Reply to A
       └── Reply to reply
           └── Reply to reply to reply...

The ``parent_message`` field recursively contains the full parent chain.

Message Forwarding
------------------

Forward messages from one room to another.

Forwarding a Message
~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'different-room-uuid',  // Target room
           content: 'Original message content',  // Copy the content
           extra_fields: {
               forwarded_from_id: 'original-message-uuid'
           }
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "message.dispatch",
       "data": {
           "id": "forwarded-msg-uuid",
           "content": "Original message content",
           "is_forwarded": true,
           "forwarded_from": {
               "id": "original-message-uuid",
               "sender": {"username": "bob"},
               "content": "Original message content",
               "created_at": "2024-01-09T10:00:00Z"
           },
           "sender": {"username": "alice"},  // Who forwarded it
           "created_at": "2024-01-10T12:00:00Z"
       }
   }

Forwarding with Media
~~~~~~~~~~~~~~~~~~~~~

Media attachments are NOT automatically copied. You must include them:

.. code-block:: javascript

   // Get original message
   const originalMessage = {...};  // From your message store

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'different-room-uuid',
           content: originalMessage.content,
           extra_fields: {
               forwarded_from_id: originalMessage.id,
               media: originalMessage.attachments.map(att => ({
                   media_url: att.media_url,
                   media_type: att.media_type,
                   mime_type: att.mime_type,
                   file_size: att.file_size,
                   metadata: att.metadata
               }))
           }
       }
   }));

Displaying Forwarded Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   function displayMessage(message) {
       let html = '';
       
       if (message.is_forwarded && message.forwarded_from) {
           html += `
               <div class="forwarded-label">
                   Forwarded from ${message.forwarded_from.sender.username}
               </div>
           `;
       }
       
       html += `<div class="message-content">${message.content}</div>`;
       
       return html;
   }

Constraint: Cannot Reply AND Forward
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A message cannot be both a reply and a forward:

.. code-block:: python

   # Database constraint
   CheckConstraint(
       condition=~Q(is_forwarded=True, parent_message__isnull=False),
       name="forwarded_messages_cant_be_replies"
   )

If you try to send both, you'll get a database integrity error.

Media Attachments
-----------------

Messages can have multiple media files attached.

Upload Flow
~~~~~~~~~~~

The package does NOT handle file uploads. You must:

1. Upload file to your storage (S3, Cloudinary, etc.)
2. Get URL from storage service
3. Send message with URL

**Complete Example:**

.. code-block:: javascript

   async function sendImageMessage(roomId, imageFile, caption) {
       // Step 1: Upload to S3
       const formData = new FormData();
       formData.append('file', imageFile);
       
       const uploadResponse = await fetch('/api/upload/', {
           method: 'POST',
           body: formData
       });
       
       const {url, size} = await uploadResponse.json();
       
       // Step 2: Get image dimensions
       const img = await createImageBitmap(imageFile);
       
       // Step 3: Send message
       socket.send(JSON.stringify({
           event_type: 'message.send',
           data: {
               room_id: roomId,
               content: caption || 'Image',
               extra_fields: {
                   media: [{
                       media_url: url,
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

Supported Media Types
~~~~~~~~~~~~~~~~~~~~~

**Images**

.. code-block:: javascript

   {
       media_type: 'image',
       mime_type: 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp' | 'image/bmp' | 'image/heic',
       metadata: {
           width: 1920,
           height: 1080,
           orientation: 'landscape' | 'portrait'
       }
   }

**Videos**

.. code-block:: javascript

   {
       media_type: 'video',
       mime_type: 'video/mp4' | 'video/quicktime' | 'video/webm' | 'video/ogg',
       metadata: {
           duration: 15.2,  // seconds
           resolution: '1920x1080',
           fps: 30,
           orientation: 'landscape',
           video_codec: 'h264',
           audio_codec: 'aac'
       }
   }

**Audio / Voice Notes**

.. code-block:: javascript

   {
       media_type: 'audio',
       mime_type: 'audio/mpeg' | 'audio/mp4' | 'audio/ogg' | 'audio/wav',
       metadata: {
           duration: 2.8,
           waveform: [0.2, 0.5, 0.1, 0.3, 0.7],  // For visualization
           bitrate: 96000
       }
   }

**Files / Documents**

.. code-block:: javascript

   {
       media_type: 'file',
       mime_type: 'application/pdf' | 'application/msword' | 'text/plain',
       metadata: {
           page_count: 10  // Optional, for PDFs
       }
   }

Multiple Attachments
~~~~~~~~~~~~~~~~~~~~

Send multiple files in one message:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.send',
       data: {
           room_id: 'room-uuid',
           content: 'Project files',
           extra_fields: {
               media: [
                   {
                       media_url: 'https://cdn.example.com/doc.pdf',
                       media_type: 'file',
                       mime_type: 'application/pdf',
                       file_size: 204800
                   },
                   {
                       media_url: 'https://cdn.example.com/image.jpg',
                       media_type: 'image',
                       mime_type: 'image/jpeg',
                       file_size: 512000,
                       metadata: {width: 1920, height: 1080}
                   }
               ]
           }
       }
   }));

MIME Type Validation
~~~~~~~~~~~~~~~~~~~~

Only whitelisted MIME types are allowed. Attempting to send unsupported types will fail:

.. code-block:: python

   # Database constraint
   CheckConstraint(
       condition=Q(mime_type__in=ALLOWED_MIME_TYPES),
       name="valid_mime_type"
   )

See :ref:`allowed-mime-types` for the complete list.

.. _allowed-mime-types:

Allowed MIME Types
^^^^^^^^^^^^^^^^^^

.. code-block:: python

   ALLOWED_MIME_TYPES = [
       # Images
       "image/jpeg", "image/png", "image/gif", "image/webp", 
       "image/bmp", "image/heic",
       
       # Videos
       "video/mp4", "video/quicktime", "video/webm", "video/ogg",
       "video/x-msvideo", "video/x-matroska",
       
       # Audio
       "audio/mpeg", "audio/mp4", "audio/aac", "audio/ogg",
       "audio/wav", "audio/opus",
       
       # Documents
       "application/pdf",
       "application/msword",
       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
       "application/vnd.ms-excel",
       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
       "text/plain", "text/csv"
   ]

Editing Messages
----------------

Edit message content after sending. Only the sender can edit.

Editing a Message
~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.modify',
       data: {
           action: 'update',
           message_id: 'msg-uuid',
           extra_fields: {
               content: 'This is the edited content'
           }
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "messagemodification.dispatch",
       "data": {
           "status": "successful",
           "action": "update",
           "message": {
               "id": "msg-uuid",
               "content": "This is the edited content",
               "is_edited": true,
               "updated_at": "2024-01-10T12:05:00Z"
               // ... rest of message
           }
       }
   }

Limitations
~~~~~~~~~~~

* Can only edit ONE message at a time
* Can only edit ``content`` field
* Cannot edit media attachments (must delete and resend)
* ``is_edited`` flag is set automatically
* ``updated_at`` timestamp changes

Displaying Edited Messages
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   function displayMessage(message) {
       return `
           <div class="message">
               <p>${message.content}</p>
               ${message.is_edited ? '<span class="edited-label">(edited)</span>' : ''}
               <span class="timestamp">${formatTime(message.updated_at)}</span>
           </div>
       `;
   }

Deleting Messages
-----------------

Delete messages with soft delete (default) or hard delete (configurable).

Deleting Messages
~~~~~~~~~~~~~~~~~

**Single Message:**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.modify',
       data: {
           action: 'delete',
           message_id: 'msg-uuid'
       }
   }));

**Multiple Messages:**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.modify',
       data: {
           action: 'delete',
           message_id: ['msg-uuid-1', 'msg-uuid-2', 'msg-uuid-3']
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "messagemodification.dispatch",
       "data": {
           "status": "successful",
           "action": "delete",
           "message_ids": ["msg-uuid-1", "msg-uuid-2"]
       }
   }

Soft Delete vs Hard Delete
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configured in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MESSAGE_SOFT_DELETE": True  # or False
   }

**Soft Delete (``True``):**

* Sets ``is_deleted=True``
* Message stays in database
* Replies maintain ``parent_message`` reference
* Can be recovered by admin

**Hard Delete (``False``):**

* Removes from database permanently
* Replies lose ``parent_message`` (set to ``null``)
* Cannot be recovered

Frontend Handling
~~~~~~~~~~~~~~~~~

With soft delete, filter deleted messages:

.. code-block:: javascript

   const visibleMessages = messages.filter(msg => !msg.is_deleted);

Or show "Message deleted":

.. code-block:: javascript

   function displayMessage(message) {
       if (message.is_deleted) {
           return '<div class="deleted-message">This message was deleted</div>';
       }
       return `<div class="message">${message.content}</div>`;
   }

Constraint: Same Room
~~~~~~~~~~~~~~~~~~~~~

When deleting multiple messages, they must all be from the SAME room:

.. code-block:: python

   if len(message_rooms) > 1:
       raise ValidationError(
           "All messages marked for modification must come from the same room"
       )

This mimics selecting multiple messages in a chat UI for batch deletion.

Message Engagement
------------------

Delivery Status
~~~~~~~~~~~~~~~

Track message delivery with ``message.acknowledged``:

.. code-block:: javascript

   // Mark single message as delivered
   socket.send(JSON.stringify({
       event_type: 'message.acknowledged',
       data: {
           message_id: 'msg-uuid'
       }
   }));

   // Mark multiple messages
   socket.send(JSON.stringify({
       event_type: 'message.acknowledged',
       data: {
           message_id: ['msg-1', 'msg-2', 'msg-3']
       }
   }));

**What it does:**

* Adds user to ``delivered_to`` ManyToMany field
* Removes user from ``ChatNotification.recipients`` (if notifications enabled)
* No broadcast - silent operation

**When to call:**

* When message appears in user's chat UI
* When app receives push notification

Read Receipts
~~~~~~~~~~~~~

Track who read each message:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'message.read',
       data: {
           message_id: 'msg-uuid'
       }
   }));

Response broadcasts to all room members:

.. code-block:: json

   {
       "eventType": "readreceipt.dispatch",
       "data": {
           "id": "msg-uuid",
           "read_receipts": [
               {
                   "reader": {"username": "bob"},
                   "read_at": "2024-01-10T12:01:00Z"
               },
               {
                   "reader": {"username": "charlie"},
                   "read_at": "2024-01-10T12:02:00Z"
               }
           ]
           // ... rest of message
       }
   }

**Displaying:**

.. code-block:: javascript

   function formatReadReceipts(message) {
       if (message.read_receipts.length === 0) {
           return 'Unread';
       }
       
       const readers = message.read_receipts.map(r => r.reader.username);
       return `Read by ${readers.join(', ')}`;
   }

Reactions
~~~~~~~~~

Add emoji reactions to messages:

.. code-block:: javascript

   // Add reaction
   socket.send(JSON.stringify({
       event_type: 'message.react',
       data: {
           type: 'add',
           message_id: 'msg-uuid',
           reaction_content: '👍'
       }
   }));

   // Remove reaction
   socket.send(JSON.stringify({
       event_type: 'message.react',
       data: {
           type: 'remove',
           message_id: 'msg-uuid',
           reaction_content: '👍'
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "reaction.dispatch",
       "data": {
           "status": "successful",
           "type": "add",
           "message": {
               "id": "msg-uuid",
               "reactions": [
                   {
                       "user": {"username": "alice"},
                       "reaction_content": "👍",
                       "created_at": "2024-01-10T12:00:00Z"
                   }
               ]
           }
       }
   }

**Limitations:**

* Each user can have ONE reaction per message
* Adding a new reaction replaces the old one

**Displaying:**

.. code-block:: javascript

   function displayReactions(message) {
       const reactionCounts = {};
       
       message.reactions.forEach(r => {
           reactionCounts[r.reaction_content] = (reactionCounts[r.reaction_content] || 0) + 1;
       });
       
       return Object.entries(reactionCounts).map(([emoji, count]) => 
           `<span class="reaction">${emoji} ${count}</span>`
       ).join('');
   }

Typing Indicators
~~~~~~~~~~~~~~~~~

Show when users are typing:

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
       
       // Clear after 3 seconds
       typingTimeout = setTimeout(() => {
           hideTypingIndicator();
       }, 3000);
   };

Receive typing events:

.. code-block:: javascript

   socket.onmessage = (e) => {
       const response = JSON.parse(e.data);
       
       if (response.eventType === 'messagetyping.dispatch') {
           showTypingIndicator(response.data.username);
       }
   };

.. tip::
   **Debounce typing events** to avoid spamming. Send at most one event per second.

Message History & Pagination
-----------------------------

Fetch past messages with pagination:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.messages',
       data: {
           room_id: 'room-uuid',
           paginate: {
               page: 1,
               size: 50
           }
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "roommessages.dispatch",
       "data": {
           "room_id": "room-uuid",
           "messages": [...]
       },
       "has_next": true,
       "has_previous": false,
       "next_page_number": 2,
       "prev_page_number": null,
       "page": 1,
       "size": 50
   }

**Recommended page size:** 20-50 messages

**Loading more:**

.. code-block:: javascript

   function loadMoreMessages() {
       if (response.has_next) {
           socket.send(JSON.stringify({
               event_type: 'room.messages',
               data: {
                   room_id: currentRoomId,
                   paginate: {
                       page: response.next_page_number,
                       size: 50
                   }
               }
           }));
       }
   }

Best Practices
--------------

Message Sending
~~~~~~~~~~~~~~~

**Validate before sending:**

.. code-block:: javascript

   function sendMessage(content) {
       if (!content.trim()) {
           return; // Don't send empty messages
       }
       
       if (content.length > 10000) {
           alert('Message too long');
           return;
       }
       
       socket.send(JSON.stringify({
           event_type: 'message.send',
           data: {room_id: roomId, content: content}
       }));
   }

**Optimistic UI updates:**

.. code-block:: javascript

   function sendMessage(content) {
       const tempMsg = {
           id: 'temp-' + Date.now(),
           content: content,
           sender: currentUser,
           status: 'sending'
       };
       
       addMessageToUI(tempMsg);  // Show immediately
       
       socket.send(JSON.stringify({
           event_type: 'message.send',
           data: {room_id: roomId, content: content}
       }));
   }

Media Handling
~~~~~~~~~~~~~~

**Show upload progress:**

.. code-block:: javascript

   async function uploadFile(file) {
       const formData = new FormData();
       formData.append('file', file);
       
       const xhr = new XMLHttpRequest();
       
       xhr.upload.onprogress = (e) => {
           const percent = (e.loaded / e.total) * 100;
           updateProgressBar(percent);
       };
       
       return new Promise((resolve, reject) => {
           xhr.onload = () => resolve(JSON.parse(xhr.response));
           xhr.onerror = () => reject(xhr.statusText);
           xhr.open('POST', '/api/upload/');
           xhr.send(formData);
       });
   }

**Validate file size:**

.. code-block:: javascript

   const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
   
   if (file.size > MAX_FILE_SIZE) {
       alert('File too large. Max 10MB.');
       return;
   }

Message Display
~~~~~~~~~~~~~~~

**Format timestamps:**

.. code-block:: javascript

   function formatMessageTime(timestamp) {
       const date = new Date(timestamp);
       const now = new Date();
       
       if (date.toDateString() === now.toDateString()) {
           return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
       }
       
       return date.toLocaleDateString();
   }

**Group messages by date:**

.. code-block:: javascript

   function groupMessagesByDate(messages) {
       const groups = {};
       
       messages.forEach(msg => {
           const date = new Date(msg.created_at).toDateString();
           if (!groups[date]) {
               groups[date] = [];
           }
           groups[date].push(msg);
       });
       
       return groups;
   }

See Also
--------

* :doc:`room-types` - Understand room types and permissions
* :doc:`notifications` - Push notification integration
* :doc:`../api-reference/events` - Complete event reference
* :doc:`../customization/models` - Extend message model

Need Help?
----------

* :doc:`../troubleshooting` - Common issues
* :doc:`../faq` - Frequently asked questions