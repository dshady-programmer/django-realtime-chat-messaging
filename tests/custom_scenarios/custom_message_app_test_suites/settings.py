from tests.settings import *

"""
Custom Message Only

This settings file demonstrates overriding only the Message model
while keeping all other models as defaults.
"""

INSTALLED_APPS += [
    'custom_message_app',

]

# Override only Message model and its serializer
REALTIME_CHAT_MESSAGING = {
    'MODELS': {
        'Message': 'custom_message_app.CustomMessage',
    },
    'SERIALIZERS': {
        'MessageSerializer': 'custom_message_app.serializers.CustomMessageSerializer',
    }
}
