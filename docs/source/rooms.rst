Rooms
=====

A **room** is the container for a conversation. There are three concrete room
types, all inheriting from the polymorphic ``Room`` base model. Every room has a
UUID primary key, ``created_at``, ``updated_at``, a ``last_message`` foreign key,
and a one-to-one ``property`` (``RoomProperty``) for storing preferences.

Room Types
----------

OneToOneChat
~~~~~~~~~~~~

A private conversation between **exactly two users**. Enforced at the database
level by signals — adding more or fewer than two participants raises a
``ValidationError``.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Description
   * - ``participants``
     - M2M to ``User``. Always exactly 2 users.

- Participants cannot leave a ``OneToOneChat`` (``room.leave`` raises a ``ValidationError``). 
  If a participant's user account is deleted, a pre_delete signal on the 
  ``User`` model handles cleanup by deleting any ``OneToOneChat`` the user belongs to. 
  This is a known temporary fix for the current release — Django's M2M ``post_remove`` 
  signal does not fire when ``CASCADE`` deletion propagates through the through table, 
  so direct room cleanup is handled at the User pre-delete stage instead. 
  If you are using a custom ``OneToOneChat`` model, this cleanup is delegated to you.
- Only participants can send messages.
- Duplicate chats between the same two users are prevented by signals.

GroupChat
~~~~~~~~~

A multi-user chat room with admin controls, a member cap, and optional message
locking.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Description
   * - ``name``
     - Display name (max 64 chars). Required.
   * - ``description``
     - Optional text description.
   * - ``creator``
     - The user who created the group. Always an admin. Cannot be removed by other admins.
   * - ``participants``
     - M2M to ``User``. All group members.
   * - ``admins``
     - M2M to ``User``. Subset of participants with management permissions.
   * - ``max_participants``
     - Enforced by signals. Default 100.
   * - ``avatar``
     - Optional URL to a group image.
   * - ``join_approval_required``
     - Boolean flag. See note below.
   * - ``group_locked``
     - When ``True``, only admins and the creator can send messages.

**Joining a GroupChat**: The default behaviour raises a ``ValidationError`` with
the message "Ask an admin to add you to the group". Groups are joined by having
an admin call ``room.add_members``. The ``join_approval_required`` flag exists to
support custom approval flows — set it to ``True`` when creating the room and
override ``join_room`` in a custom ``EventHandler`` to implement your approval
logic. See :doc:`custom_handlers` for an example.

**Locking a group**: Set ``group_locked: true`` via ``room.modify`` with
``action: "update"`` to restrict sending to admins only. This can also be toggled
back off with ``group_locked: false``.

**Automatic deletion**: When the last participant leaves or is removed, signals
delete the room automatically.

Channel
~~~~~~~

A broadcast room where only moderators (and users with explicit permission) can
send messages by default. Suited for announcements, news feeds, or one-to-many
communication.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Description
   * - ``name``
     - Display name (max 64 chars). Required.
   * - ``description``
     - Optional text description.
   * - ``creator``
     - The user who created the channel. Always a moderator.
   * - ``subscribers``
     - M2M to ``User``. All channel members.
   * - ``moderators``
     - M2M to ``User``. Can send messages and manage subscribers.
   * - ``is_public``
     - When ``True``, users can join via ``room.join`` without being added by a moderator.
   * - ``avatar``
     - Optional URL to a channel image.
   * - ``max_subscribers``
     - Enforced by signals. Default 300.

**Sending to a Channel**: Only the creator, moderators, and users with the
``can_send_messages`` object-level permission can post. Grant this permission via
``room.modify`` with ``action: "add_permission"`` and ``permissions:
["can_send_messages"]``.

**Joining a Channel**: If ``is_public`` is ``True``, any authenticated user can
join using the ``room.join`` event. Private channels require a moderator to add
them via ``room.add_members``.

RoomProperty
------------

Every room is automatically created with a ``RoomProperty`` instance (via
``pre_save`` signal) that stores a freeform ``preferences`` JSON field. Use this
to store any room-level settings your application needs without modifying the room
model directly.

.. code-block:: python

   # Example preferences dict
   {
       "notifications": True,
       "theme": "dark",
       "pinned_message_ids": ["uuid1", "uuid2"]
   }

Access and update preferences via the ``room.modify`` event with ``action:
"update"`` and a ``property`` key in the data. See :doc:`websocket_events` for
the full payload structure.

Permissions Summary
-------------------

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Permission
     - Room type
     - Granted to
   * - ``can_add_new_participants``
     - GroupChat
     - Creator, admins
   * - ``can_remove_participants``
     - GroupChat
     - Creator, admins
   * - ``can_add_new_subscribers``
     - Channel
     - Creator, moderators
   * - ``can_remove_subscribers``
     - Channel
     - Creator, moderators
   * - ``can_send_messages``
     - Channel
     - Creator, moderators (and explicit grants)

Permissions are granted and revoked automatically via Django signals when users
are added to or removed from the ``admins`` or ``moderators`` M2M fields. They
can also be managed granularly via ``room.modify``. All permissions use
``django-guardian`` for object-level enforcement.

Creating Rooms
--------------

Rooms are created via the WebSocket ``room.create`` event. See
:doc:`websocket_events` for complete payload documentation. Key points:

- The creator is automatically added as a participant/subscriber and
  admin/moderator by signals — you do not need to include them in the
  ``participants`` or ``subscribers`` list.
- For ``OneToOneChat``, the participants list should contain **only the other
  user's ID**. The creator is added automatically, making the total count
  exactly 2.
- Room ``property`` and ``preferences`` are optional at creation time. Defaults
  are applied if not provided.
