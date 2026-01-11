Permissions API Reference
=========================

Complete reference for permission decorators and handlers.

Permission Decorators
---------------------

can_access_room
~~~~~~~~~~~~~~~

Check if user is a member of the room.

.. code-block:: python

   @can_access_room
   async def my_handler(self, data, room):
       # room parameter automatically injected
       pass

**Checks:**

* OneToOneChat: User in ``participants``
* GroupChat: User in ``participants``
* Channel: User in ``subscribers``

**Returns:** ``(is_permitted: bool, room: Room)``

**Errors:** ``4002`` if not permitted

can_send_message_to_room
~~~~~~~~~~~~~~~~~~~~~~~~~

Check if user can send messages to this room.

.. code-block:: python

   @can_send_message_to_room
   async def my_handler(self, data, room):
       pass

**Checks:**

* OneToOneChat: User is participant
* GroupChat: User is participant (unless ``group_locked=True``)
* Channel: User is creator, moderator, or has ``can_send_messages`` permission

**Returns:** ``(is_permitted: bool, room: Room)``

can_modify_message
~~~~~~~~~~~~~~~~~~

Check if user is the message sender.

.. code-block:: python

   @can_modify_message
   async def my_handler(self, data, room):
       pass

**Checks:**

* User is message sender
* All messages in same room (for bulk operations)

**Returns:** ``(is_permitted: bool, room: Room)``

can_access_message
~~~~~~~~~~~~~~~~~~

Check if user can access the message.

.. code-block:: python

   @can_access_message
   async def my_handler(self, data):
       pass

**Checks:**

* User is member of message's room
* Message is not soft-deleted

**Returns:** ``is_permitted: bool``

can_add_members_to_room
~~~~~~~~~~~~~~~~~~~~~~~

Check if user can add members.

.. code-block:: python

   @can_add_members_to_room
   async def my_handler(self, data, room):
       pass

**Checks:**

* GroupChat: Creator, admin, or has ``can_add_new_participants``
* Channel: Creator, moderator, or has ``can_add_new_subscribers``

**Returns:** ``(is_permitted: bool, room: Room)``

can_remove_members_from_room
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check if user can remove members.

.. code-block:: python

   @can_remove_members_from_room
   async def my_handler(self, data, room):
       pass

**Checks:**

* GroupChat: Creator, admin, or has ``can_remove_participants``
* Channel: Creator, moderator, or has ``can_remove_subscribers``
* Cannot remove creator

**Returns:** ``(is_permitted: bool, room: Room)``

is_room_admin
~~~~~~~~~~~~~

Check if user is room admin/moderator.

.. code-block:: python

   @is_room_admin
   async def my_handler(self, data, room):
       pass

**Checks:**

* GroupChat: Creator or in ``admins``
* Channel: Creator or in ``moderators``

**Returns:** ``(is_permitted: bool, room: Room)``

Permission Handler
------------------

PermissionHandler
~~~~~~~~~~~~~~~~~

Base class containing permission logic.

**Methods:**

.. code-block:: python

   class PermissionHandler:
       @staticmethod
       @database_sync_to_async
       def _have_room_permission(user, room_id):
           """Check if user is room member."""
           pass
       
       @staticmethod
       @database_sync_to_async
       def _have_message_permission(user, message_id):
           """Check if user can access message."""
           pass
       
       @staticmethod
       @database_sync_to_async
       def _is_message_sender(user, message_id):
           """Check if user sent the message."""
           pass
       
       @staticmethod
       @database_sync_to_async
       def _have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase, default_admin_names):
           """Check if user can add/remove members."""
           pass
       
       @staticmethod
       @database_sync_to_async
       def _have_send_message_permission(user, data, default_admin_names):
           """Check if user can send messages."""
           pass
       
       @staticmethod
       @database_sync_to_async
       def _have_admin_privileges(user, room_id, default_admin_names):
           """Check if user is admin/moderator."""
           pass

**Customization:**

Override ``PERMISSION_HANDLER_CLASS`` in settings.

**Default Admin Names:**

.. code-block:: python

   default_admin_names = {
       "group": "admins",
       "channel": "moderators"
   }

If you renamed these fields in custom models, pass custom names.

Object-Level Permissions
------------------------

GroupChat Permissions
~~~~~~~~~~~~~~~~~~~~~

Defined in model Meta:

* ``can_add_new_participants``
* ``can_remove_participants``

**Auto-granted to:**

* Creator (on creation)
* Admins (on promotion)

Channel Permissions
~~~~~~~~~~~~~~~~~~~

Defined in model Meta:

* ``can_add_new_subscribers``
* ``can_remove_subscribers``
* ``can_send_messages``

**Auto-granted to:**

* Creator (on creation)
* Moderators (on promotion)

Using django-guardian
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from guardian.shortcuts import get_perms, assign_perm, remove_perm

   # Check permission
   user.has_perm('can_add_new_participants', room)

   # Get all permissions
   perms = get_perms(user, room)

   # Grant permission
   assign_perm('can_add_new_participants', user, room)

   # Revoke permission
   remove_perm('can_add_new_participants', user, room)

Error Codes
-----------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Code
     - Meaning
   * - ``4001``
     - Authentication failed
   * - ``4002``
     - Permission denied
   * - ``4003``
     - Validation error
   * - ``4004``
     - Resource not found
   * - ``4005``
     - Integrity error
   * - ``4006``
     - Internal server error

See Also
--------

* :doc:`../user-guide/permissions` - Permission guide
* :doc:`../customization/permissions` - Custom permissions
* :doc:`settings` - Permission handler configuration