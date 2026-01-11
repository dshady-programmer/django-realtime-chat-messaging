Permissions Guide
=================

Understanding and customizing the permission system using django-guardian for object-level permissions.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

The package uses three permission levels:

1. **Django Default** - Superuser, staff permissions
2. **Object-Level** (django-guardian) - Permissions on specific rooms
3. **Role-Based** - Creator, Admin/Moderator, Member/Subscriber roles

Permission Flow
~~~~~~~~~~~~~~~

.. code-block:: text

   Event Received
        ↓
   Permission Decorator Check
        ↓
   ├─ Pass → Execute Handler
   └─ Fail → Return 4002 Error

Built-in Permission Decorators
-------------------------------

All event handlers use permission decorators:

@can_access_room
~~~~~~~~~~~~~~~~

User must be a member of the room.

.. code-block:: python

   @can_access_room
   async def receive_get_room_info(self, data, room):
       # Only executes if user is a participant/subscriber

**Checks:**

* OneToOneChat: User in ``participants``
* GroupChat: User in ``participants``
* Channel: User in ``subscribers``

@can_send_message_to_room
~~~~~~~~~~~~~~~~~~~~~~~~~~

User has permission to send messages.

.. code-block:: python

   @can_send_message_to_room
   async def receive_message_send_event(self, data, room):
       # Only executes if user can send to this room

**Checks:**

* OneToOneChat: User is a participant
* GroupChat: User is participant (unless ``group_locked=True``, then only creator/admins)
* Channel: User is creator, moderator, or has ``can_send_messages`` permission

@can_modify_message
~~~~~~~~~~~~~~~~~~~

User must be the message sender.

.. code-block:: python

   @can_modify_message
   async def receive_message_modify_event(self, data, room):
       # Only executes if user sent the message

@can_add_members_to_room
~~~~~~~~~~~~~~~~~~~~~~~~~

User can invite new members.

.. code-block:: python

   @can_add_members_to_room
   async def receive_add_members_to_room(self, data, room):
       # Only executes if user can add members

**Who can add:**

* GroupChat: Creator, admins, or users with ``can_add_new_participants``
* Channel: Creator, moderators, or users with ``can_add_new_subscribers``

@can_remove_members_from_room
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

User can remove members.

**Who can remove:**

* GroupChat: Creator, admins, or users with ``can_remove_participants``
* Channel: Creator, moderators, or users with ``can_remove_subscribers``

**Restrictions:**

* Cannot remove the creator (creator can only leave voluntarily)

@is_room_admin
~~~~~~~~~~~~~~

User is creator or admin/moderator.

.. code-block:: python

   @is_room_admin
   async def receive_modify_room_event(self, data, room):
       # Only creator/admins/moderators

Object-Level Permissions
------------------------

GroupChat Permissions
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Defined in Meta.permissions
   "can_add_new_participants"
   "can_remove_participants"

**Auto-assigned to:**

* Creator (on creation)
* Admins (on promotion)

**Can be granted individually:**

.. code-block:: javascript

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

   "can_add_new_subscribers"
   "can_remove_subscribers"
   "can_send_messages"

**Auto-assigned to:**

* Creator (all permissions)
* Moderators (all permissions)

**Granting to subscribers:**

.. code-block:: javascript

   // Allow subscriber to post
   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'channel-uuid',
           action: 'add_permission',
           data: {
               users: [user_id],
               permissions: ['can_send_messages']
           }
       }
   }));

Checking Permissions
--------------------

Backend (Django)
~~~~~~~~~~~~~~~~

.. code-block:: python

   from guardian.shortcuts import get_perms

   # Check if user has permission
   user.has_perm('can_add_new_participants', room)

   # Get all permissions for user on object
   perms = get_perms(user, room)

Frontend (Check Before Action)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   // Get room info first
   socket.send(JSON.stringify({
       event_type: 'room.info',
       data: {room_id: 'room-uuid'}
   }));

   // Check user role
   socket.onmessage = (e) => {
       const response = JSON.parse(e.data);
       if (response.eventType === 'roominfo.dispatch') {
           const room = response.data;
           const isAdmin = room.admins.some(a => a.id === currentUserId);
           const isCreator = room.creator.id === currentUserId;
           
           // Show/hide UI based on permissions
           if (isAdmin || isCreator) {
               showAddMembersButton();
           }
       }
   };

Custom Permission Handlers
---------------------------

Override Permission Logic
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/permissions.py
   from realtime_chat_messaging.permissions.handlers import PermissionHandler

   class CustomPermissionHandler(PermissionHandler):
       
       @staticmethod
       def _have_send_message_permission(user, data, default_admin_names={"group": "admins", "channel": "moderators"}):
           is_permitted, room = PermissionHandler._have_send_message_permission(user, data, default_admin_names)
           
           # Additional check: user must have verified email
           if is_permitted and not user.profile.email_verified:
               return False, room
           
           return is_permitted, room

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler"
   }

Custom Permission Decorators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/decorators.py
   from functools import wraps
   from django.core.exceptions import PermissionDenied

   def requires_verified_email(method):
       @wraps(method)
       async def wrapper(self, data, *args, **kwargs):
           if not self.user.profile.email_verified:
               raise PermissionDenied("Email must be verified")
           return await method(self, data, *args, **kwargs)
       return wrapper

   # myapp/consumers.py
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from myapp.decorators import requires_verified_email

   class CustomConsumer(ChatMessagingConsumer):
       
       @requires_verified_email
       async def receive_message_send_event(self, data, room):
           return await super().receive_message_send_event(data, room)

Best Practices
--------------

Principle of Least Privilege
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Grant minimum permissions needed:

.. code-block:: python

   # ❌ Bad: Make everyone admin
   room.admins.add(*all_users)

   # ✅ Good: Grant specific permissions
   assign_perm('can_add_new_participants', trusted_user, room)

Check Permissions Before Actions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   // Frontend validation
   function canAddMembers(room, currentUser) {
       return room.creator.id === currentUser.id || 
              room.admins.some(a => a.id === currentUser.id);
   }

   if (canAddMembers(room, currentUser)) {
       // Show add members UI
   }

Document Custom Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomGroupChat(AbstractGroupChat):
       class Meta(AbstractGroupChat.Meta):
           permissions = AbstractGroupChat.Meta.permissions +  [
               ("can_pin_messages", "Can pin messages"),  # Custom
               ("can_mute_members", "Can mute members"),  # Custom
           ]
            abstract = False # don't forget to turn abstract to false

See Also
--------

* `django-guardian docs <https://django-guardian.readthedocs.io/>`_
* :doc:`room-types` - Room-specific permissions
* :doc:`../customization/permissions` - Advanced customization