"""
ASGI config for django_realtime_chat_messaging project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

# import chat.routing
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_realtime_chat_messaging.settings")
# add this line is to ensure django is loaded for django_channels_jwt_auth_middlware.auth to work properly
django.setup()
# Then we can run daphne -b 0.0.0.0 -p 8000 django_realtime_chat_messaging.asgi:application with no AppRegistryNotReady("Apps aren't loaded yet.") error.


from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from realtime_chat_messaging.routing import websocket_urlpatterns

from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack



django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
