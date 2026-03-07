"""
Settings for Scenario 5: Custom Consumer Extension

This demonstrates using a custom consumer that extends ChatMessagingConsumer
without overriding any models. All models remain default.
"""
from tests.settings import *

# Add custom app to INSTALLED_APPS
INSTALLED_APPS = INSTALLED_APPS + [
    'custom_consumer_app',
]

# Optional: Add custom settings for consumer features
REALTIME_CHAT_MESSAGING = {
   "EVENT_MAPPER": "custom_consumer_app.event_mapper.custom_event_mapper",
   "CHAT_CONSUMER_CLASS": "custom_consumer_app.consumers.CustomChatConsumer"
}

