Models API Reference
====================

Complete reference for all models in the package.

Room Models
-----------

Room (Base)
~~~~~~~~~~~

.. code-block:: python

   class Room(PolymorphicModel):
       id = UUIDField(primary_key=True, default=uuid.uuid4)
       last_message = ForeignKey(Message, null=True, blank=True, on_delete=SET_NULL)
       preferences = JSONField(default=dict)
       created_at = DateTimeField(auto_now_add=True)
       updated_at = DateTimeField(auto_now=True)

**Fields:**

* ``id`` - UUID primary key
* ``last_message`` - Reference to most recent message
* ``preferences`` - JSON field for custom settings (theme, notifications, etc.)
* ``created_at`` - When room was created
* ``updated_at`` - Last modification time

**Swappable:** ``REALTIME_CHAT_MESSAGING_ROOM_MODEL``

OneToOneChat
~~~~~~~~~~~~

.. code-block:: python

   class OneToOneChat(Room):
       participants = ManyToManyField(User, related_name="chats")

**Fields:**

* Inherits all Room fields
* ``participants`` - Always exactly 2 users

**Constraints:**

* Enforced 2 participants via signal
* Cannot create duplicate chats between same users

**Swappable:** ``REALTIME_CHAT_MESSAGING_ONETOONECHAT_MODEL``

GroupChat
~~~~~~~~~

.. code-block:: python

   class GroupChat(Room):
       name = CharField(max_length=64)
       description = TextField(null=True, blank=True)
       creator = ForeignKey(User, on_delete=CASCADE, related_name="groups_owned")
       participants = ManyToManyField(User, related_name="groups_in")
       admins = ManyToManyField(User, related_name="groups_moderated")
       max_participants = PositiveBigIntegerField(default=100)
       avatar = URLField(null=True, blank=True)
       join_approval_required = BooleanField(default=False)
       group_locked = BooleanField(default=False)

**Permissions:**

* ``can_add_new_participants``
* ``can_remove_participants``

**Swappable:** ``REALTIME_CHAT_MESSAGING_GROUPCHAT_MODEL``

Channel
~~~~~~~

.. code-block:: python

   class Channel(Room):
       name = CharField(max_length=64)
       description = TextField(null=True, blank=True)
       creator = ForeignKey(User, on_delete=CASCADE, related_name="channels_owned")
       subscribers = ManyToManyField(User, related_name="channels_subscribed")
       moderators = ManyToManyField(User, related_name="channels_moderated")
       is_public = BooleanField(default=False)
       avatar = URLField(null=True, blank=True)
       max_subscribers = PositiveBigIntegerField(default=300)

**Permissions:**

* ``can_add_new_subscribers``
* ``can_remove_subscribers``
* ``can_send_messages``

**Swappable:** ``REALTIME_CHAT_MESSAGING_CHANNEL_MODEL``

Message Models
--------------

Message
~~~~~~~

.. code-block:: python

   class Message(models.Model):
       id = UUIDField(primary_key=True, default=uuid.uuid4)
       room = ForeignKey(Room, on_delete=CASCADE, related_name="room_messages")
       sender = ForeignKey(User, on_delete=CASCADE, related_name="user_messages")
       content = TextField()
       created_at = DateTimeField(auto_now_add=True)
       updated_at = DateTimeField(auto_now=True)
       
       parent_message = ForeignKey('self', null=True, blank=True, on_delete=SET_NULL, related_name="replies")
       is_forwarded = BooleanField(default=False)
       forwarded_from = ForeignKey('self', null=True, blank=True, on_delete=SET_NULL, related_name="forwarded")
       is_edited = BooleanField(default=False)
       is_deleted = BooleanField(default=False)
       delivered_to = ManyToManyField(User, related_name="messages_received")

**Indexes:**

* ``content``
* ``content, sender``

**Constraints:**

* Forwarded messages cannot be replies

**Swappable:** ``REALTIME_CHAT_MESSAGING_MESSAGE_MODEL``

MessageMediaAsset
~~~~~~~~~~~~~~~~~

.. code-block:: python

   class MessageMediaAsset(models.Model):
       id = UUIDField(primary_key=True, default=uuid.uuid4)
       message = ForeignKey(Message, on_delete=CASCADE, related_name="attachments")
       media_url = CharField()
       media_type = CharField(max_length=64, choices=MEDIATYPE_CHOICES)
       file_size = PositiveBigIntegerField(default=0)
       mime_type = CharField(default="image/jpeg")
       caption = CharField(blank=True, null=True)
       metadata = JSONField(default=dict)

**Constraints:**

* ``mime_type`` must be in ALLOWED_MIME_TYPES

**Swappable:** ``REALTIME_CHAT_MESSAGING_MESSAGEMEDIAASSET_MODEL``

Engagement Models
-----------------

ReadReceipt
~~~~~~~~~~~

.. code-block:: python

   class ReadReceipt(models.Model):
       id = UUIDField(primary_key=True, default=uuid.uuid4)
       message = ForeignKey(Message, on_delete=CASCADE, related_name="read_receipts")
       reader = ForeignKey(User, on_delete=CASCADE)
       read_at = DateTimeField(auto_now_add=True)

**Constraints:**

* Unique together: ``message, reader``

**Swappable:** ``REALTIME_CHAT_MESSAGING_READRECEIPT_MODEL``

Reaction
~~~~~~~~

.. code-block:: python

   class Reaction(models.Model):
       id = UUIDField(primary_key=True, default=uuid.uuid4)
       message = ForeignKey(Message, on_delete=CASCADE, related_name="reactions")
       user = ForeignKey(User, on_delete=CASCADE, related_name="reactions")
       reaction_content = TextField(max_length=128)
       created_at = DateTimeField(auto_now_add=True)

**Constraints:**

* Unique together: ``message, user``

**Swappable:** ``REALTIME_CHAT_MESSAGING_REACTION_MODEL``

ChatNotification
~~~~~~~~~~~~~~~~

.. code-block:: python

   class ChatNotification(models.Model):
       id = UUIDField(primary_key=True, default=uuid.uuid4)
       recipients = ManyToManyField(User, related_name='unread_messages')
       message = ForeignKey(Message, on_delete=CASCADE, related_name='notifications')
       notification_type = CharField(max_length=64, choices=NOTIFICATION_TYPE, default='NEW_MESSAGE')

**Notification Types:**

* ``REACTION``
* ``NEW_MESSAGE``
* ``REPLY``

**Swappable:** ``REALTIME_CHAT_MESSAGING_CHATNOTIFICATION_MODEL``

Constants
---------

MEDIATYPE_CHOICES
~~~~~~~~~~~~~~~~~

.. code-block:: python

   [
       ("image", "Image"),
       ("video", "Video"),
       ("audio", "Audio"),
       ("file", "File"),
   ]

ALLOWED_MIME_TYPES
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   [
       # Images
       "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/heic",
       
       # Videos
       "video/mp4", "video/quicktime", "video/webm", "video/ogg",
       
       # Audio
       "audio/mpeg", "audio/mp4", "audio/aac", "audio/ogg", "audio/wav",
       
       # Documents
       "application/pdf", "application/msword", "text/plain", "text/csv"
   ]

NOTIFICATION_TYPE
~~~~~~~~~~~~~~~~~

.. code-block:: python

   (
       ('REACTION', 'Reaction'),
       ('NEW_MESSAGE', 'New Message'),
       ('REPLY', 'Reply')
   )

See Also
--------

* :doc:`../customization/models` - Extending models
* :doc:`serializers` - Serializer reference
* :doc:`settings` - Model configuration