# Django Realtime Chat Messaging

<!-- [![PyPI version](https://badge.fury.io/py/django-realtime-chat-messaging.svg)](https://badge.fury.io/py/django-realtime-chat-messaging)
[![Python versions](https://img.shields.io/pypi/pyversions/django-realtime-chat-messaging.svg)](https://pypi.org/project/django-realtime-chat-messaging/)
[![Django versions](https://img.shields.io/badge/django-3.2%20%7C%204.0%20%7C%204.1%20%7C%204.2%20%7C%205.0-blue.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE) -->

**The easiest way to add real-time chat to your Django application.** No WebSocket code required—just install, configure Django Channels, and start chatting.

## 🎯 Why This Package?

Most real-time chat solutions require writing custom WebSocket consumers, routing configuration, permission systems, and extensive frontend integration. **Django Realtime Chat Messaging** eliminates all that complexity:

- ✅ **Zero WebSocket Code** - Pre-built consumers handle everything
- ✅ **Three Chat Types** - OneToOne, GroupChat, Channels (broadcast)
- ✅ **Rich Features** - Replies, forwarding, reactions, read receipts, typing indicators
- ✅ **Media Support** - Images, videos, audio, documents
- ✅ **Granular Permissions** - Object-level permissions with django-guardian
- ✅ **Fully Customizable** - Models, serializers, handlers, permissions
- ✅ **Production Ready** - Scales with Redis, handles concurrent connections

## 🚀 Quick Start

### Installation

```bash
pip install django-realtime-chat-messaging
```

### Basic Setup (5 minutes)

**1. Add to INSTALLED_APPS:**

```python
# settings.py
INSTALLED_APPS = [
    'daphne',  # Must be BEFORE django.contrib.staticfiles
    'channels',
    'rest_framework',
    'polymorphic',
    'guardian',
    'realtime_chat_messaging',
    # ... your apps
]

ASGI_APPLICATION = 'myproject.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"  # Dev only
    }
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)
```

**2. Configure ASGI:**

```python
# myproject/asgi.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()  # IMPORTANT: Prevents AppRegistryNotReady errors

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack
from realtime_chat_messaging.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
```

**3. Run migrations:**

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

**4. Connect from frontend:**

```javascript
const socket = new WebSocket('ws://localhost:8000/messaging/');

socket.onopen = () => {
    // Create a one-to-one chat
    socket.send(JSON.stringify({
        event_type: 'room.create',
        data: {
            type: 'OneToOneChat',
            participants: [2]  // Other user's ID
        }
    }));
};

socket.onmessage = (e) => {
    const response = JSON.parse(e.data);
    console.log('Received:', response);
};
```

That's it! You now have real-time chat. 🎉

## 📚 Features

### Three Room Types

**OneToOneChat** - Private conversations between two users
```javascript
{ type: 'OneToOneChat', participants: [user_id] }
```

**GroupChat** - Group conversations with admins and permissions
```javascript
{ type: 'GroupChat', name: 'Team', participants: [2, 3, 4] }
```

**Channel** - Broadcast channels with moderators (like Telegram channels)
```javascript
{ type: 'Channel', name: 'Announcements', is_public: true }
```

### Rich Messaging

- **Text Messages** - HTML sanitization included (XSS protection)
- **Replies** - Thread-style conversations
- **Forwarding** - Forward messages across rooms
- **Media Attachments** - Images, videos, audio, documents
- **Message Editing** - Edit sent messages
- **Message Deletion** - Soft or hard delete (configurable)

### Engagement Features

- **Reactions** - Emoji reactions on messages
- **Read Receipts** - Track who read each message
- **Typing Indicators** - Real-time typing notifications
- **Delivery Status** - Track message delivery
- **Notifications** - Unread message tracking (integrates with push services)

### Permissions & Moderation

- **Object-Level Permissions** - Fine-grained access control
- **Admin/Moderator Roles** - GroupChat admins, Channel moderators
- **Permission Decorators** - Easy-to-use permission checks
- **Group Locking** - Restrict messaging to admins only
- **Member Management** - Add/remove members, transfer ownership

## 🎨 Complete Example

```javascript
// Create a group chat
socket.send(JSON.stringify({
    event_type: 'room.create',
    data: {
        type: 'GroupChat',
        name: 'Project Team',
        participants: [2, 3, 4],
        extra_fields: {
            max_participants: 50,
            join_approval_required: true
        }
    }
}));

// Send a message with media
socket.send(JSON.stringify({
    event_type: 'message.send',
    data: {
        room_id: 'room-uuid',
        content: 'Check out this design!',
        extra_fields: {
            media: [{
                media_url: 'https://cdn.example.com/image.jpg',
                media_type: 'image',
                mime_type: 'image/jpeg',
                file_size: 204800,
                metadata: {
                    width: 1920,
                    height: 1080
                }
            }]
        }
    }
}));

// Reply to a message
socket.send(JSON.stringify({
    event_type: 'message.send',
    data: {
        room_id: 'room-uuid',
        content: 'Looks great!',
        parent_message_id: 'message-uuid'  // Creates a reply thread
    }
}));

// React to a message
socket.send(JSON.stringify({
    event_type: 'message.react',
    data: {
        type: 'add',
        message_id: 'message-uuid',
        reaction_content: '👍'
    }
}));

// Mark messages as read
socket.send(JSON.stringify({
    event_type: 'message.read',
    data: {
        message_id: ['msg-uuid-1', 'msg-uuid-2']
    }
}));
```

## 🔧 Advanced: Customization

### Custom Models

Extend any model to add your own fields:

```python
# models.py
from realtime_chat_messaging.models import Message
from realtime_chat_messaging.model_mixins import AbstractMessage

class CustomMessage(AbstractMessage):
    priority = models.CharField(max_length=10, default='normal')
    is_pinned = models.BooleanField(default=False)
    
    class Meta:
        swappable = 'REALTIME_CHAT_MESSAGING_MESSAGE_MODEL'

# settings.py
REALTIME_CHAT_MESSAGING = {
    "MODELS": {
        "Message": "myapp.CustomMessage",
    }
}
```

### Custom Serializers

```python
# serializers.py
from realtime_chat_messaging.serializers import MessageSerializer as BaseMessageSerializer

class CustomMessageSerializer(BaseMessageSerializer):
    class Meta(BaseMessageSerializer.Meta):
        fields = BaseMessageSerializer.Meta.fields + ['priority', 'is_pinned']

# settings.py
REALTIME_CHAT_MESSAGING = {
    "SERIALIZERS": {
        "MessageSerializer": "myapp.serializers.CustomMessageSerializer",
    }
}
```

### Custom Events

```python
# consumers.py
from realtime_chat_messaging.consumers import ChatMessagingConsumer

class CustomChatConsumer(ChatMessagingConsumer):
    
    @ExceptionHandler.exception_handler_decorator
    async def receive_pin_message_event(self, data):
        # Your custom logic
        message = await self.pin_message(data['message_id'])
        await self.send_group(
            f"group-{data['room_id']}", 
            "message.pinned", 
            message
        )

# routing.py
from myapp.consumers import CustomChatConsumer

websocket_urlpatterns = [
    path("messaging/", CustomChatConsumer.as_asgi())
]

# variables/consumers.py
def custom_event_mapper(self):
    default = map_event_type_to_handlers(self)
    default['message.pin'] = self.receive_pin_message_event
    return default

# settings.py
REALTIME_CHAT_MESSAGING = {
    "EVENT_MAPPER": "myapp.consumers.custom_event_mapper"
}
```

## 📖 Documentation

- **[Full Documentation](https://django-realtime-chat-messaging.readthedocs.io/)** - Complete guides and API reference
- **[Quickstart Guide](https://django-realtime-chat-messaging.readthedocs.io/en/latest/getting-started/quickstart.html)** - Get started in 10 minutes
- **[Event Reference](https://django-realtime-chat-messaging.readthedocs.io/en/latest/api-reference/events.html)** - All WebSocket events
- **[Customization Guide](https://django-realtime-chat-messaging.readthedocs.io/en/latest/customization/)** - Extend the package
- **[Deployment Guide](https://django-realtime-chat-messaging.readthedocs.io/en/latest/deployment/)** - Production setup

## 🏗️ Architecture

```
┌─────────────┐
│   Frontend  │
│ (WebSocket) │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  ChatConsumer       │  ← WebSocket handler (no code needed!)
│  - Permissions      │
│  - Event routing    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Event Handlers     │  ← Business logic
│  - Message creation │
│  - Room management  │
│  - Notifications    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│  Models             │  ← Database (fully swappable)
│  - Room (polymorphic)
│  - Message          │
│  - ReadReceipt      │
└─────────────────────┘
```

## 🔐 Security Features

- **XSS Protection** - HTML sanitization with bleach
- **Permission Checks** - Object-level permissions on every action
- **SQL Injection Protection** - Django ORM

## 🚢 Production Setup

### Redis Configuration (Required)

```python
# settings.py
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

### JWT Authentication (Recommended)

```bash
pip install djangochannelsrestframework djangochannels-jwt-auth-middleware
```

```python
# asgi.py
from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter({
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
```

### Environment Variables

```python
# settings.py
REALTIME_CHAT_MESSAGING = {
    "MESSAGE_SOFT_DELETE": True,  # False = hard delete
    "ENABLE_NOTIFICATION": True,  # Track undelivered messages
}
```

## 🧪 Testing

```python
from channels.testing import WebsocketCommunicator
from realtime_chat_messaging.consumers import ChatMessagingConsumer

async def test_message_send():
    communicator = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
    connected, _ = await communicator.connect()
    assert connected
    
    await communicator.send_json_to({
        "event_type": "message.send",
        "data": {"room_id": room_id, "content": "Test"}
    })
    
    response = await communicator.receive_json_from()
    assert response["eventType"] == "message.dispatch"
```

## 📊 Performance

- **Optimized Queries** - `select_related` and `prefetch_related` throughout
- **Pagination** - Built-in message pagination
- **Caching** - Redis caching for user sessions and groups
- **Async/Await** - Non-blocking I/O
- **Database Indexes** - Indexed foreign keys and common queries

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md).

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 Requirements

- Python 3.8+
- Django 3.2+
- Django Channels 3.0+
- Redis (production)

**Dependencies (automatically installed):**
- `channels`
- `channels-redis`
- `daphne`
- `django-polymorphic`
- `django-guardian`
- `djangorestframework`
- `bleach`

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with:
- [Django Channels](https://channels.readthedocs.io/) - WebSocket support
- [django-polymorphic](https://django-polymorphic.readthedocs.io/) - Polymorphic models
- [django-guardian](https://django-guardian.readthedocs.io/) - Object permissions

## 📞 Support

- **Documentation**: [Read the Docs](https://django-realtime-chat-messaging.readthedocs.io/)
- **Issues**: [GitHub Issues](https://github.com/shady-cj/django-realtime-chat-messaging/issues)
- **Discussions**: [GitHub Discussions](https://github.com/shady-cj/django-realtime-chat-messaging/discussions)




## ⭐ Show Your Support

If this package helps your project, please give it a star on [GitHub](https://github.com/yourusername/django-realtime-chat-messaging)!

---

**Made with ❤️ for the Django community**