"""
Default configuration settings for the real-time chat messaging system.

This module defines the default values for all configurable components in the
chat system, including serializers, models, handlers, and behavioral settings.
These defaults can be overridden in Django settings using the
REALTIME_CHAT_MESSAGING dictionary.

All import paths use dot notation (e.g., 'app.module.ClassName') and are
dynamically imported at runtime to allow for custom implementations without
modifying the package source code.

Configuration Structure:
    - SERIALIZERS: DRF serializers for data validation and transformation
    - MODELS: Django models defining the database schema
    - Handlers: Pluggable classes for permissions, events, and exceptions
    - Behavioral flags: Feature toggles and timing configurations

Example:
    Override defaults in your Django settings.py::

        REALTIME_CHAT_MESSAGING = {
            'SERIALIZERS': {
                'MessageSerializer': 'myapp.serializers.CustomMessageSerializer',
            },
            'MESSAGE_SOFT_DELETE': True,
            'INACTIVITY_THRESHOLD': 300  # 5 minutes
        }
"""



DEFAULTS = {
        
        "SERIALIZERS": {
                "RoomListPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomListPolymorphicSerializer",
                "RoomPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomPolymorphicSerializer",
                "RoomPropertySerializer": "realtime_chat_messaging.serializers.RoomPropertySerializer",
                "ReactionSerializer": "realtime_chat_messaging.serializers.ReactionSerializer",
                "MessageMediaAssetSerializer": "realtime_chat_messaging.serializers.MessageMediaAssetSerializer",
                "MessageSerializer": "realtime_chat_messaging.serializers.MessageSerializer",
                "ChatNotificationSerializer": "realtime_chat_messaging.serializers.ChatNotificationSerializer",
                "UserSerializer": "realtime_chat_messaging.serializers.UserSerializer",
                "OneToOneChatListSerializer": "realtime_chat_messaging.serializers.OneToOneChatListSerializer",
                "GroupChatListSerializer": "realtime_chat_messaging.serializers.GroupChatListSerializer",
                "ChannelListSerializer": "realtime_chat_messaging.serializers.ChannelListSerializer",
                "OneToOneChatSerializer": "realtime_chat_messaging.serializers.OneToOneChatSerializer",
                "GroupChatSerializer": "realtime_chat_messaging.serializers.GroupChatSerializer",
                "ChannelSerializer": "realtime_chat_messaging.serializers.ChannelSerializer",
                "ReadReceiptSerializer": "realtime_chat_messaging.serializers.ReadReceiptSerializer"
        },
        "MODELS": {
                "Session": "realtime_chat_messaging.Session",
                "Room": "realtime_chat_messaging.Room",
                "RoomProperty": "realtime_chat_messaging.RoomProperty",
                "OneToOneChat": "realtime_chat_messaging.OneToOneChat",
                "GroupChat": "realtime_chat_messaging.GroupChat",
                "Channel": "realtime_chat_messaging.Channel",
                "Message": "realtime_chat_messaging.Message",
                "MessageMediaAsset": "realtime_chat_messaging.MessageMediaAsset",
                "ReadReceipt": "realtime_chat_messaging.ReadReceipt",
                "ChatNotification": "realtime_chat_messaging.ChatNotification",
                "Reaction": "realtime_chat_messaging.Reaction",
        },
        "PERMISSION_HANDLER_CLASS": "realtime_chat_messaging.permissions.handlers.PermissionHandler",
        "EVENT_MAPPER": "realtime_chat_messaging.variables.consumers.map_event_type_to_handlers",
        "EVENT_HANDLER_CLASS": "realtime_chat_messaging.utils.handlers.EventHandler",
        "EXCEPTION_HANDLER_CLASS": "realtime_chat_messaging.utils.decorators.ExceptionHandler",
        "CHAT_CONSUMER_CLASS": "realtime_chat_messaging.consumers.ChatMessagingConsumer",
        "WEBSOCKET_PATH": "messaging/",
        "MESSAGE_SOFT_DELETE": False,
        "ENABLE_NOTIFICATION": True,
        "INACTIVITY_THRESHOLD": 60 # 1 minute
    }




"""
    "PERMISSION_HANDLER_CLASS": "realtime_chat_messaging.permissions.handlers.PermissionHandler",
    
    ```
    Handler class for permission checks across the chat system.
    
    This class is responsible for determining user authorization for actions
    like sending messages, adding/removing members, and modifying rooms.
    
    To implement custom permission logic, subclass the base PermissionHandler
    and override specific permission methods.
    ```
 
    
    "EVENT_MAPPER": "realtime_chat_messaging.variables.consumers.map_event_type_to_handlers",
    
    ```
    Function that maps incoming event types to consumer handler methods.
    
    This mapper is called in the consumer's receive() method to route events
    like 'message.send', 'room.create', etc. to their corresponding handlers.
    
    Custom mappers must return a dictionary with event type strings as keys
    and callables as values.
    ```
    
    "EVENT_HANDLER_CLASS": "realtime_chat_messaging.utils.handlers.EventHandler",
 
    ```
    Handler class for processing chat events and business logic.
    
    This class contains the core logic for creating messages, managing rooms,
    handling reactions, read receipts, and all other chat operations. It acts
    as the bridge between consumers and the database layer.
    
    Custom implementations can override specific event handling methods to
    modify default behavior without rewriting the entire handler.
    ```
    
    "EXCEPTION_HANDLER_CLASS": "realtime_chat_messaging.utils.decorators.ExceptionHandler",
 
    ```
    Handler class for catching and formatting WebSocket exceptions.
    
    This class provides the exception_handler_decorator that wraps consumer
    methods, catches exceptions, and sends structured error responses to
    clients using custom WebSocket close codes.
    
    Custom exception handlers can implement different error reporting formats
    or add additional exception types.
    ```

    "CHAT_CONSUMER_CLASS": "realtime_chat_messaging.consumers.ChatMessagingConsumer",
    ```
    The WebSocket consumer class that handles real-time communication.
    ```
        
    "WEBSOCKET_PATH": "messaging/",
    ```
    The URL path for WebSocket connections to the chat consumer.
    Clients should connect to ws://<host>/<WEBSOCKET_PATH> to access the chat
    functionality. This can be customized to fit the URL structure of your
    application.
    Type: str
    Default: "messaging/"
    ```
    
    "MESSAGE_SOFT_DELETE": False,

    ```
    Enable soft deletion for messages.
    
    When True, deleted messages are marked with a flag instead of being
    removed from the database. This allows for message recovery and maintains
    conversation history integrity.
    
    When False (default), deleted messages are permanently removed from the
    database.
    
    Type: bool
    Default: False
    ```        
    
    "ENABLE_NOTIFICATION": True,

    ```
    Enable chat notification dispatching on connection.
    
    When True, pending chat notifications are automatically sent to users
    when they connect to the WebSocket. This includes unread message counts,
    mentions, and other notification types.
    
    When False, notifications must be manually requested by the client.
    
    Type: bool
    Default: True
    ```
    
    "INACTIVITY_THRESHOLD": 60
 
    ```
    Session inactivity timeout in seconds.
    
    Sessions that haven't sent a heartbeat within this threshold are
    considered expired and will be cleaned up. Expired sessions are removed
    from all channel groups to prevent message delivery to disconnected
    clients.
    
    Clients should send session.heartbeat events at least 2-3 times within
    this threshold to maintain their session.
    
    Type: int
    Default: 60 (1 minute)
    Unit: seconds
    ```
"""