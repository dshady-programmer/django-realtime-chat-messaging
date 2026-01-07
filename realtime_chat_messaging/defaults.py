



DEFAULTS = {
        
        "SERIALIZERS": {
                "RoomListPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomListPolymorphicSerializer",
                "RoomPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomPolymorphicSerializer",
                "ReactionSerializer": "realtime_chat_messaging.serializers.ReactionSerializer",
                "MessageMediaAssetSerializer": "realtime_chat_messaging.serializers.MessageMediaAssetSerializer",
                "MessageSerializer": "realtime_chat_messaging.serializers.MessageSerializer",
                "ChatNotificationSerializer": "realtime_chat_messaging.serializers.ChatNotificationSerializer"
        },
        "MODELS": {
                "Room": "realtime_chat_messaging.Room", 
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
        "MESSAGE_SOFT_DELETE": False,
        "ENABLE_NOTIFICATION": True

    }