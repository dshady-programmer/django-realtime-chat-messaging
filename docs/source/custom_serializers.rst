Custom Serializers
==================

Every serializer in the package can be replaced via the ``SERIALIZERS`` setting.
The most common reasons to create a custom serializer are:

- Adding fields from a custom model (required when swapping any model).
- Customizing the ``UserSerializer`` to expose additional user fields like
  ``profile_picture`` or ``display_name``.
- Changing validation logic.
- Controlling which fields are read-only or write-only.

The Serializer Mixin Pattern
-----------------------------

The package separates serializer logic into two layers:

- **Mixin** (``realtime_chat_messaging.mixins.serializers``) — provides
  ``SerializerMethodField`` declarations, write-only ID fields, and shared
  validation (e.g. XSS sanitisation). These are reusable building blocks.
- **Concrete serializer** (``realtime_chat_messaging.serializers``) — combines
  the mixin with ``ModelSerializer`` and provides the ``Meta`` class.

To create a custom serializer, inherit from the mixin and ``ModelSerializer``:

.. code-block:: python

   from rest_framework import serializers
   from realtime_chat_messaging.mixins.serializers import MessageSerializerMixin
   from .models import CustomMessage


   class CustomMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):

       class Meta:
           model = CustomMessage
           fields = "__all__"

Available Mixins
----------------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Mixin
     - Provides
   * - ``MessageSerializerMixin``
     - ``room``, ``room_id``, ``sender``, ``sender_id``, ``read_receipts``, ``reactions``, ``attachments``, ``validate_content()``
   * - ``ReadReceiptSerializerMixin``
     - ``reader``, ``reader_id`` (write-only), ``message_id`` (write-only)
   * - ``ReactionSerializerMixin``
     - ``user``, ``user_id`` (write-only), ``message`` (write-only)
   * - ``MessageMediaAssetSerializerMixin``
     - ``message_id`` (write-only)
   * - ``ChatNotificationSerializerMixin``
     - ``message``, ``message_id`` (write-only)
   * - ``OneToOneChatSerializerMixin``
     - ``participants``, ``property``
   * - ``GroupChatSerializerMixin``
     - ``creator``, ``participants``, ``property``
   * - ``ChannelSerializerMixin``
     - ``creator``, ``subscribers``, ``property``
   * - ``OneToOneChatListSerializerMixin``
     - ``peer``, ``last_message`` (requires ``user`` in context)
   * - ``GroupChatListSerializerMixin``
     - ``creator``, ``last_message``
   * - ``ChannelListSerializerMixin``
     - ``creator``, ``last_message``

Customizing ``UserSerializer``
-------------------------------

The default ``UserSerializer`` exposes only ``id``, ``username``, ``email``,
``first_name``, and ``last_name``. This is intentionally minimal. To expose
additional fields (e.g. a ``profile_picture`` from a related ``Profile`` model):

.. code-block:: python

   # myapp/serializers.py
   from django.contrib.auth import get_user_model
   from rest_framework import serializers

   User = get_user_model()


   class ExtendedUserSerializer(serializers.ModelSerializer):

       profile_picture = serializers.SerializerMethodField()

       class Meta:
           model = User
           fields = ["id", "username", "email", "first_name", "last_name",
                     "profile_picture"]

       def get_profile_picture(self, obj):
           if hasattr(obj, "profile") and obj.profile.picture:
               return obj.profile.picture.url
           return None

Register it:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "SERIALIZERS": {
           "UserSerializer": "myapp.serializers.ExtendedUserSerializer",
       }
   }

The ``ExtendedUserSerializer`` will now be used everywhere a user is nested in
the output — messages, room participants, reactions, read receipts, etc.

Customizing ``MessageSerializer``
----------------------------------

The ``MessageSerializer`` is the most commonly customized serializer when using
custom message models. Key points:

- Keep the ``MessageSerializerMixin`` in the MRO — it provides XSS sanitisation
  and correct relationship serialization.
- The ``update()`` method in the default serializer prevents modification of
  immutable fields. If you override it, replicate this protection or call
  ``super().update()``.
- The ``parent_message`` and ``forwarded_from`` fields use ``RecursiveField``
  for nested serialization. Include them in ``fields`` if you need reply/forward
  data in responses.

.. code-block:: python

   from rest_framework import serializers
   from django_rest_framework_recursive.fields import RecursiveField
   from realtime_chat_messaging.mixins.serializers import MessageSerializerMixin
   from realtime_chat_messaging.utils.loader import get_model
   from .models import CustomMessage


   class CustomMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):

       # Preserve recursive fields from the default serializer
       parent_message_id = serializers.PrimaryKeyRelatedField(
           queryset=get_model("Message").objects.all(),
           source="parent_message",
           write_only=True,
           required=False,
       )
       forwarded_from_id = serializers.PrimaryKeyRelatedField(
           queryset=get_model("Message").objects.all(),
           source="forwarded_from",
           write_only=True,
           required=False,
       )
       parent_message = RecursiveField(allow_null=True, read_only=True)
       forwarded_from = RecursiveField(allow_null=True, read_only=True)
       delivered_to = serializers.SerializerMethodField()

       # Custom fields
       priority = serializers.ChoiceField(
           choices=CustomMessage.PRIORITY_CHOICES,
           default="normal",
       )

       class Meta:
           model = CustomMessage
           fields = "__all__"

       def get_delivered_to(self, instance):
           return list(instance.delivered_to.values_list("username", flat=True))

Customizing Room Serializers
-----------------------------

For custom room models with extra fields, extend the room serializer mixin:

.. code-block:: python

   from rest_framework import serializers
   from realtime_chat_messaging.mixins.serializers import GroupChatSerializerMixin
   from .models import CustomGroupChat


   class CustomGroupChatSerializer(GroupChatSerializerMixin, serializers.ModelSerializer):

       welcome_message = serializers.CharField(required=False, allow_blank=True)

       class Meta:
           model = CustomGroupChat
           exclude = ["last_message"]

Register the serializer under all relevant keys (both the detail and list
serializer if you also want a custom list view):

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "GroupChat": "myapp.CustomGroupChat",
       },
       "SERIALIZERS": {
           "GroupChatSerializer": "myapp.serializers.CustomGroupChatSerializer",
           "GroupChatListSerializer": "myapp.serializers.CustomGroupChatListSerializer",
       },
   }

Validation and ``extra_fields``
--------------------------------

The ``room.create`` and ``message.send`` events support an ``extra_fields``
dictionary that is merged with the main payload before serializer validation.
Any custom fields you add to your model and serializer can be passed via
``extra_fields`` from the client, and they will be validated by your serializer
automatically.

.. code-block:: json

   {
     "event_type": "message.send",
     "data": {
       "room_id": "<uuid>",
       "content": "Urgent issue!",
       "extra_fields": {
         "priority": "urgent",
         "is_pinned": false
       }
     }
   }

.. warning::

   Be careful with ``message.modify`` (update action). The default
   ``MessageSerializer.update()`` only allows ``content`` to be updated —
   all other fields are explicitly discarded regardless of what the client sends.

   If you add custom fields to your serializer that should be updatable, they
   will only take effect if they are not among the default non-updatable fields.
   These are:

   ``sender``, ``room``, ``parent_message``, ``forwarded_from``,
   ``is_forwarded``, ``is_deleted``, ``created_at``, ``updated_at``

   Note that relational fields (``sender``, ``room``, ``parent_message``,
   ``forwarded_from``) are represented via ``PrimaryKeyRelatedField`` in the
   default serializer, meaning they arrive in request data as ``sender_id``,
   ``room_id``, ``parent_message_id``, and ``forwarded_from_id`` respectively.
   Keep this in mind when deciding which field names to guard against in a
   custom ``update()`` override.

   Override ``update()`` in your custom serializer to explicitly handle any
   additional updatable fields, and be careful not to expose sensitive or
   structurally immutable fields to client modification.