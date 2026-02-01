from .settings import *



REALTIME_CHAT_MESSAGING={
        'MODELS': {
            'Message': 'custom_implementation_test_app.CustomMessage',
            'GroupChat': 'custom_implementation_test_app.CustomGroupChat',
            'Session': 'custom_implementation_test_app.CustomSession',
        },
        'SERIALIZERS': {
            'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer',
            'GroupChatSerializer': 'custom_implementation_test_app.serializers.CustomGroupChatSerializer',
        },
        'EVENT_HANDLER_CLASS': 'custom_implementation_test_app.handlers.CustomEventHandler',
        'PERMISSION_HANDLER_CLASS': 'custom_implementation_test_app.permissions.CustomPermissionHandler',
    }