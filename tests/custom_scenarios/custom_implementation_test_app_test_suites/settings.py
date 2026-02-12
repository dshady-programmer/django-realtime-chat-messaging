from ...settings import *



REALTIME_CHAT_MESSAGING={
    'MODELS': {
        'Message': 'custom_implementation_test_app.CustomMessage',
        'GroupChat': 'custom_implementation_test_app.CustomGroupChat',
        'Session': 'custom_implementation_test_app.CustomSession',
        'RoomProperty': 'custom_implementation_test_app.CustomRoomProperty',
        # 'OneToOneChat': 'custom_implementation_test_app.CustomOneToOneChat',
        'Channel': 'custom_implementation_test_app.CustomChannel',
    },
    'SERIALIZERS': {
        'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer',
        'GroupChatSerializer': 'custom_implementation_test_app.serializers.CustomGroupChatSerializer',
        'GroupChatListSerializer': 'custom_implementation_test_app.serializers.CustomGroupChatListSerializer',
        'ChannelSerializer': 'custom_implementation_test_app.serializers.CustomChannelSerializer',
        'RoomPropertySerializer': 'custom_implementation_test_app.serializers.CustomRoomPropertySerializer',
        
    },
    'EVENT_HANDLER_CLASS': 'custom_implementation_test_app.handlers.CustomEventHandler',
    'PERMISSION_HANDLER_CLASS': 'custom_implementation_test_app.permissions.CustomPermissionHandler',
}
