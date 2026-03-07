# django-realtime-chat-messaging

A reusable Django package that adds fully functional, production-ready real-time
chat to any existing application. Connect a WebSocket, configure Django Channels,
and you get private chats, group chats, broadcast channels, reactions, read
receipts, delivery tracking, push notification scaffolding, and multi-device
session support — without writing any chat business logic yourself.

## Features

- **Three room types** — private one-to-one chats, group chats, and broadcast channels
- **Full message lifecycle** — create, reply, forward, edit, and delete (soft or hard)
- **Reactions** — one reaction per user per message, auto-replacing via signals
- **Read receipts and delivery tracking** — per message, per user, with bulk support
- **Push notification scaffolding** — integrates with Firebase, AWS SNS, or any provider
- **Multi-device sessions** — all active connections receive every message simultaneously
- **Object-level permissions** — via `django-guardian`, automatically managed via signals
- **XSS-safe content** — all message bodies sanitised with `bleach`
- **Everything is swappable** — models, serializers, handlers, permissions, consumer, and URL path

## Installation

```bash
pip install django-realtime-chat-messaging
```

## Quick Setup

**`settings.py`**
```python
INSTALLED_APPS = [
    "daphne",
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "polymorphic",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "guardian",
    "realtime_chat_messaging",
]

ASGI_APPLICATION = "yourproject.asgi.application"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}  # use Redis in production
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "chat-dev",
    }
}
```

**`asgi.py`**
```python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yourproject.settings")
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from realtime_chat_messaging.routing import websocket_urlpatterns
from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
```

**Migrate and run**
```bash
python manage.py migrate
python manage.py runserver
```

Connect at `ws://localhost:8000/messaging/` with a valid auth token.

## Usage

All communication is over a single WebSocket connection using a structured event protocol.

```javascript
// Create a one-to-one chat
ws.send(JSON.stringify({
  event_type: "room.create",
  data: { type: "OneToOneChat", participants: [2] }
}));

// Send a message
ws.send(JSON.stringify({
  event_type: "message.send",
  data: { room_id: "<room_uuid>", content: "Hello! 👋" }
}));
```

## Requirements

- Python ≥ 3.11
- Django ≥ 4.2
- Redis (production)

## Documentation

Full documentation at [Read the Docs](https://django-realtime-chat-messaging.readthedocs.io).

Includes:
- Quickstart guide
- Complete WebSocket event reference
- Custom models guide (with migration fix)
- Custom handlers, serializers, permissions, and consumer
- Deployment guide

## License

Apache 2.0 — see [LICENSE](LICENSE).
