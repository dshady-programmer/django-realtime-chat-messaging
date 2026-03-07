from django.urls import path

from realtime_chat_messaging.conf import realtime_chat_settings
from realtime_chat_messaging.utils.loader import import_and_verify_type_class

websocket_urlpatterns = [
    path(realtime_chat_settings.WEBSOCKET_PATH, import_and_verify_type_class(realtime_chat_settings.CHAT_CONSUMER_CLASS, "CHAT_CONSUMER_CLASS").as_asgi())
    
]
