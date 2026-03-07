Settings Reference
==================

All package settings live under the ``REALTIME_CHAT_MESSAGING`` key in your
Django ``settings.py``:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MESSAGE_SOFT_DELETE": True,
       "INACTIVITY_THRESHOLD": 300,
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
       },
   }

You only need to specify the keys you want to override. All other settings fall
back to their defaults. Dictionary settings (``SERIALIZERS``, ``MODELS``) are
merged with defaults — you only specify the entries you are changing.

Behavioural Settings
--------------------

``MESSAGE_SOFT_DELETE``
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``bool``
   * - Default
     - ``False``

Controls how message deletion works.

- ``False`` — deleted messages are permanently removed from the database.
- ``True`` — deleted messages have ``is_deleted`` set to ``True`` and remain in
  the database. Soft-deleted messages are excluded from ``room.messages``
  queries. This is useful for audit trails, message recovery, or analytics.

``ENABLE_NOTIFICATION``
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``bool``
   * - Default
     - ``True``

Controls the ``ChatNotification`` system.

- ``True`` — notifications are created for every message and dispatched to users
  on connection via ``chat.notifications``.
- ``False`` — no notifications are created and the ``chat.notifications`` event
  is never sent. ``message.acknowledged`` still updates ``delivered_to`` on
  messages.

``INACTIVITY_THRESHOLD``
~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``int``
   * - Default
     - ``60``
   * - Unit
     - seconds

Sessions older than this value are considered expired and cleaned up. Clients
should send ``session.heartbeat`` events **2–3 times within this window** (every
15–30 seconds for the default of 60). Adjust for your application's expected idle
time:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "INACTIVITY_THRESHOLD": 300  # 5 minutes
   }

``WEBSOCKET_PATH``
~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``str``
   * - Default
     - ``"messaging/"``

The URL path for WebSocket connections. Clients connect to
``ws://<host>/<WEBSOCKET_PATH>``. Change this to fit your URL structure:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "WEBSOCKET_PATH": "ws/chat/"
   }

Pluggable Class Settings
------------------------

All handler and consumer classes can be replaced with custom implementations by
providing a dotted import path.

``CHAT_CONSUMER_CLASS``
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``str`` (dotted import path)
   * - Default
     - ``"realtime_chat_messaging.consumers.ChatMessagingConsumer"``

The WebSocket consumer class. Replace with a subclass of
``ChatMessagingConsumer`` to add custom event handlers or override existing ones.
See :doc:`custom_consumer`.

``EVENT_MAPPER``
~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``str`` (dotted import path to a function)
   * - Default
     - ``"realtime_chat_messaging.variables.consumers.map_event_type_to_handlers"``

A callable that receives the consumer instance and returns a ``dict`` mapping
event type strings to handler methods. Override to add, remove, or remap events.
See :doc:`custom_consumer`.

``EVENT_HANDLER_CLASS``
~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``str`` (dotted import path)
   * - Default
     - ``"realtime_chat_messaging.utils.handlers.EventHandler"``

The business logic handler. Contains all room, message, session, and notification
logic. Override specific methods to change default behaviour. See
:doc:`custom_handlers`.

``PERMISSION_HANDLER_CLASS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``str`` (dotted import path)
   * - Default
     - ``"realtime_chat_messaging.permissions.handlers.PermissionHandler"``

The authorization handler. Implement custom permission rules by subclassing.
See :doc:`custom_permissions`.

``EXCEPTION_HANDLER_CLASS``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 80

   * - Type
     - ``str`` (dotted import path)
   * - Default
     - ``"realtime_chat_messaging.utils.decorators.ExceptionHandler"``

The exception handler class. Provides ``exception_handler_decorator`` used to
wrap all consumer methods. Override to add custom exception types or change error
formatting. Must expose a ``classmethod`` named ``exception_handler_decorator``.

``MODELS`` Dictionary
---------------------

Override individual model classes. Each value is a dotted ``app_label.ModelName``
string. You only need to specify models you are replacing.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "MODELS": {
           "Message": "myapp.CustomMessage",
           "ReadReceipt": "myapp.CustomReadReceipt",
       }
   }

Available model keys:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Key
     - Default
   * - ``Session``
     - ``realtime_chat_messaging.Session``
   * - ``Room``
     - ``realtime_chat_messaging.Room``
   * - ``RoomProperty``
     - ``realtime_chat_messaging.RoomProperty``
   * - ``OneToOneChat``
     - ``realtime_chat_messaging.OneToOneChat``
   * - ``GroupChat``
     - ``realtime_chat_messaging.GroupChat``
   * - ``Channel``
     - ``realtime_chat_messaging.Channel``
   * - ``Message``
     - ``realtime_chat_messaging.Message``
   * - ``MessageMediaAsset``
     - ``realtime_chat_messaging.MessageMediaAsset``
   * - ``ReadReceipt``
     - ``realtime_chat_messaging.ReadReceipt``
   * - ``ChatNotification``
     - ``realtime_chat_messaging.ChatNotification``
   * - ``Reaction``
     - ``realtime_chat_messaging.Reaction``

.. note::

   ``Room`` is a polymorphic base model. You cannot swap it in the same way as
   other models — all concrete room types inherit from it. See
   :doc:`custom_models` for extending room types.

``SERIALIZERS`` Dictionary
--------------------------

Override individual serializer classes. Only specify the serializers you are
replacing.

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
           "UserSerializer": "myapp.serializers.UserSerializer",
       }
   }

Available serializer keys:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - Default
   * - ``UserSerializer``
     - ``realtime_chat_messaging.serializers.UserSerializer``
   * - ``MessageSerializer``
     - ``realtime_chat_messaging.serializers.MessageSerializer``
   * - ``RoomPropertySerializer``
     - ``realtime_chat_messaging.serializers.RoomPropertySerializer``
   * - ``ReadReceiptSerializer``
     - ``realtime_chat_messaging.serializers.ReadReceiptSerializer``
   * - ``ReactionSerializer``
     - ``realtime_chat_messaging.serializers.ReactionSerializer``
   * - ``MessageMediaAssetSerializer``
     - ``realtime_chat_messaging.serializers.MessageMediaAssetSerializer``
   * - ``ChatNotificationSerializer``
     - ``realtime_chat_messaging.serializers.ChatNotificationSerializer``
   * - ``OneToOneChatSerializer``
     - ``realtime_chat_messaging.serializers.OneToOneChatSerializer``
   * - ``GroupChatSerializer``
     - ``realtime_chat_messaging.serializers.GroupChatSerializer``
   * - ``ChannelSerializer``
     - ``realtime_chat_messaging.serializers.ChannelSerializer``
   * - ``OneToOneChatListSerializer``
     - ``realtime_chat_messaging.serializers.OneToOneChatListSerializer``
   * - ``GroupChatListSerializer``
     - ``realtime_chat_messaging.serializers.GroupChatListSerializer``
   * - ``ChannelListSerializer``
     - ``realtime_chat_messaging.serializers.ChannelListSerializer``
   * - ``RoomPolymorphicSerializer``
     - ``realtime_chat_messaging.serializers.RoomPolymorphicSerializer``
   * - ``RoomListPolymorphicSerializer``
     - ``realtime_chat_messaging.serializers.RoomListPolymorphicSerializer``

Complete Example
----------------

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       # Feature flags
       "MESSAGE_SOFT_DELETE": True,
       "ENABLE_NOTIFICATION": True,
       "INACTIVITY_THRESHOLD": 120,
       "WEBSOCKET_PATH": "ws/chat/",

       # Custom models
       "MODELS": {
           "Message": "myapp.CustomMessage",
       },

       # Custom serializers
       "SERIALIZERS": {
           "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
           "UserSerializer": "myapp.serializers.ExtendedUserSerializer",
       },

       # Custom handlers
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler",
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler",
       "CHAT_CONSUMER_CLASS": "myapp.consumers.CustomChatConsumer",
       "EVENT_MAPPER": "myapp.events.custom_event_mapper",
   }
