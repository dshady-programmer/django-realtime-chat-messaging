"""
Settings for Scenario 1: Custom Message Only

This settings file demonstrates overriding only the Message model
while keeping all other models as defaults.
"""
from tests.settings import *

# Add custom app to INSTALLED_APPS
INSTALLED_APPS = INSTALLED_APPS + [
    'scenario_1_custom_message_only.custom_message_app',
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
