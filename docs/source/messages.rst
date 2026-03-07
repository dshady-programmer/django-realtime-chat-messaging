Messages
========

The ``Message`` model is the core data structure of the package. Every message
belongs to a room, has a sender, and supports replies, forwarding, reactions, read
receipts, delivery tracking, and media attachments.

Message Fields
--------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Description
   * - ``id``
     - UUID primary key.
   * - ``room``
     - Foreign key to ``Room``.
   * - ``sender``
     - Foreign key to ``User``.
   * - ``content``
     - Message text. HTML-sanitised on creation (XSS protection via ``bleach``).
   * - ``is_deleted``
     - Soft-delete flag. Only meaningful when ``MESSAGE_SOFT_DELETE`` is ``True``.
   * - ``is_edited``
     - Set to ``True`` automatically when content is updated.
   * - ``is_forwarded``
     - ``True`` when this message was forwarded from another message.
   * - ``forwarded_from``
     - FK to the original message (null unless forwarded).
   * - ``parent_message``
     - FK to another message for threaded replies (null if top-level).
   * - ``delivered_to``
     - M2M to ``User``. Updated when recipients send ``message.acknowledged``.
   * - ``created_at``
     - Auto-set on creation.
   * - ``updated_at``
     - Auto-set on every save.

Constraint: a message **cannot** be both a forward and a reply. The database
enforces this with a ``CheckConstraint``.

Sending Messages
----------------

Standard message::

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<room_uuid>",
       "content": "Hello everyone 👋"
     }
   }

Reply (threaded)::

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<room_uuid>",
       "content": "Good point!",
       "extra_fields": {
         "parent_message_id": "<message_uuid>"
       }
     }
   }

Forward::

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<target_room_uuid>",
       "content": "",
       "extra_fields": {
         "forwarded_from_id": "<original_message_uuid>"
       }
     }
   }

With media attachments::

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<room_uuid>",
       "content": "",
       "extra_fields": {
         "media": [
           {
             "media_url": "https://cdn.example.com/photo.jpg",
             "media_type": "image",
             "file_size": 204800,
             "mime_type": "image/jpeg",
             "metadata": {"width": 1080, "height": 1920}
           }
         ]
       }
     }
   }

.. note::

   When ``extra_fields`` is provided, its keys must match fields on your
   ``Message`` model (or custom model). The ``MessageSerializer`` validates them.
   Do not pass ``sender``, ``room``, ``forwarded_from``, or ``parent_message`` 
   directly — use the dedicated ``_id`` fields (for example: ``sender_id``, ``room_id``, ``parent_message_id``, 
   ``forwarded_from_id``).

Content Sanitisation
--------------------

All message content is sanitised with ``bleach`` before being saved. The
following HTML tags are allowed: ``b``, ``i``, ``strong``, ``em``, ``a``,
``span``, ``p``, ``ul``, ``ol``, ``li``, ``br``. All other tags are stripped.
Allowed attributes: ``href``, ``title``, ``target`` on links; ``class`` and
``id`` on all elements. Everything else is stripped at the attribute level.

This happens in ``MessageSerializerMixin.validate_content()``. If you provide a
custom ``MessageSerializer``, ensure you preserve this validation.

Media Attachments
-----------------

Media is **not stored by the package**. You upload files to your own CDN or
storage (S3, Cloudflare R2, etc.) and pass the resulting URL in the ``media``
array of ``extra_fields``. The package creates ``MessageMediaAsset`` records
pointing to those URLs. However, you can override the ``create_message`` method
on the ``EventHandler`` class to add custom functionalities.

Supported ``media_type`` values: ``image``, ``video``, ``audio``, ``file``.

Supported MIME types (enforced by a database constraint):

- **Images**: ``image/jpeg``, ``image/png``, ``image/gif``, ``image/webp``,
  ``image/bmp``, ``image/heic``
- **Audio**: ``audio/mpeg``, ``audio/mp4``, ``audio/aac``, ``audio/ogg``,
  ``audio/wav``, ``audio/opus``
- **Video**: ``video/mp4``, ``video/quicktime``, ``video/webm``, ``video/ogg``,
  ``video/x-msvideo``, ``video/x-matroska``
- **Documents**: ``application/pdf``, ``application/msword``, ``.docx``,
  ``application/vnd.ms-excel``, ``.xlsx``, ``application/vnd.ms-powerpoint``,
  ``.pptx``, ``text/plain``, ``text/csv``

The ``metadata`` field is a freeform JSON object. Recommended structures:

.. code-block:: python

   # Image
   {"width": 1080, "height": 1920, "orientation": "portrait"}

   # Video / video note
   {
     "duration": 12.5,
     "resolution": "1080x1920",
     "fps": 30,
     "orientation": "portrait",
     "audio_codec": "aac",
     "video_codec": "h264"
   }

   # Audio / voice note
   {"duration": 2.8, "waveform": [0.2, 0.5, 0.1], "bitrate": 96000}

Editing and Deleting Messages
------------------------------

Only the message sender can edit or delete their messages (enforced by the
``@can_modify_message`` decorator).

**Edit**::

   {
     "event_type": "message.modify",
     "data": {
       "action": "update",
       "message_id": "<message_uuid>",
       "extra_fields": {
         "content": "Corrected message text"
       }
     }
   }

Only ``content`` can be updated by default, ``is_edited`` flag is set to ``True``. 
Deleted messages cannot be edited.

.. note::

  if the ``Message`` model is extended with custom fields, they will be updated, 
  it's the user's responsibility to restrict updates to allowed fields. 
  


**Delete (single or bulk)**::

   {
     "event_type": "message.modify",
     "data": {
       "action": "delete",
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

``message_id`` accepts a single ID or a list. All messages in a bulk operation
must come from the **same room**. When deleting, any associated
``ChatNotification`` records are also deleted.

Soft Delete vs Hard Delete
~~~~~~~~~~~~~~~~~~~~~~~~~~

Controlled by the ``MESSAGE_SOFT_DELETE`` setting (default ``False``):

- ``False`` (default): messages are permanently deleted with
  ``Message.objects.delete()``.
- ``True``: the ``is_deleted`` flag is set to ``True`` and the row is kept.
  Soft-deleted messages are **excluded** from ``room.messages`` queries. They
  remain in the database for audit, recovery, or analytics.

Reactions
---------

Each user can have **one reaction per message**. Adding a new reaction to a
message you have already reacted to automatically removes the old one (via
``pre_save`` signal).

**Add reaction**::

   {
     "event_type": "message.react",
     "data": {
       "type": "add",
       "message_id": "<uuid>",
       "reaction_content": "👍"
     }
   }

**Remove reaction**::

   {
     "event_type": "message.react",
     "data": {
       "type": "remove",
       "message_id": "<uuid>",
       "reaction_content": "👍"
     }
   }

The server broadcasts a ``reaction.dispatch`` event to all room participants with
the updated message.

Read Receipts
-------------

Mark one or more messages as read::

   {
     "event_type": "message.read",
     "data": {
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

A ``readreceipt.dispatch`` event is broadcast to all room participants. The
sender's own messages are excluded (you cannot create a read receipt for your own
message). Bulk operations use ``bulk_create`` for efficiency.

Each user can only have one read receipt per message (unique constraint).

Delivery Acknowledgement
------------------------

When a client receives a message and confirms delivery::

   {
     "event_type": "message.acknowledged",
     "data": {
       "message_id": ["<uuid1>", "<uuid2>"]
     }
   }

This does two things:

1. Adds the current user to the ``delivered_to`` M2M field on each message.
2. Removes the user from the ``recipients`` list of any associated
   ``ChatNotification`` (if ``ENABLE_NOTIFICATION`` is ``True``). When
   ``recipients`` becomes empty the notification is auto-deleted by signals.

The ``messagedelivered.dispatch`` event is sent **only to the original sender**
of each message (not broadcast to the room), so the sender can update their sent
message delivery indicators.

Retrieving Messages
-------------------

Fetch room messages with optional pagination::

   {
     "event_type": "room.messages",
     "data": {
       "room_id": "<uuid>",
       "paginate": {
         "page": 1,
         "size": 50
       }
     }
   }

Omit ``paginate`` to retrieve all messages (not recommended for large rooms).
Messages are ordered newest-first. The response is sent only to the requesting
user (not broadcast to the room).

**Paginated response structure**:

.. code-block:: javascript

   {
     "eventType": "roommessages.dispatch",
     "data": {
       "has_next": true,
       "has_previous": false,
       "next_page_number": 2,
       "prev_page_number": null,
       "page": 1,
       "size": 50,
       "data": {
         "room_id": "<uuid>",
         "messages": [...]
       }
     }
   }

Typing Indicators
-----------------

Notify room participants that a user is typing::

   {
     "event_type": "message.typing",
     "data": {
       "room_id": "<uuid>"
     }
   }

The server broadcasts ``messagetyping.dispatch`` with ``{"username": "alice"}``
to all room participants. Typing events are **not persisted**.

Message Serializer Output
--------------------------

The full serialized message structure returned by the default ``MessageSerializer``:

.. code-block:: javascript

   {
     "id": "550e8400-e29b-41d4-a716-446655440000",
     "room": {"id": "<room_uuid>"},
     "sender": {
       "id": 1,
       "username": "alice",
       "email": "alice@example.com",
       "first_name": "Alice",
       "last_name": "Smith"
     },
     "content": "Hello!",
     "is_deleted": false,
     "is_edited": false,
     "is_forwarded": false,
     "forwarded_from": null,
     "parent_message": null,
     "delivered_to": ["alice", "bob"],
     "read_receipts": [
       {"reader": {...}, "read_at": "2026-01-01T12:00:00Z"}
     ],
     "reactions": [
       {"user": {...}, "reaction_content": "👍", "created_at": "..."}
     ],
     "attachments": [],
     "created_at": "2026-01-01T12:00:00Z",
     "updated_at": "2026-01-01T12:00:00Z"
   }
