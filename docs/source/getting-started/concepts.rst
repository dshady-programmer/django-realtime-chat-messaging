Core Concepts
=============

Understanding how Django Realtime Chat Messaging works will help you build better chat applications and customize the package effectively.

.. contents:: Table of Contents
   :local:
   :depth: 2

Architecture Overview
---------------------

The package follows a layered architecture:

.. code-block:: text

   ┌──────────────────────────────────────┐
   │         Frontend (Browser)           │
   │  WebSocket Connection + Event Sender │
   └────────────────┬─────────────────────┘
                    │ ws://
                    ▼
   ┌──────────────────────────────────────┐
   │      ChatMessagingConsumer           │
   │  - Connection management             │
   │  - Event routing                     │
   │  - Permission checks                 │
   └────────────────┬─────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────┐
   │       Event Handlers                 │
   │  - Business logic                    │
   │  - Database operations               │
   │  - Serialization                     │
   └────────────────┬─────────────────────┘
                    │
                    ▼
   ┌──────────────────────────────────────┐
   │      Models (Database)               │
   │  - Room (polymorphic base)           │
   │  - OneToOneChat, GroupChat, Channel  │
   │  - Message, Reaction, ReadReceipt    │
   └──────────────────────────────────────┘

Components Explained
~~~~~~~~~~~~~~~~~~~~

**Consumer** (``ChatMessagingConsumer``)
   Handles WebSocket connections, authenticates users, routes events to handlers, and manages channel layers.

**Event Handlers** (``EventHandler`` class)
   Contains business logic for each event (message creation, room management, etc.). Separated into mixins for organization.

**Permission Decorators**
   Wrap handler methods to check permissions before execution. Use django-guardian for object-level permissions.

**Models**
   Store all persistent data. Fully swappable, allowing complete customization.

**Serializers**
   Convert between models and JSON. Also swappable for custom fields.

**Channel Layer** (Redis)
   Routes messages between WebSocket connections. Required for multi-server deployments.

The Three Room Types
--------------------

The package provides three polymorphic room types, each with different behavior and use cases.

OneToOneChat
~~~~~~~~~~~~

Private conversations between exactly two users.

**Characteristics:**

* Always 2 participants (enforced by database constraint)
* No admins or roles
* Both users have equal permissions
* Cannot be left (room deleted if user removed)
* Duplicate prevention (can't create two chats between same users)

**Use Cases:**

* Direct messaging (like WhatsApp, Facebook Messenger)
* Customer support (agent ↔ customer)
* Private discussions

**Creation:**

.. code-block:: javascript

   {
       type: 'OneToOneChat',
       participants: [other_user_id]
   }

**Database Schema:**

.. code-block:: python

   class OneToOneChat(Room):
       participants = ManyToManyField(User)  # Always 2

GroupChat
~~~~~~~~~

Multi-user conversations with admin hierarchy.

**Characteristics:**

* 3+ participants (configurable max)
* Creator + Admins + Members
* Admins can manage members and permissions
* Can be "locked" (only admins can send messages)
* Requires invitation to join (no public join)

**Use Cases:**

* Team collaboration (like Slack channels)
* Friend groups (like WhatsApp groups)
* Project discussions

**Creation:**

.. code-block:: javascript

   {
       type: 'GroupChat',
       name: 'Project Team',
       participants: [user2, user3, user4],
       extra_fields: {
           max_participants: 50,
           join_approval_required: true,
           group_locked: false
       }
   }

**Roles:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Role
     - Permissions
   * - **Creator**
     - All permissions, cannot be removed (only leave voluntarily)
   * - **Admin**
     - Add/remove members, promote/demote admins, send messages
   * - **Member**
     - Send messages (unless group_locked), read messages

**Database Schema:**

.. code-block:: python

   class GroupChat(Room):
       name = CharField(max_length=64)
       description = TextField()
       creator = ForeignKey(User)
       participants = ManyToManyField(User)
       admins = ManyToManyField(User)
       max_participants = PositiveBigIntegerField(default=100)
       group_locked = BooleanField(default=False)
       join_approval_required = BooleanField(default=False)

Channel
~~~~~~~

Broadcast channels where only moderators can post (like Telegram channels).

**Characteristics:**

* One-to-many communication
* Creator + Moderators + Subscribers
* Only moderators can send messages (by default)
* Can be public (anyone can join) or private
* Large subscriber limit (default: 300)

**Use Cases:**

* Company announcements
* News feeds
* Content broadcasting
* Community updates

**Creation:**

.. code-block:: javascript

   {
       type: 'Channel',
       name: 'Announcements',
       subscribers: [user2, user3],
       extra_fields: {
           is_public: true,
           max_subscribers: 1000
       }
   }

**Roles:**

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Role
     - Permissions
   * - **Creator**
     - All permissions, cannot be removed
   * - **Moderator**
     - Send messages, add/remove subscribers, manage permissions
   * - **Subscriber**
     - Read messages, react (cannot send messages without permission)

**Database Schema:**

.. code-block:: python

   class Channel(Room):
       name = CharField(max_length=64)
       description = TextField()
       creator = ForeignKey(User)
       subscribers = ManyToManyField(User)
       moderators = ManyToManyField(User)
       is_public = BooleanField(default=False)
       max_subscribers = PositiveBigIntegerField(default=300)

Polymorphism Explained
~~~~~~~~~~~~~~~~~~~~~~

All three room types inherit from the ``Room`` base model using django-polymorphic:

.. code-block:: python

   # Base model
   class Room(PolymorphicModel):
       id = UUIDField(primary_key=True)
       last_message = ForeignKey(Message, null=True)
       created_at = DateTimeField(auto_now_add=True)
       preferences = JSONField(default=dict)

   # Specific types extend the base
   class OneToOneChat(Room):
       participants = ManyToManyField(User)

   class GroupChat(Room):
       name = CharField()
       participants = ManyToManyField(User)
       admins = ManyToManyField(User)
       # ... GroupChat-specific fields

   class Channel(Room):
       name = CharField()
       subscribers = ManyToManyField(User)
       moderators = ManyToManyField(User)
       # ... Channel-specific fields

**Benefits:**

* Query all rooms: ``Room.objects.filter(participants=user)``
* Automatic type resolution: Returns correct subclass (OneToOneChat, GroupChat, or Channel)
* Shared fields: ``last_message``, ``created_at``, ``preferences`` on all types
* Type-specific fields: Each subclass adds its own fields

Message Features
----------------

Messages support rich features beyond simple text.

Message Types
~~~~~~~~~~~~~

**Regular Message**

.. code-block:: python

   {
       "content": "Hello, world!",
       "parent_message": null,
       "is_forwarded": false
   }

**Reply Message** (Threading)

.. code-block:: python

   {
       "content": "I agree!",
       "parent_message": {...},  # Original message
       "is_forwarded": false
   }

**Forwarded Message**

.. code-block:: python

   {
       "content": "Check this out",
       "parent_message": null,
       "is_forwarded": true,
       "forwarded_from": {...}  # Original message
   }

.. warning::
   A message cannot be both a reply AND forwarded. This is enforced by database constraint:
   
   .. code-block:: python

      CheckConstraint(
          condition=~Q(is_forwarded=True, parent_message__isnull=False),
          name="forwarded_messages_cant_be_replies"
      )

Message Lifecycle
~~~~~~~~~~~~~~~~~

.. code-block:: text

   1. Created
      ↓
   2. Delivered (acknowledged)
      ↓
   3. Read (read receipt)
      ↓
   4. Optionally: Reacted to
      ↓
   5. Optionally: Edited
      ↓
   6. Optionally: Deleted (soft or hard)

**Created**
   Message saved to database, assigned UUID, timestamp added.

**Delivered**
   User acknowledges receipt (``message.acknowledged``). User added to ``delivered_to`` field.

**Read**
   User opens message (``message.read``). ``ReadReceipt`` created with timestamp.

**Reacted**
   User adds emoji (``message.react``). ``Reaction`` created (one per user).

**Edited**
   Sender updates content (``message.modify``). ``is_edited`` set to ``True``, ``updated_at`` changes.

**Deleted**
   Sender deletes message (``message.modify``):
   
   * Soft delete: ``is_deleted=True`` (configurable)
   * Hard delete: Row removed from database

Media Attachments
~~~~~~~~~~~~~~~~~

Messages can have multiple media attachments via ``MessageMediaAsset``.

**Flow:**

1. Frontend uploads file to CDN (S3, Cloudinary, etc.)
2. Frontend gets URL from CDN
3. Frontend sends message with URL in ``media`` array
4. Backend creates ``MessageMediaAsset`` records

**Why external upload?**

* Separates file storage from chat logic
* Allows choice of storage provider
* Reduces WebSocket payload size
* Better error handling for uploads

**Supported Types:**

* **Images**: JPEG, PNG, GIF, WebP, BMP, HEIC
* **Videos**: MP4, MOV, WebM, OGG, AVI, MKV
* **Audio**: MP3, M4A, AAC, OGG, WAV, Opus
* **Files**: PDF, Word, Excel, PowerPoint, TXT, CSV

Permissions System
------------------

The package uses django-guardian for object-level permissions.

Permission Levels
~~~~~~~~~~~~~~~~~

**User-Level Permissions** (Django default)
   Global permissions like ``is_staff``, ``is_superuser``.

**Object-Level Permissions** (django-guardian)
   Permissions on specific room instances.

**Role-Based Permissions** (Package-specific)
   Permissions granted by role (creator, admin/moderator, member/subscriber).

How Permissions Work
~~~~~~~~~~~~~~~~~~~~

Every event handler is wrapped with permission decorators:

.. code-block:: python

   @can_send_message_to_room
   async def receive_message_send_event(self, data, room):
       # Only executed if user has permission
       message = await EventHandler.create_message(data, self.user)
       await self.send_group(group, "message.dispatch", message)

**Available Decorators:**

* ``@can_access_room`` - User must be a member
* ``@can_access_message`` - User must be a room member
* ``@can_send_message_to_room`` - User must have send permission
* ``@can_modify_message`` - User must be message sender
* ``@can_add_members_to_room`` - User must be admin/moderator
* ``@can_remove_members_from_room`` - User must be admin/moderator
* ``@is_room_admin`` - User must be creator/admin/moderator

GroupChat Permissions
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Object-level permissions
   'can_add_new_participants'
   'can_remove_participants'

**Who has these permissions:**

* Creator: Always
* Admins: Always (auto-assigned on promotion)
* Members: Can be granted individually

**Example:**

.. code-block:: javascript

   // Grant permission to specific user
   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'add_permission',
           data: {
               users: [user_id],
               permissions: ['can_add_new_participants']
           }
       }
   }));

Channel Permissions
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Object-level permissions
   'can_add_new_subscribers'
   'can_remove_subscribers'
   'can_send_messages'

**Who has these permissions:**

* Creator: Always
* Moderators: Always (auto-assigned on promotion)
* Subscribers: Can be granted individually

**Special:** ``can_send_messages`` allows subscribers to post in the channel.

Notifications System
--------------------

The package tracks unread messages via ``ChatNotification`` (when ``ENABLE_NOTIFICATION=True``).

How It Works
~~~~~~~~~~~~

1. **Message Sent**
   
   * ``ChatNotification`` created
   * ``recipients`` = all room members except sender

2. **Message Delivered** (``message.acknowledged``)
   
   * User removed from ``recipients``
   * If ``recipients`` empty → notification deleted

3. **On Connect**
   
   * User receives all pending notifications
   * Grouped by room

**Benefits:**

* Track undelivered messages
* Integrate with push notifications (Firebase, AWS SNS, etc.)
* Show unread counts in UI

Integration with Push Services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Override ``_create_chat_notification`` to integrate:

.. code-block:: python

   from realtime_chat_messaging.utils.handlers import ChatNotificationHandlerMixin
   import firebase_admin

   class CustomChatNotificationHandler(ChatNotificationHandlerMixin):
       
       @staticmethod
       def create_chat_notification(message, type, user):
           # Create notification in database
           ChatNotificationHandlerMixin.create_chat_notification(
               message, type, user
           )
           
           # Send push notification
           room = message.room
           if hasattr(room, "participants"):
               recipients = room.participants.exclude(id=user.id)
           else:
               recipients = room.subscribers.exclude(id=user.id)
           
           for recipient in recipients:
               if recipient.fcm_token:
                   firebase_admin.messaging.send(
                       messaging.Message(
                           notification=messaging.Notification(
                               title=f"New message from {user.username}",
                               body=message.content[:100]
                           ),
                           token=recipient.fcm_token
                       )
                   )

Then register in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler"
   }

Channel Layer (Redis)
---------------------

The channel layer enables WebSocket communication across multiple connections and servers.

What It Does
~~~~~~~~~~~~

* **Routes messages** between WebSocket connections
* **Manages groups** (rooms that users subscribe to)
* **Persists connection state** (which channels are in which groups)
* **Scales horizontally** (multiple servers share same Redis)

Groups Explained
~~~~~~~~~~~~~~~~

When you join a room, you're added to a channel layer group:

.. code-block:: python

   # Group name format
   group_name = f"group-{room_id}"
   
   # Add user's channel to group
   await self.channel_layer.group_add(group_name, self.channel_name)

When a message is sent:

.. code-block:: python

   # Broadcast to all users in room
   await self.channel_layer.group_send(
       group_name,
       {
           "type": "broadcast_group",
           "eventType": "message.dispatch",
           "data": message_data
       }
   )

**User-Specific Groups:**

Every user also has their own group for private events:

.. code-block:: python

   user_group = f"user-{user_id}"

Used for:

* ``room.list`` responses
* ``room.info`` responses
* ``roomexit.dispatch`` (when removed from room)

Why Redis?
~~~~~~~~~~

**In-Memory Channel Layer** (Development only)

* ❌ Single server only
* ❌ Lost on restart
* ✅ No setup required

**Redis Channel Layer** (Production)

* ✅ Multiple servers
* ✅ Persists across restarts
* ✅ High performance
* ✅ Reliable delivery

Session Management
~~~~~~~~~~~~~~~~~~

The package handles session cleanup automatically:

**On Connect:**

1. Check if user has previous connection
2. Remove old channel from all groups
3. Add new channel to all groups
4. Store new channel name

**On Disconnect:**

1. Remove channel from all groups
2. Clear temporary channel name
3. Keep persistent channel name (for adding other users to groups)

**Why?**

Prevents duplicate connections and ensures users receive messages on latest connection only.

.. note::
   **Current Limitation:** Multi-device support is not yet implemented. Connecting from multiple devices will disconnect previous connections. This will be improved in future versions.

Dynamic Component System
------------------------

The package uses a dynamic loading system for maximum flexibility.

Swappable Models
~~~~~~~~~~~~~~~~

Like Django's User model (``AUTH_USER_MODEL``), all chat models are swappable:

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.CustomMessage",
           "Room": "myapp.CustomRoom",
           # ... swap any model
       }
   }

**Requirements:**

* Must inherit from abstract base (e.g., ``AbstractMessage``)
* Must include all required fields
* Must be registered before migrations

Swappable Serializers
~~~~~~~~~~~~~~~~~~~~~

Customize JSON representation:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "SERIALIZERS": {
           "MessageSerializer": "myapp.CustomMessageSerializer",
           # ... swap any serializer
       }
   }

**Requirements:**

* Must inherit from base serializer or provide same interface
* Must handle all required fields
* Gets loaded dynamically at runtime

Swappable Handlers
~~~~~~~~~~~~~~~~~~

Override business logic:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.CustomEventHandler",
       "PERMISSION_HANDLER_CLASS": "myapp.CustomPermissionHandler",
   }

**Requirements:**

* Must inherit from base handler
* Can override specific methods
* All methods must have same signature

Swappable Event Mapper
~~~~~~~~~~~~~~~~~~~~~~~

Add custom events:

.. code-block:: python

   # myapp/events.py
   from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers

   def custom_event_mapper(consumer_instance):
       default = map_event_type_to_handlers(consumer_instance)
       default['message.pin'] = consumer_instance.handle_pin_message
       return default

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "EVENT_MAPPER": "myapp.events.custom_event_mapper"
   }

Best Practices
--------------

Room Type Selection
~~~~~~~~~~~~~~~~~~~

**Use OneToOneChat when:**

* Two users only
* Equal permissions
* Simple private chat

**Use GroupChat when:**

* Multiple users (3+)
* Need admin hierarchy
* Collaborative work

**Use Channel when:**

* One-to-many communication
* Broadcast-style messaging
* Read-mostly content

Message Acknowledgment vs Read Receipts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Use ``message.acknowledged`` for:**

* Delivery confirmation
* "Message delivered to device"
* Tracking message arrival

**Use ``message.read`` for:**

* Read receipts ("seen by")
* User opened message
* Engagement tracking

**Both or Neither:**

* Both: Full WhatsApp-style delivery + read
* Neither: Simple chat without status

Soft vs Hard Delete
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "MESSAGE_SOFT_DELETE": True  # or False
   }

**Soft Delete (``True``):**

* Sets ``is_deleted=True``
* Message stays in database
* Can be recovered
* Shows "Message deleted" in UI

**Hard Delete (``False``):**

* Removes from database
* Cannot be recovered
* Replies/forwards lose reference

**Choose based on:**

* Compliance requirements
* Storage constraints
* User expectations

Next Steps
----------

Now that you understand core concepts:

* :doc:`../user-guide/room-types` - Deep dive into each room type
* :doc:`../user-guide/messages` - Master message features
* :doc:`../user-guide/permissions` - Advanced permission patterns
* :doc:`../customization/models` - Extend and customize models

Need Help?
----------

* :doc:`../troubleshooting` - Common issues
* :doc:`../faq` - Frequently asked questions
* `GitHub Discussions <https://github.com/yourusername/django-realtime-chat-messaging/discussions>`_ - Ask questions