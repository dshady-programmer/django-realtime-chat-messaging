# Django Realtime Chat Messaging

A Django package that provides a structured, reusable real‑time chat system built on **Django Channels**. It abstracts common WebSocket patterns (rooms, messages, permissions, notifications) while remaining configurable and extensible.

This project focuses on **correctness, clarity, and maintainability**.

---

## Overview

Building real‑time chat in Django usually involves:

* Writing and maintaining WebSocket consumers
* Managing routing and permissions manually
* Duplicating logic for rooms, messages, and notifications

This package centralizes those concerns and exposes them through a consistent event‑based WebSocket API.

It provides:

* Predefined WebSocket consumers
* Multiple room types (private, group, broadcast)
* Message lifecycle management (send, edit, delete, react, read)
* Object‑level permission handling via `django-guardian`
* Swappable models, serializers, and event handlers

---

## Supported Chat Types

* **OneToOneChat** – private conversations between two users
* **GroupChat** – multi‑user rooms with admins and membership control
* **Channel** – broadcast‑style rooms with moderators and subscribers

---

## Installation

```bash
pip install django-realtime-chat-messaging
```

---

## Basic Setup

### 1. Installed Apps

```python
# settings.py
INSTALLED_APPS = [
    "daphne",  # must be before django.contrib.staticfiles
    "channels",
    "rest_framework",
    "polymorphic",
    "guardian",
    "realtime_chat_messaging",
]

ASGI_APPLICATION = "myproject.asgi.application"
```

### 2. Channel Layer (Development)

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}
```

> Use Redis in production (see below).

### 3. Authentication Backends

```python
AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)
```

---

## ASGI Configuration

```python
# myproject/asgi.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack
from realtime_chat_messaging.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
```

---

## Database Setup

```bash
python manage.py migrate
python manage.py runserver
```

---

## WebSocket Usage

### Connecting

```javascript
const socket = new WebSocket(
    "ws://localhost:8000/messaging/?token=<jwt_token>"
);

socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    console.log(payload);
};
```

---

## Room Creation Examples

### One‑to‑One Chat

```javascript
socket.send(JSON.stringify({
    "event_type": "room.create",
    "data": {
        "type": "OneToOneChat",
        "participants": [2]
    }
}));
```

### Group Chat

```javascript
socket.send(JSON.stringify({
    "event_type": "room.create",
    "data": {
        "type": "GroupChat",
        "name": "Team",
        "participants": [2, 3, 4]
    }
}));
```

### Channel

```javascript
socket.send(JSON.stringify({
    "event_type": "room.create",
    "data": {
        "type": "Channel",
        "name": "Announcements",
        "is_public": true
    }
}));
```

---

## Messaging

### Send Message

```javascript
socket.send(JSON.stringify({
    "event_type": "message.send",
    "data": {
        "room_id": "room-uuid",
        "content": "Hello world"
    }
}));
```

### Reply to Message

```javascript
socket.send(JSON.stringify({
    "event_type": "message.send",
    "data": {
        "room_id": "room-uuid",
        "content": "Replying here",
        "parent_message_id": "message-uuid"
    }
}));
```

### React to Message

```javascript
socket.send(JSON.stringify({
    "event_type": "message.react",
    "data": {
        "type": "add",
        "message_id": "message-uuid",
        "reaction_content": "👍"
    }
}));
```

### Mark as Read

```javascript
socket.send(JSON.stringify({
    "event_type": "message.read",
    "data": {
        "message_id": ["msg-1", "msg-2"]
    }
}));
```

---

## Media Attachments

```javascript
socket.send(JSON.stringify({
    "event_type": "message.send",
    "data": {
        "room_id": "room-uuid",
        "content": "Design draft",
        "extra_fields": {
            "media": [
                {
                    "media_url": "https://cdn.example.com/image.jpg",
                    "media_type": "image",
                    "mime_type": "image/jpeg",
                    "file_size": 204800,
                    "metadata": {
                        "width": 1920,
                        "height": 1080
                    }
                }
            ]
        }
    }
}));
```

---

## Customization

### Custom Message Model

```python
from realtime_chat_messaging.model_mixins import AbstractMessage
from django.db import models

class CustomMessage(AbstractMessage):
    priority = models.CharField(max_length=10, default="normal")
    is_pinned = models.BooleanField(default=False)

    class Meta:
        swappable = "REALTIME_CHAT_MESSAGING_MESSAGE_MODEL"
```

```python
# settings.py
REALTIME_CHAT_MESSAGING = {
    "MODELS": {
        "Message": "myapp.CustomMessage"
    }
}
```

---

### Custom Serializer

```python
from realtime_chat_messaging.serializers import MessageSerializer

class CustomMessageSerializer(MessageSerializer):
    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ["priority", "is_pinned"]
```

```python
REALTIME_CHAT_MESSAGING = {
    "SERIALIZERS": {
        "MessageSerializer": "myapp.serializers.CustomMessageSerializer"
    }
}
```

---

## Redis (Production)

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)]
        }
    }
}
```

---

## JWT Authentication (Optional)

```bash
pip install djangochannelsrestframework djangochannels-jwt-auth-middleware
```

```python
from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    )
})
```

---

## Testing

```python
from channels.testing import WebsocketCommunicator
from realtime_chat_messaging.consumers import ChatMessagingConsumer

async def test_message_send():
    communicator = WebsocketCommunicator(
        ChatMessagingConsumer.as_asgi(),
        "/messaging/"
    )

    connected, _ = await communicator.connect()
    assert connected

    await communicator.send_json_to({
        "event_type": "message.send",
        "data": {
            "room_id": "room-uuid",
            "content": "Test"
        }
    })

    response = await communicator.receive_json_from()
    assert response["eventType"] == "message.dispatch"
```

---

## Security Notes

* HTML content is sanitized using `bleach`
* All actions are guarded by object‑level permissions
* Database access relies exclusively on the Django ORM

---

## Requirements

* Python 3.8+
* Django 3.2+
* Django Channels 3+
* Redis (recommended for production)

Dependencies are installed automatically.

---

## License

MIT License. See `LICENSE` for details.

---


## Built with:
- [Django Channels](https://channels.readthedocs.io/) - WebSocket support
- [django-polymorphic](https://django-polymorphic.readthedocs.io/) - Polymorphic models
- [django-guardian](https://django-guardian.readthedocs.io/) - Object permissions

## 📞 Support

- **Documentation**: [Read the Docs](https://django-realtime-chat-messaging.readthedocs.io/)
- **Issues**: [GitHub Issues](https://github.com/shady-cj/django-realtime-chat-messaging/issues)
- **Discussions**: [GitHub Discussions](https://github.com/shady-cj/django-realtime-chat-messaging/discussions)