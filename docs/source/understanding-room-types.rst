Understanding Room Types
========================

Django Realtime Chat Messaging provides three distinct room types, each designed for different communication patterns. This guide explains when and how to use each type.

The Three Room Types
---------------------

.. list-table::
   :header-rows: 1
   :widths: 20 30 25 25

   * - Room Type
     - Best For
     - Who Can Post
     - Max Participants
   * - OneToOneChat
     - Direct messages, support tickets
     - Both participants
     - Exactly 2
   * - GroupChat
     - Team discussions, project rooms
     - All participants (or admins only if locked)
     - Configurable (default 100)
   * - Channel
     - Announcements, broadcasts
     - Moderators + permitted users
     - Configurable (default 300)

OneToOneChat: Direct Messaging
-------------------------------

**Use Cases:**
   - Private conversations between two users
   - Customer support tickets (agent + customer)
   - Direct messages in social platforms
   - One-on-one consultations

Model Structure
~~~~~~~~~~~~~~~

.. code-block:: python

   class OneToOneChat(Room):
       participants = ManyToManyField(User, related_name="chats")

**Key Characteristics:**

- Must have exactly 2 participants
- No admin or creator concept
- Both users have equal permissions
- System prevents duplicate chats between same pair
- No max participants limit (always 2)

Creating a OneToOneChat
~~~~~~~~~~~~~~~~~~~~~~~

**Via WebSocket:**

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.create",
       data: {
           type: "OneToOneChat",
           participants: [user1_id, user2_id]
       }
   }));

**Programmatically:**

.. code-block:: python

   from realtime_chat_messaging.models import OneToOneChat
   from django.contrib.auth import get_user_model

   User = get_user_model()
   user1 = User.objects.get(username='alice')
   user2 = User.objects.get(username='bob')

   # Create chat
   chat = OneToOneChat.objects.create()
   chat.participants.add(user1, user2)

**Important Rules:**

1. Must add exactly 2 participants
2. System prevents duplicate chats (signal enforcement)
3. Cannot convert to GroupChat or Channel
4. Both users can send messages, react, and reply

Permissions
~~~~~~~~~~~

Both participants have equal rights:

- Send messages
- Read all messages
- React to messages
- Reply to messages
- Mark messages as read

Neither participant can:

- Add new members (would violate 2-participant rule)
- Remove the other participant
- Change room settings

GroupChat: Multi-User Discussions
----------------------------------

**Use Cases:**
   - Team collaboration spaces
   - Project discussion rooms
   - Friend group chats
   - Study groups
   - Community discussions

Model Structure
~~~~~~~~~~~~~~~

.. code-block:: python

   class GroupChat(Room):
       name = CharField(max_length=64)
       description = TextField(null=True, blank=True)
       creator = ForeignKey(User, related_name="groups_owned")
       admins = ManyToManyField(User, related_name="groups_moderated")
       participants = ManyToManyField(User, related_name="groups_in")
       max_participants = PositiveBigIntegerField(default=100)
       avatar = URLField(null=True, blank=True)
       join_approval_required = BooleanField(default=False)
       group_locked = BooleanField(default=False)

**Key Characteristics:**

- Has a creator (owner with maximum permissions)
- Supports multiple admins
- Configurable maximum participants
- Can be "locked" (only admins can send messages)
- Creator automatically added as admin
- Group deleted if no participants remain

Creating a GroupChat
~~~~~~~~~~~~~~~~~~~~

**Via WebSocket:**

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.create",
       data: {
           type: "GroupChat",
           name: "Project Team",
           description: "Our awesome project",
           participants: [user2_id, user3_id],  // Creator added automatically
           extra_fields: {
               max_participants: 50,
               avatar: "https://example.com/avatar.jpg",
               group_locked: false
           }
       }
   }));

**Programmatically:**

.. code-block:: python

   from realtime_chat_messaging.models import GroupChat

   group = GroupChat.objects.create(
       name="Project Team",
       description="Team discussion space",
       creator=user1,
       max_participants=50
   )
   # Creator added as participant and admin automatically via signals
   
   # Add other members
   group.participants.add(user2, user3)
   
   # Optionally add more admins
   group.admins.add(user2)

Group Locking
~~~~~~~~~~~~~

When ``group_locked = True``, only creator and admins can send messages:

.. code-block:: python

   # Lock the group
   group.group_locked = True
   group.save()

   # Now only creator/admins can post
   # Regular participants can still read and react

**Use cases for locking:**

- Announcements within team (admins post, everyone reads)
- Q&A sessions (moderators post questions)
- Temporary discussion freeze

Permissions Hierarchy
~~~~~~~~~~~~~~~~~~~~~

**Creator (Highest)**
   - All admin permissions
   - Cannot be removed by admins
   - Can remove any participant including admins
   - Can modify group settings
   - Can delete the group

**Admins**
   - Add new participants
   - Remove participants (except creator)
   - Send messages even when locked
   - Manage permissions for specific users
   - Promote/demote other admins (if they have permission)

**Regular Participants**
   - Send messages (unless locked)
   - Read all messages
   - React and reply to messages
   - Leave group voluntarily
   - Cannot add or remove members (unless granted permission)

Granting Custom Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Admins and creator can grant specific permissions to users:

.. code-block:: python

   # Via WebSocket
   ws.send(JSON.stringify({
       event_type: "room.modify",
       data: {
           room_id: "group-uuid",
           action: "add_permission",
           data: {
               users: [user_id],
               permission: ["can_add_new_participants"]
           }
       }
   }));

Available group permissions:

- ``can_add_new_participants``
- ``can_remove_participants``

Channel: Broadcast Communication
---------------------------------

**Use Cases:**
   - Company announcements
   - News channels
   - Public broadcasts
   - Large community updates
   - One-to-many communication

Model Structure
~~~~~~~~~~~~~~~

.. code-block:: python

   class Channel(Room):
       name = CharField(max_length=64)
       description = TextField(null=True, blank=True)
       creator = ForeignKey(User, related_name="channels_owned")
       subscribers = ManyToManyField(User, related_name="channels_subscribed")
       is_public = BooleanField(default=False)
       avatar = URLField(null=True, blank=True)
       moderators = ManyToManyField(User, related_name="channels_moderated")
       max_subscribers = PositiveBigIntegerField(default=300)

**Key Characteristics:**

- Always "locked" - only moderators can post by default
- Can be public (anyone can subscribe) or private (invite-only)
- Uses "subscribers" instead of "participants"
- Supports larger member counts
- Perfect for broadcast scenarios

Creating a Channel
~~~~~~~~~~~~~~~~~~

**Via WebSocket:**

.. code-block:: javascript

   ws.send(JSON.stringify({
       event_type: "room.create",
       data: {
           type: "Channel",
           name: "Announcements",
           description: "Company-wide updates",
           is_public: true,
           subscribers: [user2_id, user3_id],  // Creator added automatically
           extra_fields: {
               max_subscribers: 500,
               avatar: "https://example.com/channel-avatar.jpg"
           }
       }
   }));

**Programmatically:**

.. code-block:: python

   from realtime_chat_messaging.models import Channel

   channel = Channel.objects.create(
       name="Announcements",
       description="Important updates",
       creator=user1,
       is_public=True,
       max_subscribers=500
   )
   # Creator added as subscriber and moderator automatically
   
   # Add subscribers
   channel.subscribers.add(user2, user3, user4)
   
   # Add more moderators
   channel.moderators.add(user2)

Public vs Private Channels
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Public Channels (is_public=True)**

Users can join without invitation:

.. code-block:: javascript

   // Anyone can join
   ws.send(JSON.stringify({
       event_type: "room.join",
       data: {
           room_id: "channel-uuid"
       }
   }));

**Private Channels (is_public=False)**

Users must be added by moderators:

.. code-block:: javascript

   // Only moderators can add subscribers
   ws.send(JSON.stringify({
       event_type: "room.add_members",
       data: {
           room_id: "channel-uuid",
           members: [user_id]
       }
   }));

Permissions Hierarchy
~~~~~~~~~~~~~~~~~~~~~

**Creator (Highest)**
   - All moderator permissions
   - Cannot be removed by moderators
   - Can remove any subscriber including moderators
   - Can modify channel settings
   - Can delete the channel

**Moderators**
   - Send messages (bypassing post restrictions)
   - Add new subscribers
   - Remove subscribers (except creator)
   - Grant posting permissions to specific users
   - Manage channel settings

**Subscribers**
   - Read all messages
   - React to messages
   - Reply to messages (if they have send permission)
   - Cannot post messages (unless granted permission)
   - Can unsubscribe voluntarily

Granting Posting Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allow specific subscribers to post:

.. code-block:: python

   # Via WebSocket
   ws.send(JSON.stringify({
       event_type: "room.modify",
       data: {
           room_id: "channel-uuid",
           action: "add_permission",
           data: {
               users: [user_id],
               permission: ["can_send_messages"]
           }
       }
   }));

Available channel permissions:

- ``can_send_messages``
- ``can_add_new_subscribers``
- ``can_remove_subscribers``

Choosing the Right Room Type
-----------------------------

Decision Tree
~~~~~~~~~~~~~

.. code-block:: text

   Need private 1-on-1 communication?
   └─ YES → OneToOneChat
   └─ NO  → Continue
   
   Need two-way discussion with multiple people?
   └─ YES → GroupChat
   └─ NO  → Continue
   
   Need broadcast with controlled posting?
   └─ YES → Channel

Comparison Table
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 20 25 25 30

   * - Feature
     - OneToOneChat
     - GroupChat
     - Channel
   * - Participant Limit
     - Always 2
     - Configurable (default 100)
     - Configurable (default 300)
   * - Creator/Owner
     - No
     - Yes
     - Yes
   * - Admins/Moderators
     - No
     - Yes (admins)
     - Yes (moderators)
   * - Default Posting Rights
     - Both users
     - All participants
     - Moderators only
   * - Can Be Locked
     - No
     - Yes
     - Always locked
   * - Public Join
     - No
     - No (by default)
     - Yes (if is_public=True)
   * - Best For
     - DMs, support
     - Team collaboration
     - Broadcasts, announcements

Common Patterns
---------------

WhatsApp-Style Setup
~~~~~~~~~~~~~~~~~~~~

- Use ``OneToOneChat`` for direct messages
- Use ``GroupChat`` with ``group_locked=False`` for group chats
- All participants can send messages

Slack-Style Setup
~~~~~~~~~~~~~~~~~

- Use ``GroupChat`` for team channels
- Use ``Channel`` with ``is_public=True`` for public channels
- Moderate permissions based on roles

Discord-Style Setup
~~~~~~~~~~~~~~~~~~~

- Use ``Channel`` with ``is_public=True`` for public channels
- Use ``Channel`` with ``is_public=False`` for private channels
- Use permission system for role-based access

Telegram-Style Setup
~~~~~~~~~~~~~~~~~~~~

- Use ``OneToOneChat`` for direct chats
- Use ``GroupChat`` for regular groups
- Use ``Channel`` for broadcast channels (creator posts only)

Advanced: Polymorphic Queries
------------------------------

Since all room types inherit from ``Room``, you can query across types:

.. code-block:: python

   from realtime_chat_messaging.models import Room
   from django.db.models import Q

   # Get all rooms for a user
   user_rooms = Room.objects.filter(
       Q(onetoonechat__participants=user) |
       Q(groupchat__participants=user) |
       Q(channel__subscribers=user)
   )

   # Each room retains its specific type
   for room in user_rooms:
       if isinstance(room, OneToOneChat):
           print(f"DM with {room.participants.exclude(id=user.id).first()}")
       elif isinstance(room, GroupChat):
           print(f"Group: {room.name}")
       elif isinstance(room, Channel):
           print(f"Channel: {room.name}")

Room Lifecycle
--------------

Creation
~~~~~~~~

All room types are created via signals that automatically:

1. Add creator as participant/subscriber
2. Add creator as admin/moderator (GroupChat/Channel)
3. Grant default permissions to creator

Deletion
~~~~~~~~

Rooms are automatically deleted when:

- ``GroupChat`` or ``Channel`` has no participants/subscribers
- Triggered by signal when last member leaves/is removed

.. warning::
   ``OneToOneChat`` is **never** automatically deleted. Even if both users are inactive, the chat and its messages persist. You must handle deletion manually if needed.

Signals in Action
~~~~~~~~~~~~~~~~~

The package uses Django signals to enforce business rules:

.. code-block:: python

   # GroupChat signals
   - post_save: Add creator as participant and admin
   - m2m_changed (participants): Enforce max_participants
   - m2m_changed (participants): Delete if no participants
   - m2m_changed (admins): Auto-grant/revoke permissions

   # Channel signals
   - post_save: Add creator as subscriber and moderator
   - m2m_changed (subscribers): Enforce max_subscribers
   - m2m_changed (subscribers): Delete if no subscribers
   - m2m_changed (moderators): Auto-grant/revoke permissions

   # OneToOneChat signals
   - m2m_changed (participants): Enforce exactly 2 participants
   - m2m_changed (participants): Prevent duplicate chats

Next Steps
----------

Now that you understand room types:

- :doc:`authentication-setup` - Set up user authentication
- :doc:`websocket/room-events` - Learn to create and manage rooms
- :doc:`guides/whatsapp-style` - Build WhatsApp-style chat
- :doc:`guides/slack-style` - Build Slack-style communication