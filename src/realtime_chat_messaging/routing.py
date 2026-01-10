from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("messaging/", consumers.ChatMessagingConsumer.as_asgi())
    
]
