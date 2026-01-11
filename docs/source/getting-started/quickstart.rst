Quickstart Guide
================

Get real-time chat running in your Django app in less than 10 minutes. This guide walks you through creating your first chat room and sending messages.

What You'll Build
-----------------

By the end of this guide, you'll have:

* ✅ Real-time one-to-one chat between users
* ✅ WebSocket connection with authentication
* ✅ Message persistence in database
* ✅ Working frontend example
* ✅ Understanding of core concepts

Prerequisites
-------------

Before starting, make sure you've completed:

1. :doc:`installation` - Package installed and Django configured
2. Migrations run: ``python manage.py migrate``
3. At least one user created in your database

If you haven't done these yet, follow the :doc:`installation` guide first.

Step 1: Create Test Users
--------------------------

We'll need two users to test chat functionality. Open Django shell:

.. code-block:: bash

   python manage.py shell

Create users:

.. code-block:: python

   from django.contrib.auth.models import User

   # Create Alice
   alice = User.objects.create_user(
       username='alice',
       email='alice@example.com',
       password='password123'
   )

   # Create Bob
   bob = User.objects.create_user(
       username='bob',
       email='bob@example.com',
       password='password123'
   )

   print(f"Alice ID: {alice.id}")
   print(f"Bob ID: {bob.id}")

   exit()

.. note::
   Remember Alice and Bob's IDs - you'll need them in the next steps.

Step 2: Create a Chat View
---------------------------

Create a simple view to render the chat interface. In your app's ``views.py``:

.. code-block:: python

   # myapp/views.py
   from django.contrib.auth.decorators import login_required
   from django.shortcuts import render

   @login_required
   def chat_view(request):
       return render(request, 'chat.html')

Add URL route in ``urls.py``:

.. code-block:: python

   # myproject/urls.py
   from django.contrib import admin
   from django.urls import path
   from myapp.views import chat_view

   urlpatterns = [
       path('admin/', admin.site.urls),
       path('chat/', chat_view, name='chat'),
   ]

Step 3: Create Chat Template
-----------------------------

Create ``myapp/templates/chat.html``:

.. code-block:: html

   <!DOCTYPE html>
   <html>
   <head>
       <title>Django Realtime Chat</title>
       <style>
           body {
               font-family: Arial, sans-serif;
               max-width: 800px;
               margin: 50px auto;
               padding: 20px;
           }
           #chat-log {
               height: 400px;
               overflow-y: scroll;
               border: 1px solid #ccc;
               padding: 10px;
               margin-bottom: 10px;
               background: #f9f9f9;
           }
           #message-input {
               width: 80%;
               padding: 10px;
               border: 1px solid #ccc;
           }
           #send-button {
               width: 18%;
               padding: 10px;
               background: #007bff;
               color: white;
               border: none;
               cursor: pointer;
           }
           #send-button:hover {
               background: #0056b3;
           }
           .message {
               margin: 10px 0;
               padding: 8px;
               background: white;
               border-radius: 5px;
           }
           .message.sent {
               background: #e3f2fd;
               text-align: right;
           }
           .message.received {
               background: #f5f5f5;
           }
           .username {
               font-weight: bold;
               color: #007bff;
           }
           .timestamp {
               font-size: 0.8em;
               color: #666;
           }
       </style>
   </head>
   <body>
       <h1>Django Realtime Chat</h1>
       <p>Logged in as: <strong>{{ user.username }}</strong></p>
       
       <div id="status">Connecting...</div>
       <div id="chat-log"></div>
       
       <input id="message-input" type="text" placeholder="Type a message...">
       <button id="send-button">Send</button>

       <script>
           const currentUser = "{{ user.username }}";
           const currentUserId = {{ user.id }};
           let currentRoomId = null;

           // WebSocket connection
           const chatSocket = new WebSocket(
               'ws://' + window.location.host + '/messaging/'
           );

           const chatLog = document.getElementById('chat-log');
           const messageInput = document.getElementById('message-input');
           const sendButton = document.getElementById('send-button');
           const statusDiv = document.getElementById('status');

           chatSocket.onopen = function(e) {
               console.log('✅ WebSocket connected');
               statusDiv.textContent = '✅ Connected';
               statusDiv.style.color = 'green';
               
               // Request list of rooms
               chatSocket.send(JSON.stringify({
                   event_type: 'room.list',
                   data: {}
               }));
           };

           chatSocket.onmessage = function(e) {
               const response = JSON.parse(e.data);
               console.log('Received:', response);
               
               handleIncomingMessage(response);
           };

           chatSocket.onerror = function(e) {
               console.error('❌ WebSocket error:', e);
               statusDiv.textContent = '❌ Connection error';
               statusDiv.style.color = 'red';
           };

           chatSocket.onclose = function(e) {
               console.log('WebSocket disconnected');
               statusDiv.textContent = '⚠️ Disconnected';
               statusDiv.style.color = 'orange';
               
               if (e.code === 4001) {
                   statusDiv.textContent = '❌ Authentication failed';
               }
           };

           function handleIncomingMessage(response) {
               const eventType = response.eventType;
               const data = response.data;

               switch(eventType) {
                   case 'roomlist.dispatch':
                       handleRoomList(data);
                       break;
                   case 'roomcreate.dispatch':
                       handleRoomCreated(data);
                       break;
                   case 'message.dispatch':
                       handleNewMessage(data);
                       break;
                   case 'roommessages.dispatch':
                       handleMessageHistory(data);
                       break;
                   default:
                       console.log('Unhandled event:', eventType, data);
               }
           }

           function handleRoomList(rooms) {
               console.log('Rooms:', rooms);
               
               if (rooms.length === 0) {
                   addSystemMessage('No existing chats. Creating a new chat...');
                   // Create a chat with Bob (user ID 2)
                   createRoom(2);
               } else {
                   // Use the first room
                   currentRoomId = rooms[0].id;
                   addSystemMessage(`Joined existing chat: ${currentRoomId}`);
                   loadMessages(currentRoomId);
               }
           }

           function handleRoomCreated(room) {
               currentRoomId = room.id;
               addSystemMessage(`✅ Chat created: ${room.id}`);
               console.log('Room created:', room);
           }

           function handleNewMessage(message) {
               displayMessage(message);
               
               // Mark as read if not sent by us
               if (message.sender.id !== currentUserId) {
                   markAsRead(message.id);
               }
           }

           function handleMessageHistory(response) {
               const messages = response.data.messages;
               chatLog.innerHTML = '';  // Clear loading message
               
               messages.reverse().forEach(msg => displayMessage(msg));
               chatLog.scrollTop = chatLog.scrollHeight;
           }

           function displayMessage(message) {
               const messageDiv = document.createElement('div');
               const isSent = message.sender.username === currentUser;
               
               messageDiv.className = 'message ' + (isSent ? 'sent' : 'received');
               messageDiv.innerHTML = `
                   <span class="username">${message.sender.username}</span>: 
                   ${message.content}
                   <br>
                   <span class="timestamp">${new Date(message.created_at).toLocaleTimeString()}</span>
               `;
               
               chatLog.appendChild(messageDiv);
               chatLog.scrollTop = chatLog.scrollHeight;
           }

           function addSystemMessage(text) {
               const messageDiv = document.createElement('div');
               messageDiv.style.cssText = 'text-align: center; color: #666; font-style: italic; margin: 10px 0;';
               messageDiv.textContent = text;
               chatLog.appendChild(messageDiv);
           }

           function createRoom(otherUserId) {
               chatSocket.send(JSON.stringify({
                   event_type: 'room.create',
                   data: {
                       type: 'OneToOneChat',
                       participants: [otherUserId]
                   }
               }));
           }

           function loadMessages(roomId) {
               chatSocket.send(JSON.stringify({
                   event_type: 'room.messages',
                   data: {
                       room_id: roomId,
                       paginate: {
                           page: 1,
                           size: 50
                       }
                   }
               }));
           }

           function sendMessage() {
               const message = messageInput.value.trim();
               
               if (!message) return;
               if (!currentRoomId) {
                   alert('No active chat room!');
                   return;
               }

               chatSocket.send(JSON.stringify({
                   event_type: 'message.send',
                   data: {
                       room_id: currentRoomId,
                       content: message
                   }
               }));

               messageInput.value = '';
           }

           function markAsRead(messageId) {
               chatSocket.send(JSON.stringify({
                   event_type: 'message.read',
                   data: {
                       message_id: messageId
                   }
               }));
           }

           // Send message on button click
           sendButton.onclick = sendMessage;

           // Send message on Enter key
           messageInput.onkeypress = function(e) {
               if (e.key === 'Enter') {
                   sendMessage();
               }
           };
       </script>
   </body>
   </html>

Step 4: Test the Chat
----------------------

1. **Start the server**:

   .. code-block:: bash

      python manage.py runserver

2. **Login as Alice**:

   * Go to http://localhost:8000/admin/
   * Login with username: ``alice``, password: ``password123``

3. **Open the chat**:

   * Navigate to http://localhost:8000/chat/
   * You should see "Connected" status
   * A chat room will be created automatically with Bob

4. **Send a message**:

   * Type "Hello from Alice!" and press Enter
   * You should see your message appear in the chat

5. **Test two-way communication**:

   * Open a new browser window (or incognito mode)
   * Login as Bob at http://localhost:8000/admin/
   * Go to http://localhost:8000/chat/
   * Bob should see Alice's message!
   * Send a message from Bob - Alice will see it in real-time!

.. image:: /_static/quickstart-chat-demo.png
   :alt: Chat demo screenshot
   :align: center

What Just Happened?
-------------------

Let's break down the magic:

1. **WebSocket Connection**:

   .. code-block:: javascript

      const chatSocket = new WebSocket('ws://localhost:8000/messaging/');

   This connects to the pre-built ``ChatMessagingConsumer`` that handles all WebSocket events.

2. **Room Creation**:

   .. code-block:: javascript

      {
          event_type: "room.create",
          data: {
              type: "OneToOneChat",
              participants: [2]  // Bob's ID
          }
      }

   The consumer validates permissions, creates a room in the database, and broadcasts to both users.

3. **Sending Messages**:

   .. code-block:: javascript

      {
          event_type: "message.send",
          data: {
              room_id: "uuid",
              content: "Hello!"
          }
      }

   The consumer:
   
   * Checks if you have permission to send to this room
   * Saves the message to the database
   * Broadcasts to all room members via Redis channel layer
   * Creates a notification for undelivered message tracking

4. **Real-time Delivery**:

   All connected users in the room receive:

   .. code-block:: json

      {
          "eventType": "message.dispatch",
          "data": {
              "id": "message-uuid",
              "sender": {"username": "alice"},
              "content": "Hello!",
              "created_at": "2024-01-10T12:00:00Z"
          }
      }

Understanding the Flow
----------------------

.. code-block:: text

   Alice's Browser                  Server                     Bob's Browser
   ---------------                  ------                     -------------
        |                              |                              |
        | WebSocket Connect            |                              |
        |----------------------------->|                              |
        |                              |                              |
        |         room.create          |                              |
        |----------------------------->|                              |
        |                              | Create Room in DB            |
        |                              | Add both users to group      |
        |                              |                              |
        |     roomcreate.dispatch      |     roomcreate.dispatch      |
        |<-----------------------------|----------------------------->|
        |                              |                              |
        |         message.send         |                              |
        |----------------------------->|                              |
        |                              | Save to DB                   |
        |                              | Broadcast to group           |
        |                              |                              |
        |      message.dispatch        |      message.dispatch        |
        |<-----------------------------|----------------------------->|
        |                              |                              |

Next Steps
----------

Now that you have basic chat working, explore more features:

Send a Reply
~~~~~~~~~~~~

.. code-block:: javascript

   chatSocket.send(JSON.stringify({
       event_type: "message.send",
       data: {
           room_id: currentRoomId,
           content: "This is a reply!",
           extra_fields: {
                parent_message_id: "original-message-uuid"  // Creates a thread
            }
       }
   }));

Add a Reaction
~~~~~~~~~~~~~~

.. code-block:: javascript

   chatSocket.send(JSON.stringify({
       event_type: "message.react",
       data: {
           type: "add",
           message_id: "message-uuid",
           reaction_content: "👍"
       }
   }));

Show Typing Indicator
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   messageInput.oninput = function() {
       chatSocket.send(JSON.stringify({
           event_type: "message.typing",
           data: {
               room_id: currentRoomId
           }
       }));
   };

Create a Group Chat
~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   chatSocket.send(JSON.stringify({
       event_type: "room.create",
       data: {
           type: "GroupChat",
           name: "Project Team",
           participants: [2, 3, 4]  // Multiple user IDs
       }
   }));

Common Issues
-------------

Messages not appearing in real-time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue**: Messages save to database but don't appear for other users until page refresh.

**Solution**: You're using ``InMemoryChannelLayer`` in production. Switch to Redis:

.. code-block:: python

   # settings.py
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("127.0.0.1", 6379)],
           },
       },
   }

.. code-block:: bash

   pip install channels-redis
   # Make sure Redis is running

"Chat already exists" error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue**: Trying to create duplicate OneToOneChat.

**Explanation**: This is expected behavior. A OneToOneChat between two users can only exist once.

**Solution**: Check existing rooms first with ``room.list`` before creating.

WebSocket closes immediately (code 4001)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue**: Authentication failed.

**Solution**: Make sure you're logged in via Django admin before accessing the chat page and ensure you're using ``AuthMiddlewareStack`` from ``channels.auth``

JavaScript errors in console
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue**: ``Uncaught SyntaxError`` or similar.

**Solution**: Make sure you updated the user IDs in the template to match your actual user IDs.

Learn More
----------

Congratulations! You now understand the basics of Django Realtime Chat Messaging. Continue learning:

* :doc:`concepts` - Core concepts explained in depth
* :doc:`../user-guide/room-types` - OneToOneChat, GroupChat, and Channels
* :doc:`../user-guide/messages` - Replies, forwarding, media attachments
* :doc:`../api-reference/events` - Complete WebSocket event reference
* :doc:`../user-guide/frontend-integration` - React, Vue.js examples

Ready to Build Something Amazing?
----------------------------------

You now have the foundation to build:

* 💬 Customer support chat
* 📱 Social media messaging
* 👥 Team collaboration tools
* 📢 Announcement channels
* 🎮 In-game chat systems

Check out :doc:`../customization/models` to start customizing for your use case!