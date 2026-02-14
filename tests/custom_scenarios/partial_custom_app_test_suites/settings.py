"""
Settings for Scenario 4: Partial Override (Message + GroupChat)

This settings file demonstrates overriding only Message and GroupChat models
while keeping all other models as defaults.
"""
from tests.settings import *


INSTALLED_APPS += [
    'partial_custom_app',
]

# Override Message and GroupChat models and their serializers
REALTIME_CHAT_MESSAGING = {
    'MODELS': {
        'Message': 'partial_custom_app.CustomMessage',
        'GroupChat': 'partial_custom_app.CustomGroupChat',
    },
    'SERIALIZERS': {
        'MessageSerializer': 'partial_custom_app.serializers.CustomMessageSerializer',
        'GroupChatSerializer': 'partial_custom_app.serializers.CustomGroupChatSerializer',
        'GroupChatListSerializer': 'partial_custom_app.serializers.CustomGroupChatListSerializer',
    }
}
