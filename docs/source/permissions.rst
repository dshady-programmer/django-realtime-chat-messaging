Permissions
===========

The package uses **two layers** of permission checking: decorator-level guards on
consumer methods, and ``django-guardian`` object-level permissions on room
instances.

Permission Decorators
---------------------

Every consumer event handler that requires authorisation is wrapped with a
decorator from ``realtime_chat_messaging.permissions.decorators``. Each decorator
calls the configured ``PERMISSION_HANDLER_CLASS`` and injects the resolved
``room`` object into the handler method.

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Decorator
     - What it checks
   * - ``@can_access_room``
     - User is a member of the room (participant or subscriber)
   * - ``@can_send_message_to_room``
     - User can send to the room (see rules below). Injects ``room``.
   * - ``@can_access_message``
     - User is a member of the room containing the message(s)
   * - ``@can_modify_message``
     - User is the sender of the message(s). All messages must be in the same room. Injects ``room``.
   * - ``@can_add_members_to_room``
     - User has ``can_add_new_participants`` (GroupChat) or ``can_add_new_subscribers`` (Channel) permission
   * - ``@can_remove_members_from_room``
     - User has ``can_remove_participants`` (GroupChat) or ``can_remove_subscribers`` (Channel) permission
   * - ``@is_room_admin``
     - For ``delete``: user is room creator (for GroupChats and Channels), or a member of the room for OneToOneChats. 
       For other actions: user is admin/moderator.

Send Message Permission Rules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The rules vary by room type:

- **OneToOneChat** — user must be a participant.
- **GroupChat (unlocked)** — user must be a participant.
- **GroupChat (locked, i.e. group_locked=True)** — user must be a participant AND
  (be the creator OR be an admin).
- **Channel** — user must be a subscriber AND (be the creator OR be a moderator
  OR have the ``can_send_messages`` object-level permission).

Note that even the creator of a group or channel must be a member (participant /
subscriber) to send messages, add/remove members, delete the room etc. 
Leaving a room as a creator of that room from the members list
removes your privileges as a creator.

Object-Level Permissions
------------------------

``django-guardian`` manages per-room permissions. Permissions are assigned and
revoked automatically via Django signals — you rarely need to manage them
manually.

**GroupChat permissions**:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Permission codename
     - Automatically granted to
   * - ``can_add_new_participants``
     - Creator on room creation; any user added to ``admins``
   * - ``can_remove_participants``
     - Creator on room creation; any user added to ``admins``

**Channel permissions**:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Permission codename
     - Automatically granted to
   * - ``can_add_new_subscribers``
     - Creator on room creation; any user added to ``moderators``
   * - ``can_remove_subscribers``
     - Creator on room creation; any user added to ``moderators``
   * - ``can_send_messages``
     - Creator on room creation; any user added to ``moderators``

Managing Permissions via WebSocket
------------------------------------

Grant or revoke object-level permissions for specific users via ``room.modify``:

**Grant**::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_permission",
       "data": {
         "users": [3, 7],
         "permission": ["can_send_messages"]
       }
     }
   }

**Revoke**::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "remove_permission",
       "data": {
         "users": [3],
         "permission": ["can_send_messages"]
       }
     }
   }

Valid permissions for GroupChat: ``can_add_new_participants``,
``can_remove_participants``.

Valid permissions for Channel: ``can_add_new_subscribers``,
``can_remove_subscribers``, ``can_send_messages``.

The room creator can never have their permissions removed by another admin —
``room.creator.id`` is silently excluded from any permission removal operation.

Managing Admins and Moderators
--------------------------------

**Add admin to GroupChat**::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_admin",
       "data": {
         "users": [5, 6]
       }
     }
   }

**Remove admin from GroupChat**::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "remove_admin",
       "data": {
         "users": [5]
       }
     }
   }

**Add moderator to Channel**::

   {
     "event_type": "room.modify",
     "data": {
       "room_id": "<uuid>",
       "action": "add_moderator",
       "data": {
         "users": [8]
       }
     }
   }

When a user is added to ``admins`` or ``moderators`` the signal
``add_permissions_to_admin_and_moderators`` automatically grants the appropriate
permissions. When they are removed, all permissions are revoked.

Only users who are already room members can be made admins or moderators. Users
not in the member list are silently skipped.

Customising Permissions
-----------------------

To replace the entire permission logic, implement a custom ``PermissionHandler``
and configure it in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.MyPermissionHandler"
   }

Your class must expose the same async interface:

.. code-block:: python

   from realtime_chat_messaging.permissions.handlers import PermissionHandler

   class MyPermissionHandler(PermissionHandler):

       async def have_send_message_permission(self, user, data):
           # Custom logic — return (is_permitted: bool, room: Room)
           ...

To override only specific checks, subclass ``PermissionHandler`` and override
the relevant ``async`` method. Each method must return ``(bool, Room)`` except
``have_message_permission`` which returns ``bool`` only.

For finer-grained customisation, subclass ``PermissionHelperMixin`` (the
synchronous layer) and override the ``_have_*`` methods. Wrap your DB calls
with ``sqlite_safe_db_sync_to_async``. See :doc:`custom_permissions` for full
examples.

The ``default_admin_names`` Parameter
---------------------------------------

Several permission helper methods accept a ``default_admin_names`` keyword
argument:

.. code-block:: python

   default_admin_names = {"group": "admins", "channel": "moderators"}

This maps to the M2M field names used for admins (GroupChat) and moderators
(Channel). If you create a custom GroupChat or Channel model that **renames**
these fields (e.g. ``admins`` → ``managers``), you must pass the updated mapping
when calling these methods or override the helpers to use your field names.
