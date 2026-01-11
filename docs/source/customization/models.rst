Model Customization
===================

Extending and swapping models to add custom fields and behavior.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

All models are swappable like Django's ``AUTH_USER_MODEL``. Inherit from abstract base classes to add custom fields.

Available Models
~~~~~~~~~~~~~~~~

* ``Room`` - Base for all room types
* ``OneToOneChat``, ``GroupChat``, ``Channel`` - Room types
* ``Message`` - All messages
* ``MessageMediaAsset`` - Media attachments
* ``ReadReceipt`` - Read tracking
* ``Reaction`` - Emoji reactions
* ``ChatNotification`` - Unread tracking

Extending Message Model
-----------------------

Most Common Customization
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from django.conf import settings
   from realtime_chat_messaging.model_mixins import AbstractMessage
   from django.db import models
   from django.db.models import Q

   class CustomMessage(AbstractMessage):
       priority = models.CharField(
           max_length=10,
           choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High')],
           default='normal'
       )
       is_pinned = models.BooleanField(default=False)
       mentioned_users = models.ManyToManyField(
           settings.AUTH_USER_MODEL,  # Use settings reference
           related_name='mentioned_in_messages',
           blank=True
       )
       
       class Meta(AbstractMessage.Meta):
           abstract = False
           # Inherit base constraints and indexes
           # Add your own constraints if needed
           constraints = AbstractMessage.Meta.constraints + [
               models.CheckConstraint(
                   condition=Q(priority__in=['low', 'normal', 'high']),
                   name='valid_priority'
               )
           ]

.. danger::
   **CRITICAL: Always inherit from AbstractMessage.Meta!**
   
   This ensures you get:
   
   * Required database indexes (``content``, ``content + sender``)
   * Base constraints
   * Abstract = False (overrides the abstract base)
   
   Failing to inherit the Meta class will break database performance and may cause migrations to fail.

**Register in settings:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.models.CustomMessage"
       }
   }

**Run migrations:**

.. code-block:: bash

   python manage.py makemigrations
   python manage.py migrate

**Update serializer:**

.. code-block:: python

   # myapp/serializers.py
   from realtime_chat_messaging.serializers import MessageSerializer as BaseMessageSerializer

   class CustomMessageSerializer(BaseMessageSerializer):
       priority = serializers.CharField(read_only=True)
       is_pinned = serializers.BooleanField(read_only=True)
       mentioned_users = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
       
       class Meta(BaseMessageSerializer.Meta):
           model = CustomMessage
           fields = BaseMessageSerializer.Meta.fields + ['priority', 'is_pinned', 'mentioned_users']

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.models.CustomMessage"
       },
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer"
       }
   }

Extending Room Models
---------------------

.. warning::
   **Extending Room requires extending ALL room types** because OneToOneChat, GroupChat, and Channel inherit from Room.

Complete Example
~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from realtime_chat_messaging.model_mixins import (
       AbstractRoom, AbstractOneToOneChat, 
       AbstractGroupChat, AbstractChannel
   )
   from polymorphic.models import PolymorphicModel

   class CustomRoom(PolymorphicModel, AbstractRoom):
       is_archived = models.BooleanField(default=False)
       archived_at = models.DateTimeField(null=True, blank=True)
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_ROOM_MODEL'

   class CustomOneToOneChat(CustomRoom, AbstractOneToOneChat):
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_ONETOONECHAT_MODEL'

   class CustomGroupChat(CustomRoom, AbstractGroupChat):
       custom_roles = models.JSONField(default=dict)
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_GROUPCHAT_MODEL'

   class CustomChannel(CustomRoom, AbstractChannel):
       verified = models.BooleanField(default=False)
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_CHANNEL_MODEL'

**Register all:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Room": "myapp.models.CustomRoom",
           "OneToOneChat": "myapp.models.CustomOneToOneChat",
           "GroupChat": "myapp.models.CustomGroupChat",
           "Channel": "myapp.models.CustomChannel"
       }
   }

Other Model Examples
--------------------

MessageMediaAsset
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from realtime_chat_messaging.model_mixins import AbstractMessageMediaAsset

   class CustomMessageMediaAsset(AbstractMessageMediaAsset):
       thumbnail_url = models.URLField(null=True, blank=True)
       blurhash = models.CharField(max_length=100, null=True, blank=True)
       virus_scanned = models.BooleanField(default=False)
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_MESSAGEMEDIAASSET_MODEL'

ReadReceipt
~~~~~~~~~~~

.. code-block:: python

   from realtime_chat_messaging.model_mixins import AbstractReadReceipt

   class CustomReadReceipt(AbstractReadReceipt):
       device_type = models.CharField(max_length=20, null=True)  # 'web', 'ios', 'android'
       
       class Meta:
           swappable = 'REALTIME_CHAT_MESSAGING_READRECEIPT_MODEL'
           constraints = [
               models.UniqueConstraint(fields=['message', 'reader'], name='unique_read_receipts'),
           ]

Required Fields
---------------

Each abstract model has required fields that MUST be included.

AbstractMessage
~~~~~~~~~~~~~~~

.. code-block:: python

   id = UUIDField(primary_key=True, default=uuid.uuid4)
   room = ForeignKey(Room, on_delete=CASCADE)
   sender = ForeignKey(User, on_delete=CASCADE)
   content = TextField()
   created_at = DateTimeField(auto_now_add=True)
   updated_at = DateTimeField(auto_now=True)

AbstractRoom
~~~~~~~~~~~~

.. code-block:: python

   id = UUIDField(primary_key=True, default=uuid.uuid4)
   last_message = ForeignKey(Message, null=True, on_delete=SET_NULL)
   created_at = DateTimeField(auto_now_add=True)
   updated_at = DateTimeField(auto_now=True)

AbstractGroupChat
~~~~~~~~~~~~~~~~~

.. code-block:: python

   name = CharField(max_length=64)
   description = TextField(null=True, blank=True)
   creator = ForeignKey(User, on_delete=CASCADE)
   participants = ManyToManyField(User)

AbstractChannel
~~~~~~~~~~~~~~~

.. code-block:: python

   name = CharField(max_length=64)
   description = TextField(null=True, blank=True)
   creator = ForeignKey(User, on_delete=CASCADE)
   subscribers = ManyToManyField(User)

Migration Strategy
------------------

Initial Setup (No Data)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # 1. Define custom models
   # 2. Configure settings
   # 3. Run migrations
   python manage.py makemigrations
   python manage.py migrate

Changing After Deployment
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. danger::
   **Never change swappable models after production deployment without a migration plan.**

**Safe approach:**

1. Create new custom model
2. Run migrations to add new table
3. Write data migration to copy data
4. Update settings to point to new model
5. Remove old tables

**Example data migration:**

.. code-block:: python

   # migrations/0002_migrate_to_custom_message.py
   from django.db import migrations

   def copy_messages(apps, schema_editor):
       OldMessage = apps.get_model('realtime_chat_messaging', 'Message')
       NewMessage = apps.get_model('myapp', 'CustomMessage')
       
       for old_msg in OldMessage.objects.all():
           NewMessage.objects.create(
               id=old_msg.id,
               room=old_msg.room,
               sender=old_msg.sender,
               content=old_msg.content,
               created_at=old_msg.created_at,
               updated_at=old_msg.updated_at,
               # Set defaults for new fields
               priority='normal',
               is_pinned=False
           )

   class Migration(migrations.Migration):
       dependencies = [
           ('myapp', '0001_initial'),
       ]
       
       operations = [
           migrations.RunPython(copy_messages),
       ]

Common Patterns
---------------

Soft Delete
~~~~~~~~~~~

.. code-block:: python

   class CustomMessage(AbstractMessage):
       deleted_at = models.DateTimeField(null=True, blank=True)
       deleted_by = models.ForeignKey(User, null=True, on_delete=SET_NULL, related_name='+')
       
       def soft_delete(self, user):
           self.deleted_at = timezone.now()
           self.deleted_by = user
           self.save()

Message Threading
~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessage(AbstractMessage):
       thread_id = models.UUIDField(null=True, blank=True)
       thread_position = models.IntegerField(default=0)
       
       def save(self, *args, **kwargs):
           if self.parent_message and not self.thread_id:
               # Inherit thread from parent
               self.thread_id = self.parent_message.thread_id or self.parent_message.id
           super().save(*args, **kwargs)

Room Categories
~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomRoom(PolymorphicModel, AbstractRoom):
       category = models.CharField(
           max_length=50,
           choices=[
               ('work', 'Work'),
               ('personal', 'Personal'),
               ('social', 'Social')
           ],
           default='personal'
       )
       tags = models.JSONField(default=list)

User Presence
~~~~~~~~~~~~~

.. code-block:: python

   class CustomOneToOneChat(Room, AbstractOneToOneChat):
       last_activity = models.JSONField(default=dict)
       # {'user_id': '2024-01-10T12:00:00Z', ...}

Best Practices
--------------

Keep Migrations Simple
~~~~~~~~~~~~~~~~~~~~~~

Don't add complex logic in model definitions:

.. code-block:: python

   # ❌ Bad
   class CustomMessage(AbstractMessage):
       def calculate_sentiment(self):
           # Complex AI processing
           pass

   # ✅ Good
   class CustomMessage(AbstractMessage):
       sentiment_score = models.FloatField(null=True)
       # Calculate in signal or celery task

Use Signals for Automation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from django.db.models.signals import post_save
   from django.dispatch import receiver

   @receiver(post_save, sender=CustomMessage)
   def extract_mentions(sender, instance, created, **kwargs):
       if created and '@' in instance.content:
           # Extract and set mentioned_users
           usernames = re.findall(r'@(\w+)', instance.content)
           users = User.objects.filter(username__in=usernames)
           instance.mentioned_users.set(users)

Document Custom Fields
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomMessage(AbstractMessage):
       priority = models.CharField(
           max_length=10,
           choices=[...],
           default='normal',
           help_text="Message priority level. High priority messages are highlighted in UI."
       )

See Also
--------

* :doc:`serializers` - Update serializers for custom fields
* :doc:`handlers` - Custom business logic
* :doc:`../api-reference/settings` - MODELS setting