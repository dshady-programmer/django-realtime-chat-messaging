Room Types Guide
================

Deep dive into the three room types: OneToOneChat, GroupChat, and Channel. Understand their differences, use cases, and best practices.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

Django Realtime Chat Messaging provides three polymorphic room types, each optimized for different communication patterns:

.. list-table::
   :header-rows: 1
   :widths: 20 25 25 30

   * - Room Type
     - Participants
     - Access Control
     - Primary Use Case
   * - OneToOneChat
     - Exactly 2
     - Equal permissions
     - Direct messaging
   * - GroupChat
     - 3+ (configurable)
     - Admin hierarchy
     - Team collaboration
   * - Channel
     - Unlimited (configurable)
     - Moderator-controlled
     - Broadcasting

All three inherit from the base ``Room`` model, sharing common fields while adding type-specific functionality.

OneToOneChat
------------

Private conversations between exactly two users.

Characteristics
~~~~~~~~~~~~~~~

**Fixed Participant Count**
   Always exactly 2 participants. Enforced by database signal:
   
   .. code-block:: python

      @receiver(m2m_changed, sender=OneToOneChat.participants.through)
      def enforce_two_participants(sender, instance, action, pk_set, **kwargs):
          if instance.participants.count() != 2:
              raise ValidationError("OneToOneChat must have exactly 2 participants")

**No Hierarchy**
   Both users have equal permissions - no admins, creators, or special roles.

**Duplicate Prevention**
   Cannot create multiple chats between the same two users:
   
   .. code-block:: python

      # Signal checks for existing chat
      existing = OneToOneChat.objects.filter(
          participants=user1
      ).filter(
          participants=user2
      ).exists()
      
      if existing:
          raise ValidationError("Chat already exists")

**Cannot Leave**
   Users cannot leave a OneToOneChat. The room is deleted if a user is removed.

Database Schema
~~~~~~~~~~~~~~~

.. code-block:: python

   class OneToOneChat(Room):
       participants = models.ManyToManyField(User, related_name="chats")
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_ONETOONECHAT_MODEL'

**Inherited from Room:**

* ``id`` - UUID primary key
* ``last_message`` - ForeignKey to most recent message
* ``created_at`` - Timestamp
* ``updated_at`` - Auto-updated timestamp
* ``preferences`` - JSONField for custom settings

Creating OneToOneChat
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.create',
       data: {
           type: 'OneToOneChat',
           participants: [other_user_id]  // Just one other user
       }
   }));

.. note::
   You only specify the OTHER user's ID. The current user is automatically added by the backend.

Response:

.. code-block:: json

   {
       "eventType": "roomcreate.dispatch",
       "data": {
           "id": "uuid",
           "type": "OneToOneChat",
           "participants": [
               {"id": 1, "username": "alice"},
               {"id": 2, "username": "bob"}
           ],
           "created_at": "2024-01-10T12:00:00Z"
       }
   }

Use Cases
~~~~~~~~~

**Direct Messaging**
   WhatsApp, Facebook Messenger style one-on-one conversations.

**Customer Support**
   Agent ↔ Customer support chats.

**Private Discussions**
   Confidential conversations between two team members.

**Dating Apps**
   Matched user conversations.

Best Practices
~~~~~~~~~~~~~~

**Check for Existing Chat First**

.. code-block:: javascript

   // Get all rooms first
   socket.send(JSON.stringify({
       event_type: 'room.list',
       data: {}
   }));

   // Check if chat exists
   const existingChat = rooms.find(room => 
       room.type === 'OneToOneChat' && 
       room.peer.id === targetUserId
   );

   if (!existingChat) {
       // Create new chat
       socket.send(JSON.stringify({
           event_type: 'room.create',
           data: {
               type: 'OneToOneChat',
               participants: [targetUserId]
           }
       }));
   }

**Handle Race Conditions**

If two users try to create a chat simultaneously, one will fail with error code 4005. Handle gracefully:

.. code-block:: javascript

   socket.onmessage = (e) => {
       const response = JSON.parse(e.data);
       
       if (response.error && response.error.code === 4005) {
           // Chat already exists, fetch room list
           socket.send(JSON.stringify({
               event_type: 'room.list',
               data: {}
           }));
       }
   };

**Display Peer Information**

In OneToOneChat list serializer, you get ``peer`` instead of ``participants``:

.. code-block:: javascript

   {
       "id": "uuid",
       "type": "OneToOneChat",
       "peer": {
           "id": 2,
           "username": "bob",
           "first_name": "Bob",
           "last_name": "Johnson"
       },
       "last_message": {...}
   }

Use this to display the other user's name/avatar in your UI.

Limitations
~~~~~~~~~~~

* Cannot add more participants (always 2)
* Cannot leave without deleting the chat
* No role hierarchy
* Duplicate prevention can cause race conditions (will be improved in future versions)

GroupChat
---------

Multi-user conversations with admin hierarchy and granular permissions.

Characteristics
~~~~~~~~~~~~~~~

**Flexible Participant Count**
   3 to ``max_participants`` (default: 100, configurable).

**Three-Tier Hierarchy**
   
   1. **Creator** - Ultimate authority, cannot be removed
   2. **Admins** - Can manage members and permissions
   3. **Members** - Can send messages and read

**Invitation-Only**
   Cannot join publicly. Must be added by creator/admin.

**Group Locking**
   Optional: Restrict messaging to admins only (``group_locked=True``).

Database Schema
~~~~~~~~~~~~~~~

.. code-block:: python

   class GroupChat(Room):
       name = models.CharField(max_length=64)
       description = models.TextField(null=True, blank=True)
       creator = models.ForeignKey(User, on_delete=models.CASCADE, 
                                   related_name="groups_owned")
       participants = models.ManyToManyField(User, related_name="groups_in")
       admins = models.ManyToManyField(User, related_name="groups_moderated")
       max_participants = models.PositiveBigIntegerField(default=100)
       avatar = models.URLField(null=True, blank=True)
       join_approval_required = models.BooleanField(default=False)
       group_locked = models.BooleanField(default=False)
       
       class Meta:
           permissions = [
               ("can_add_new_participants", "Can add new participants"),
               ("can_remove_participants", "Can remove participants")
           ]
           swappable = 'REALTIME_CHAT_MESSAGING_GROUPCHAT_MODEL'

Creating GroupChat
~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.create',
       data: {
           type: 'GroupChat',
           name: 'Project Alpha Team',
           description: 'Discussion for Project Alpha deliverables',
           participants: [2, 3, 4, 5],  // Initial members
           extra_fields: {
               max_participants: 50,
               join_approval_required: true,
               group_locked: false,  // Anyone can send messages
               avatar: 'https://cdn.example.com/group-avatar.jpg',
               preferences: {
                   theme: 'dark',
                   notifications: 'mentions_only'
               }
           }
       }
   }));

Response:

.. code-block:: json

   {
       "eventType": "roomcreate.dispatch",
       "data": {
           "id": "uuid",
           "type": "GroupChat",
           "name": "Project Alpha Team",
           "description": "Discussion for Project Alpha deliverables",
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
           "group_locked": false,
           "created_at": "2024-01-10T12:00:00Z"
       }
   }

Role Management
~~~~~~~~~~~~~~~

Promoting to Admin
^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'add_admin',
           data: {
               users: [2, 3]  // User IDs to promote
           }
       }
   }));

**What happens:**

1. Users added to ``admins`` ManyToMany field
2. Automatically granted ``can_add_new_participants`` permission
3. Automatically granted ``can_remove_participants`` permission
4. Receive ``roomupdate.dispatch`` event

Demoting Admin
^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'remove_admin',
           data: {
               users: [2]
           }
       }
   }));

**What happens:**

1. User removed from ``admins`` field
2. Permissions automatically revoked
3. Still remains a participant

.. warning::
   **Cannot demote the creator!** The creator is automatically added as admin on creation and cannot be removed from admin role.

Granting Custom Permissions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Grant permissions without making someone a full admin:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'add_permission',
           data: {
               users: [4, 5],
               permissions: ['can_add_new_participants']
           }
       }
   }));

**Available permissions:**

* ``can_add_new_participants`` - Invite new members
* ``can_remove_participants`` - Kick members

Member Management
~~~~~~~~~~~~~~~~~

Adding Members
^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.add_members',
       data: {
           room_id: 'group-uuid',
           members: [6, 7, 8]
       }
   }));

**Who can add:**

* Creator (always)
* Admins (always)
* Users with ``can_add_new_participants`` permission

**Broadcast:**

All members (including new ones) receive:

.. code-block:: json

   {
       "eventType": "roomaddmembers.dispatch",
       "data": {
           "room": {"id": "uuid", "name": "Project Alpha Team"},
           "new_members": ["david", "emma", "frank"],
           "added_by": "alice"
       }
   }

Removing Members
^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.remove_members',
       data: {
           room_id: 'group-uuid',
           members: [4]
       }
   }));

**Who can remove:**

* Creator (always)
* Admins (always)
* Users with ``can_remove_participants`` permission

**Restrictions:**

* Cannot remove the creator (only creator can leave voluntarily)
* If you remove an admin, they're also removed from admin role

**Broadcast:**

Removed user receives:

.. code-block:: json

   {
       "eventType": "roomexit.dispatch",
       "data": {
           "room": {"id": "uuid"},
           "message": "You have been removed by alice"
       }
   }

Remaining members receive:

.. code-block:: json

   {
       "eventType": "roomremovemembers.dispatch",
       "data": {
           "room": {"id": "uuid"},
           "removed_members": ["david"],
           "removed_by": "alice"
       }
   }

Group Locking
~~~~~~~~~~~~~

When ``group_locked=True``, only creator and admins can send messages:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'update',
           data: {
               group_locked: true
           }
       }
   }));

**Use cases:**

* Announcement-only groups
* Read-only groups for most members
* Temporary message restriction during conflicts

**Permission check:**

.. code-block:: python

   if room.group_locked:
       is_permitted = (
           room.creator == user or 
           user in room.admins.all()
       )
   else:
       is_permitted = user in room.participants.all()

Use Cases
~~~~~~~~~

**Team Collaboration**
   Project teams, development teams, department chats.

**Social Groups**
   Friend groups, family groups, hobby groups.

**Educational**
   Class groups, study groups, teacher-student discussions.

**Event Planning**
   Wedding planning, party organization, event coordination.

Best Practices
~~~~~~~~~~~~~~

**Set Reasonable Max Participants**

.. code-block:: javascript

   // For small teams
   max_participants: 10

   // For departments
   max_participants: 50

   // For communities
   max_participants: 200

**Use Group Locking Wisely**

Lock groups when:

* Making important announcements
* During heated discussions (cool-down period)
* Converting to announcement-only mode

**Name Groups Descriptively**

.. code-block:: javascript

   // Good
   name: "Engineering - Backend Team"
   name: "Project Alpha - Q1 2024"
   
   // Bad
   name: "Group"
   name: "Chat1"

**Set Clear Descriptions**

.. code-block:: javascript

   description: "Backend engineering team. For technical discussions, code reviews, and sprint planning."

Channel
-------

Broadcast channels where only moderators can post (by default). Perfect for one-to-many communication.

Characteristics
~~~~~~~~~~~~~~~

**One-to-Many Communication**
   Moderators broadcast, subscribers receive.

**Large Subscriber Base**
   Default ``max_subscribers``: 300 (configurable to 1000+).

**Public or Private**
   
   * Public: Anyone can join (``is_public=True``)
   * Private: Moderator must add (``is_public=False``)

**Moderator Control**
   Only creator, moderators, or users with ``can_send_messages`` permission can post.

Database Schema
~~~~~~~~~~~~~~~

.. code-block:: python

   class Channel(Room):
       name = models.CharField(max_length=64)
       description = models.TextField(null=True, blank=True)
       creator = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name="channels_owned")
       subscribers = models.ManyToManyField(User, related_name="channels_subscribed")
       moderators = models.ManyToManyField(User, related_name="channels_moderated")
       is_public = models.BooleanField(default=False)
       avatar = models.URLField(null=True, blank=True)
       max_subscribers = models.PositiveBigIntegerField(default=300)
       
       class Meta:
           permissions = [
               ("can_add_new_subscribers", "Can add new subscribers"),
               ("can_remove_subscribers", "Can remove subscribers"),
               ("can_send_messages", "Can send messages"),
           ]
           swappable = 'REALTIME_CHAT_MESSAGING_CHANNEL_MODEL'

Creating Channel
~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.create',
       data: {
           type: 'Channel',
           name: 'Company Announcements',
           description: 'Official company-wide announcements and updates',
           subscribers: [2, 3, 4],  // Initial subscribers
           extra_fields: {
               is_public: true,
               max_subscribers: 1000,
               avatar: 'https://cdn.example.com/channel-logo.jpg',
               preferences: {
                   allow_comments: false
               }
           }
       }
   }));

Public vs Private Channels
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Public Channel
^^^^^^^^^^^^^^

.. code-block:: javascript

   extra_fields: {
       is_public: true
   }

**Anyone can join:**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.join',
       data: {
           room_id: 'channel-uuid'
       }
   }));

**Use cases:**

* Company announcements
* Community updates
* Public news feeds

Private Channel
^^^^^^^^^^^^^^^

.. code-block:: javascript

   extra_fields: {
       is_public: false
   }

**Moderator must add subscribers:**

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.add_members',
       data: {
           room_id: 'channel-uuid',
           members: [5, 6, 7]
       }
   }));

**Use cases:**

* Executive announcements
* Paid content channels
* Exclusive communities

Role Management
~~~~~~~~~~~~~~~

Promoting to Moderator
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'channel-uuid',
           action: 'add_moderator',
           data: {
               users: [2, 3]
           }
       }
   }));

**Moderator permissions:**

* Can send messages
* Can add/remove subscribers
* Can grant ``can_send_messages`` to specific subscribers

Allowing Subscribers to Post
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, only moderators can post. To allow specific subscribers:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'channel-uuid',
           action: 'add_permission',
           data: {
               users: [4, 5],
               permissions: ['can_send_messages']
           }
       }
   }));

**Use case:** Community channels where trusted members can post.

Subscriber Management
~~~~~~~~~~~~~~~~~~~~~

Adding Subscribers
^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.add_members',  // Same event for GroupChat and Channel
       data: {
           room_id: 'channel-uuid',
           members: [6, 7, 8]
       }
   }));

**Who can add:**

* Creator
* Moderators
* Users with ``can_add_new_subscribers`` permission

Removing Subscribers
^^^^^^^^^^^^^^^^^^^^

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.remove_members',
       data: {
           room_id: 'channel-uuid',
           members: [4]
       }
   }));

**Who can remove:**

* Creator
* Moderators
* Users with ``can_remove_subscribers`` permission

Use Cases
~~~~~~~~~

**Company Announcements**
   HR updates, company news, policy changes.

**Content Broadcasting**
   News channels, blog updates, product launches.

**Community Updates**
   Open source project announcements, community news.

**Educational Content**
   Course announcements, lecture notes, assignment updates.

Best Practices
~~~~~~~~~~~~~~

**Choose Public/Private Carefully**

Public when:

* Content is for everyone
* Organic growth desired
* No sensitive information

Private when:

* Exclusive content
* Controlled audience
* Sensitive information

**Set Max Subscribers Appropriately**

.. code-block:: javascript

   // Small organization
   max_subscribers: 500

   // Medium company
   max_subscribers: 2000

   // Large community
   max_subscribers: 10000

**Use Moderators for Large Channels**

For channels with 100+ subscribers, appoint multiple moderators to:

* Share moderation workload
* Ensure 24/7 coverage
* Distribute authority

**Disable Comments (Optional)**

If you want pure broadcasting with no subscriber interaction:

.. code-block:: javascript

   preferences: {
       allow_reactions: false,  // Custom implementation
       allow_comments: false     // Custom implementation
   }

.. note::
   Comment/reaction disabling requires custom implementation. The base package allows all subscribers to react.

Comparison Table
----------------

.. list-table::
   :header-rows: 1
   :widths: 20 26 27 27

   * - Feature
     - OneToOneChat
     - GroupChat
     - Channel
   * - Participants
     - Exactly 2
     - 3 to max_participants
     - 1 to max_subscribers
   * - Hierarchy
     - None
     - Creator, Admins, Members
     - Creator, Moderators, Subscribers
   * - Can Join Publicly
     - No
     - No
     - Yes (if is_public=True)
   * - Who Can Send
     - Both users
     - All participants (unless locked)
     - Moderators + permitted users
   * - Can Leave
     - No
     - Yes
     - Yes
   * - Max Size
     - 2
     - ~100 (configurable)
     - ~1000+ (configurable)
   * - Use Case
     - Direct messaging
     - Collaboration
     - Broadcasting

Choosing the Right Room Type
-----------------------------

Decision Tree
~~~~~~~~~~~~~

.. code-block:: text

   How many people?
   │
   ├─ 2 people
   │  └─> OneToOneChat
   │
   ├─ 3-50 people
   │  │
   │  ├─ Need hierarchy?
   │  │  ├─ Yes └─> GroupChat
   │  │  └─ No  └─> GroupChat (all members equal)
   │  │
   │  └─ One-way communication?
   │     └─> Channel
   │
   └─ 50+ people
      │
      ├─ Two-way discussion?
      │  └─> GroupChat
      │
      └─ Broadcast-style?
         └─> Channel

Examples by Scenario
~~~~~~~~~~~~~~~~~~~~~

**Customer Support Chat**
   → OneToOneChat (agent ↔ customer)

**Development Team (10 people)**
   → GroupChat (collaborative work)

**Company Announcements (500 employees)**
   → Channel (HR broadcasts to all)

**Friend Group (5 people)**
   → GroupChat (casual chat)

**Open Source Project Updates**
   → Channel (public, broadcast-style)

**Executive Team (5 people)**
   → GroupChat (discussions, decisions)

**Newsletter/Blog Updates**
   → Channel (content distribution)

Advanced Patterns
-----------------

Hybrid: GroupChat with Read-Only Periods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start as normal GroupChat, lock during announcements:

.. code-block:: javascript

   // Normal mode
   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'update',
           data: {group_locked: false}
       }
   }));

   // Announcement mode
   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'update',
           data: {group_locked: true}
       }
   }));

Multi-Channel Architecture
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Large organizations can create channel hierarchy:

.. code-block:: text

   Company Announcements (public channel)
   ├── Engineering Updates (private channel)
   │   ├── Backend Team (group chat)
   │   └── Frontend Team (group chat)
   ├── Sales Updates (private channel)
   └── HR Announcements (private channel)

Progressive Permission Grants
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start restrictive, grant permissions as users earn trust:

1. New subscriber: Read-only
2. Active member: ``can_send_messages`` granted
3. Trusted member: Promoted to moderator

See Also
--------

* :doc:`messages` - Message features (replies, forwarding, media)
* :doc:`permissions` - Detailed permission system
* :doc:`../customization/models` - Extend room models
* :doc:`../api-reference/events` - Complete event reference

Need Help?
----------

* :doc:`../troubleshooting` - Common issues
* :doc:`../faq` - Frequently asked questions