



DEFAULTS = {
        
        "SERIALIZERS": {
                "RoomListPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomListPolymorphicSerializer",
                "RoomPolymorphicSerializer": "realtime_chat_messaging.serializers.RoomPolymorphicSerializer",
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
        "ENABLE_NOTIFICATION": True,
        "INACTIVITY_THRESHOLD": 60 # 1 minute
    }
