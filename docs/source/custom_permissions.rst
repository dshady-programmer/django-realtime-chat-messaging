Custom Permissions
==================

The permission system has two layers: async ``PermissionHandler`` (the public
interface) and synchronous ``PermissionHelperMixin`` (the DB logic). Override
either to customise authorisation.

The Simplest Override
----------------------

Subclass ``PermissionHandler`` and override the async method you want to change:

.. code-block:: python

   # myapp/permissions.py
   from realtime_chat_messaging.permissions.handlers import PermissionHandler


   class CustomPermissionHandler(PermissionHandler):

       async def have_send_message_permission(self, user, data):
           """
           Custom send permission: staff users can send to any room.
           Returns: (is_permitted: bool, room: Room)
           """
           if user.is_staff:
               from realtime_chat_messaging.utils.loader import get_model
               from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async
               from django.shortcuts import get_object_or_404

               @sqlite_safe_db_sync_to_async
               def get_room():
                   Room = get_model("Room")
                   room_id = data.get("room_id")
                   return True, get_object_or_404(Room, pk=room_id)

               return await get_room()

           # Fall back to default for non-staff users
           return await super().have_send_message_permission(user, data)

Register it:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler",
   }

Overriding the Sync Helper Layer
----------------------------------

For more involved changes, override the synchronous ``_have_*`` methods in
``PermissionHelperMixin`` and use ``sqlite_safe_db_sync_to_async`` to wrap them:

.. code-block:: python

   from realtime_chat_messaging.permissions.handlers import PermissionHandler
   from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async
   from realtime_chat_messaging.utils.loader import get_model


   class CustomPermissionHandler(PermissionHandler):

       @sqlite_safe_db_sync_to_async
       def have_room_permission(self, user, room_id):
           """
           Allow access to archived rooms for their members.
           """
           Room = get_model("Room")
           from django.shortcuts import get_object_or_404
           room = get_object_or_404(Room, pk=room_id)

           # Custom: check archived rooms table too
           is_member = self._is_member(user, room)
           return is_member, room

       @staticmethod
       def _is_member(user, room):
           if hasattr(room, "participants"):
               return room.participants.filter(pk=user.pk).exists()
           elif hasattr(room, "subscribers"):
               return room.subscribers.filter(pk=user.pk).exists()
           return False

Method Return Types
--------------------

All permission handler methods must return the same types as the defaults:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Method
     - Return type
   * - ``have_room_permission(user, room_id)``
     - ``(bool, Room)``
   * - ``have_message_permission(user, message_id)``
     - ``bool``
   * - ``is_message_sender(user, message_id)``
     - ``(bool, Room)``
   * - ``have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase)``
     - ``(bool, Room)``
   * - ``have_send_message_permission(user, data)``
     - ``(bool, Room)``
   * - ``have_admin_privileges(user, room_id, action)``
     - ``(bool, Room)``

The ``default_admin_names`` Parameter
----------------------------------------

Several helper methods accept a ``default_admin_names`` keyword:

.. code-block:: python

   default_admin_names = {"group": "admins", "channel": "moderators"}

This maps the GroupChat and Channel admin M2M field names. If you created a
custom GroupChat model that renamed ``admins`` to ``managers``, override the
helper and pass the updated mapping:

.. code-block:: python

   class CustomPermissionHandler(PermissionHandler):

       @sqlite_safe_db_sync_to_async
       def have_room_permissions_to_add_or_remove_members(self, user, room_id, perm_phrase):
           return self._have_room_permissions_to_add_or_remove_members(
               user,
               room_id,
               perm_phrase,
               default_admin_names={"group": "managers", "channel": "moderators"},
           )
