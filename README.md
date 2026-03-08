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
- **XSS-safe content** — all message bodies sanitized with `bleach`
- **Everything is swappable** — models, serializers, handlers, permissions, consumer, and URL path

## Requirements

- Python ≥ 3.11
- Django ≥ 4.2
- Redis (production channel layer and cache)

## Installation

```bash
pip install django-realtime-chat-messaging django-channels-jwt-auth-middleware djangorestframework-simplejwt
```

## Quick Setup

### 1. `settings.py`

```python
INSTALLED_APPS = [
    "daphne",                         # serves ASGI — omit if using Uvicorn/Hypercorn
    "channels",                       # required
    "django.contrib.admin",
    "django.contrib.auth",
    "polymorphic",                    # required — do not omit
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "guardian",                       # required — do not omit
    "rest_framework",                 # required
    "realtime_chat_messaging",        # required
    # ... your own apps
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

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
}
```

> **Note:** `"polymorphic"` and `"guardian"` must be in `INSTALLED_APPS` even if
> you are not using them directly. Missing either will cause migration or runtime errors.

> **Note:** `"daphne"` is only required if you are using Daphne as your ASGI
> server. If you prefer Uvicorn or Hypercorn, omit it from `INSTALLED_APPS` and
> start your server manually instead.

### 2. `asgi.py`

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

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
```

### 3. Add JWT token endpoints to `urls.py`

```python
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view()),
    path("api/token/refresh/", TokenRefreshView.as_view()),
]
```

### 4. Migrate and run

```bash
python manage.py migrate
python manage.py runserver
```

### 5. Create users and obtain a token

Create at least two users (you need two to test a chat):

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
User = get_user_model()

alice = User.objects.create_user(username="alice", password="secret123")
bob   = User.objects.create_user(username="bob",   password="secret123")

print(alice.id, bob.id)  # note the IDs
```

Obtain a token for Alice:

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}'
# → {"access": "<token>", "refresh": "..."}
```

### 6. Connect and send a message

```javascript
const token = "<your_access_token>";
const ws = new WebSocket(`ws://localhost:8000/messaging/?token=${token}`);

ws.onopen = () => {
  // Create a one-to-one chat with Bob (use Bob's actual user ID)
  ws.send(JSON.stringify({
    event_type: "room.create",
    data: { type: "OneToOneChat", participants: [2] }
  }));
};

ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

Once you have a room ID from the `roomcreate.dispatch` response:

```javascript
ws.send(JSON.stringify({
  event_type: "message.send",
  data: { room_id: "<room_uuid>", content: "Hello! 👋" }
}));
```

> **Important:** The token must be passed as a query parameter in the WebSocket
> URL (`?token=<your_access_token>`). There is no separate authentication step —
> omitting the token will cause the server to close the connection immediately.

### Testing with WebSocket King

Prefer a visual tool? [WebSocket King](https://websocketking.com) is a
browser-based WebSocket client that requires no setup.

1. Go to [websocketking.com](https://websocketking.com)
2. Enter your connection URL — **include the token**:
   ```
   ws://localhost:8000/messaging/?token=<your_access_token>
   ```
3. Click **Connect**, then paste and send JSON events:
   ```json
   {"event_type": "room.create", "data": {"type": "OneToOneChat", "participants": [2]}}
   ```

## Usage

All communication is over a single WebSocket connection using a structured event
protocol. Events sent to the server use `snake_case`; events dispatched by the
server use `camelCase`.

```javascript
// Send a message
ws.send(JSON.stringify({
  event_type: "message.send",
  data: { room_id: "<room_uuid>", content: "Hello! 👋" }
}));

// React to a message
ws.send(JSON.stringify({
  event_type: "message.react",
  data: { message_id: "<message_uuid>", reaction_content: "👍" }
}));

// List your rooms
ws.send(JSON.stringify({ event_type: "room.list", data: {} }));
```

See the [full event reference](https://django-realtime-chat-messaging.readthedocs.io/en/latest/websocket_events.html)
for all available events.

## Documentation

Full documentation at [Read the Docs](https://django-realtime-chat-messaging.readthedocs.io).

Includes:

- Complete WebSocket event reference
- Custom models guide (including migration fix)
- Custom handlers, serializers, permissions, and consumer
- Push notification integration
- Deployment guide

## License

Apache 2.0 — see [LICENSE](LICENSE).