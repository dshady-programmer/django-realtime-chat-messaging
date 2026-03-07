Custom Models
=============

Every concrete model in the package (except ``Room``) is swappable. You can
replace any model with your own implementation that adds fields, changes
behaviour, or both — without modifying the package source.

Overview
--------

The workflow for adding a custom model is:

1. Create a new Django app.
2. Create your model by inheriting from the appropriate abstract base class.
3. Register the model in ``REALTIME_CHAT_MESSAGING`` settings.
4. Create a matching custom serializer.
5. Run ``makemigrations``, fix the circular dependency, then ``migrate``.
6. Reconnect signals if you need them on your custom model.

Step 1 — Create a New App
--------------------------

.. code-block:: bash

   python manage.py startapp myapp

Add it to ``INSTALLED_APPS``:

.. code-block:: python

   INSTALLED_APPS = [
       ...
       "myapp",
   ]

Step 2 — Create Your Model
---------------------------

Inherit from the abstract base model in
``realtime_chat_messaging.mixins.models``. Always:

- Inherit from the abstract class (e.g. ``AbstractMessage``).
- Inherit the ``Meta`` class from the abstract parent.
- Set ``abstract = False`` in your ``Meta``.
- **Do not** add a ``swappable`` attribute to your ``Meta`` — that is only needed
  on the package's own concrete models.

.. code-block:: python

   # myapp/models.py
   from django.db import models
   from realtime_chat_messaging.mixins.models import AbstractMessage


   class CustomMessage(AbstractMessage):
       """Custom message with priority, pinning, and expiry."""

       PRIORITY_CHOICES = [
           ("low", "Low"),
           ("normal", "Normal"),
           ("high", "High"),
           ("urgent", "Urgent"),
       ]

       priority = models.CharField(
           max_length=20,
           choices=PRIORITY_CHOICES,
           default="normal",
       )
       is_pinned = models.BooleanField(default=False)
       expiry_date = models.DateTimeField(null=True, blank=True)

       class Meta(AbstractMessage.Meta):
           abstract = False
           ordering = ["-priority", "-created_at"]

Step 3 — Register in Settings
------------------------------

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.CustomMessage",
       },
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
       },
   }

.. important::

   Whenever you swap a model, you **must** also provide a matching custom
   serializer. The package will use your serializer for all operations involving
   that model.

Step 4 — Create a Custom Serializer
-------------------------------------

Inherit from the corresponding serializer mixin and ``ModelSerializer``:

.. code-block:: python

   # myapp/serializers.py
   from rest_framework import serializers
   from realtime_chat_messaging.mixins.serializers import MessageSerializerMixin
   from .models import CustomMessage


   class CustomMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):

       priority = serializers.ChoiceField(
           choices=CustomMessage.PRIORITY_CHOICES,
           default="normal",
       )
       is_pinned = serializers.BooleanField(read_only=True)

       class Meta:
           model = CustomMessage
           fields = [
               "id", "content", "room", "room_id", "sender", "sender_id",
               "priority", "is_pinned", "expiry_date",
               "is_deleted", "is_edited", "is_forwarded",
               "forwarded_from", "parent_message",
               "delivered_to", "read_receipts", "reactions", "attachments",
               "created_at", "updated_at",
           ] # or "__all__" if you want all fields
           read_only_fields = ["id", "created_at", "updated_at"]

.. note::

   The ``MessageSerializerMixin`` provides ``room``, ``room_id``, ``sender``,
   ``sender_id``, ``read_receipts``, ``reactions``, ``attachments``, and
   ``validate_content()``. Include the fields it provides in your ``Meta.fields``
   list as needed.

Step 5 — Migrations and the Circular Dependency Fix
----------------------------------------------------

Run ``makemigrations``:

.. code-block:: bash

   python manage.py makemigrations myapp

Django will generate a migration that depends on
``('realtime_chat_messaging', '0002_initial')``. **Do not run this migration.**
It will fail with a circular dependency error because ``0002_initial`` already
depends on ``settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL`` (which is now
pointing at your custom model).

**The fix**: open the generated migration file and change the dependency from
``0002_initial`` to ``0001_initial``:

.. code-block:: python

   # myapp/migrations/0001_initial.py

   class Migration(migrations.Migration):
       initial = True

       dependencies = [
           # Change this:
           # ("realtime_chat_messaging", "0002_initial"),
           # To this:
           ("realtime_chat_messaging", "0001_initial"),   # ← fix
           migrations.swappable_dependency(settings.AUTH_USER_MODEL),
       ]

       # ... rest of migration unchanged

This applies to **all swappable models**. Whenever Django auto-generates a
``0002_initial`` dependency for any swapped model, change it to ``0001_initial``.

Now run the migrations:

.. code-block:: bash

   python manage.py migrate

Step 6 — Signals
-----------------

Signals defined in the package are connected to the **default concrete models**
(e.g. ``OneToOneChat``, ``GroupChat``). When you swap a model, those signals do
**not** automatically attach to your custom model. You must reconnect them
yourself if you need their behaviour.
**Why this ?** Because we want users to take control of their customization without unnecessary side effects

For example, if you create a custom ``GroupChat``, reconnect the relevant
signals based on your need:

.. code-block:: python

   # myapp/signals.py
   from django.db.models.signals import m2m_changed, post_save
   from django.dispatch import receiver
   from guardian.shortcuts import assign_perm
   from .models import CustomGroupChat


   @receiver(post_save, sender=CustomGroupChat)
   def add_creator_as_admin(sender, instance, created, **kwargs):
       if created:
           instance.participants.add(instance.creator)
           instance.admins.add(instance.creator)
           assign_perm("can_add_new_participants", instance.creator, instance)
           assign_perm("can_remove_participants", instance.creator, instance)

Connect signals in your ``AppConfig.ready()``:

.. code-block:: python

   # myapp/apps.py
   from django.apps import AppConfig

   class MyAppConfig(AppConfig):
       name = "myapp"

       def ready(self):
           from . import signals  # noqa

Available Abstract Models
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Abstract Class
     - Use for
   * - ``AbstractMessage``
     - Extending the ``Message`` model
   * - ``AbstractReadReceipt``
     - Extending the ``ReadReceipt`` model
   * - ``AbstractReaction``
     - Extending the ``Reaction`` model
   * - ``AbstractChatNotification``
     - Extending the ``ChatNotification`` model
   * - ``AbstractMessageMediaAsset``
     - Extending the ``MessageMediaAsset`` model
   * - ``AbstractSession``
     - Extending the ``Session`` model
   * - ``AbstractRoomProperty``
     - Extending the ``RoomProperty`` model
   * - ``AbstractOneToOneChat``
     - Extending the ``OneToOneChat`` model (also inherit ``Room``)
   * - ``AbstractGroupChat``
     - Extending the ``GroupChat`` model (also inherit ``Room``)
   * - ``AbstractChannel``
     - Extending the ``Channel`` model (also inherit ``Room``)

Extending Room Types
--------------------

Room models are more involved because they use polymorphic inheritance. Your
custom room model must inherit from both ``Room`` and the abstract base:

.. code-block:: python

   # myapp/models.py
   from realtime_chat_messaging.models import Room
   from realtime_chat_messaging.mixins.models import AbstractGroupChat


   class CustomGroupChat(Room, AbstractGroupChat):
       """GroupChat with a custom welcome_message field."""

       welcome_message = models.TextField(blank=True, default="")

       class Meta(AbstractGroupChat.Meta):
           abstract = False

.. warning::

   Do not swap the ``Room`` base model itself. All concrete room types must
   inherit from ``realtime_chat_messaging.models.Room`` for polymorphic queries
   to work correctly. Only the concrete room subclasses (``OneToOneChat``,
   ``GroupChat``, ``Channel``) are intended to be swapped.

Extending RoomProperty
-----------------------

``RoomProperty`` is auto-created by a ``pre_save`` signal with no arguments.
If your custom ``RoomProperty`` has extra required fields, you must either give
them defaults or allow them to be nullable:

.. code-block:: python

   # myapp/models.py
   from realtime_chat_messaging.mixins.models import AbstractRoomProperty
   from django.db import models


   class CustomRoomProperty(AbstractRoomProperty):
       theme = models.CharField(max_length=32, default="light")

       class Meta(AbstractRoomProperty.Meta):
           abstract = False

Because ``theme`` has a default, auto-creation via the signal out of the box. 

.. Note::
    If you have overridden any of the Room models (GroupChat, Channel, OneToOneChat), then you should
    create custom signals for this. The default signals only listens for event on the
    default models.

Swapping Multiple Models
-------------------------

You can swap multiple models at the same time. Register all of them in settings:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.CustomMessage",
           "ReadReceipt": "myapp.CustomReadReceipt",
       },
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
           "ReadReceiptSerializer": "myapp.serializers.CustomReadReceiptSerializer",
       },
   }

For each swapped model's migration, apply the same ``0002_initial`` →
``0001_initial`` fix. If your models reference each other (e.g. a custom
``ReadReceipt`` that references your custom ``Message``), order the dependency
declarations carefully and lean on ``swappable_dependency`` for the settings-based
references.
