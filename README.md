# Django Realtime Chat Package

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-4.2%2B-green.svg)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Development Status](https://img.shields.io/badge/status-in%20development-yellow.svg)]()

A production-ready, reusable Django application that provides comprehensive real-time messaging functionality out of the box. Build chat applications faster by abstracting away the complexity of WebSocket connections, message persistence, and real-time features.

> **⚠️ Development Status**: This package is currently under active development as part of a capstone project. Features are being implemented weekly. Expected completion: [Your completion date]

---

## 🚀 Features

### Core Messaging
- ✅ **Multiple Chat Types**: One-to-one conversations, group chats, and broadcast channels
- ✅ **Real-time Delivery**: WebSocket-based instant messaging using Django Channels
- ✅ **Message Threading**: Reply to specific messages with parent-child relationships
- ✅ **Message Forwarding**: Forward messages between conversations with smart restrictions
- ✅ **Rich Media Support**: Images, videos, documents, stickers, and GIFs with metadata
- ✅ **Message Management**: Edit and soft-delete messages

### Social Features
- ✅ **Emoji Reactions**: React to messages with emoji tracking
- ✅ **Read Receipts**: Track which users have read specific messages
- ✅ **Typing Indicators**: Real-time typing status broadcasts
- ✅ **Online Presence**: User online/away/offline status
- ✅ **Notifications**: Categorized notifications for replies, mentions, and reactions

### Technical Features
- ✅ **WebSocket-Only Architecture**: All operations via real-time events
- ✅ **Polymorphic Rooms**: Flexible room model supporting different chat types
- ✅ **Redis Caching**: Performance optimization for frequent queries
- ✅ **Auto Cleanup**: Automatic WebSocket channel layer management
- ✅ **Token Authentication**: Configurable token-based auth
- ✅ **Signal-Based Cache Invalidation**: Keep cached data fresh
- ✅ **Extensible Design**: Easy to customize and extend

### Optional Features
- 🔒 **End-to-End Encryption**: Available in enhanced version `[encryption]` extra

---

## 📋 Requirements

- Python 3.8+
- Django 4.2+
- Redis 4.0+
- Django Channels 4.0+

---

## 🎯 Project Goals

This package aims to solve a common pain point in Django development: implementing real-time messaging is time-consuming and requires significant boilerplate code. Instead of rebuilding chat functionality for every project, developers can:

1. Install via `pip install django-realtime-chat-package`
2. Configure basic settings (Django Channels, Redis, ASGI)
3. Immediately access comprehensive messaging features
4. Extend and customize as needed

---

## 🏗️ Architecture Overview

### Database Models

**Polymorphic Room System**
```
Room (Base Model)
├── OneToOneChat (Direct messaging)
├── GroupChat (Multi-user conversations)
└── Channel (Broadcast channels)
```

**Supporting Models**
- **Message**: Stores all messages with threading and forwarding support
- **ReadReceipt**: Tracks message read status per user
- **Reaction**: Emoji reactions with user tracking
- **Notification**: User notification management
- **Interaction**: Tracks message engagement (replies, reactions, forwards)
- **MessageMediaAsset**: Media attachments with metadata

### WebSocket API

**Connection**: `/ws/chat/{room_id}/?token={auth_token}`

**Event Categories** (45 total events):
- Connection Management (2 events)
- Room Management (8 events)
- Message Operations (6 events)
- Media Handling (2 events)
- Reactions (3 events)
- Read Receipts (2 events)
- Notifications (2 events)
- Presence & Typing (2 events)
- Server Broadcasts (18 events)

---

## 🛠️ Installation

> **Note**: Installation instructions will be finalized upon first release

```bash
# Standard version
pip install django-realtime-chat-package

# Enhanced version with encryption
pip install django-realtime-chat-package[encryption]
```

### Basic Configuration

**1. Add to INSTALLED_APPS**
```python
INSTALLED_APPS = [
    # ...
    'channels',
    'django_realtime_chat_package',
    # ...
]
```

**2. Configure Channel Layers (Redis)**
```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

**3. Update ASGI Configuration**
```python
# asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django_realtime_chat_package.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

**4. Run Migrations**
```bash
python manage.py migrate django_realtime_chat_package
```

---

## 📖 Usage Examples

> **Note**: Detailed usage examples will be added as features are implemented

### Creating a One-to-One Chat
```python
# Coming soon
```

### Sending a Message via WebSocket
```javascript
// Coming soon
```

### Handling Real-time Events
```javascript
// Coming soon
```

---

## ⚙️ Configuration

Available settings for customization:

```python
# settings.py

# Authentication token keyword (default: 'token')
CHAT_TOKEN_KEYWORD = 'token'

# Maximum message length (default: 5000)
CHAT_MAX_MESSAGE_LENGTH = 5000

# Media upload path (default: 'chat/media/')
CHAT_MEDIA_UPLOAD_PATH = 'chat/media/'

# Enable encryption features (default: False)
CHAT_ENABLE_ENCRYPTION = False

# Cache timeout in seconds (default: 300)
CHAT_CACHE_TIMEOUT = 300

# Maximum upload size in bytes (default: 10MB)
CHAT_MAX_UPLOAD_SIZE = 10485760

# Typing indicator timeout (default: 3 seconds)
CHAT_TYPING_TIMEOUT = 3
```

---

## 🗓️ Development Roadmap

### ✅ Week 1: Foundation (Completed)
- [x] Project planning and architecture design
- [x] ERD diagram creation
- [x] WebSocket API event documentation

### 🔄 Week 2: Database Layer (In Progress)
- [ ] Implement all 9 database models
- [ ] Create migrations
- [ ] Write model unit tests (50+ test cases)
- [ ] Set up Django admin interface
- [ ] Configure Redis and Channels

### 📅 Week 3: WebSocket Implementation (Upcoming)
- [ ] Build WebSocket consumer with event routing
- [ ] Implement connection/disconnection handling
- [ ] Create authentication middleware
- [ ] Implement message events (6 events)
- [ ] Implement room management events (8 events)
- [ ] Add typing indicators and presence

### 📅 Week 4: Advanced Features (Upcoming)
- [ ] Implement reaction events (3 events)
- [ ] Implement read receipt events (2 events)
- [ ] Implement notification system (2 events)
- [ ] Add media handling (2 events)
- [ ] Build Redis caching layer
- [ ] Create signal handlers for cache invalidation
- [ ] Performance testing and optimization

### 📅 Week 5: Documentation & Release (Upcoming)
- [ ] Write comprehensive documentation
- [ ] Create demo Django project
- [ ] Build example JavaScript WebSocket client
- [ ] Implement encryption features (enhanced version)
- [ ] Final testing (integration, security, performance)
- [ ] Prepare PyPI package
- [ ] Record demo video

---

## 🧪 Testing

```bash
# Run all tests
python manage.py test django_realtime_chat_package

# Run with coverage
coverage run --source='django_realtime_chat_package' manage.py test
coverage report
```

**Testing Goals**:
- 80%+ code coverage
- Unit tests for all models and serializers
- Integration tests for WebSocket events
- Performance tests for concurrent connections
- Security tests for authentication and permissions

---

## 🤝 Contributing

This is currently a capstone project and not open for external contributions. However, feedback and suggestions are welcome!

**Found a bug or have a suggestion?**
- Open an issue on GitHub
- Provide detailed description and reproduction steps

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎓 About This Project

This package is being developed as a capstone project to demonstrate:
- Django application architecture and best practices
- Real-time WebSocket communication with Django Channels
- Database design with polymorphic models
- Performance optimization with caching strategies
- Comprehensive testing and documentation

**Developer**: [Your Name]  
**Institution**: [Your Institution]  
**Project Duration**: 5 weeks  
**Expected Completion**: [Date]

---

## 📚 Documentation

- [Installation Guide](docs/installation.md) *(Coming soon)*
- [WebSocket API Reference](docs/api-reference.md) *(Coming soon)*
- [Configuration Guide](docs/configuration.md) *(Coming soon)*
- [Usage Examples](docs/examples.md) *(Coming soon)*
- [Extension Guide](docs/extending.md) *(Coming soon)*
- [Troubleshooting](docs/troubleshooting.md) *(Coming soon)*

---

## 🔮 Future Enhancements

Features planned for post-capstone development:

- 📞 **Voice/Video Calls**: WebRTC signaling support
- 🔍 **Message Search**: Full-text search with Elasticsearch
- 🌐 **Message Translation**: Automatic language translation
- ⏰ **Scheduled Messages**: Send messages at specific times
- 🤖 **Bots & Webhooks**: Chatbot and external integrations
- 📊 **Analytics Dashboard**: Usage statistics and engagement metrics
- 📱 **Push Notifications**: Firebase Cloud Messaging integration
- 📌 **Message Pinning**: Pin important messages in rooms
- 🚫 **User Blocking**: User safety and moderation features
- 🛡️ **Advanced Moderation**: Automated content filtering
- 📥 **Export Chat History**: Export in PDF, JSON, CSV formats
- 🎤 **Voice Messages**: Record and send audio messages
- 🔗 **Link Previews**: Automatic metadata extraction

---

## 📞 Support

For questions or support during development:
- **GitHub Issues**: [Project Issues Page]
- **Email**: [Your Email]
- **Documentation**: [Link to documentation when available]

---

## 🙏 Acknowledgments

- Django Software Foundation for the amazing framework
- Django Channels team for WebSocket support
- Redis team for the blazing-fast cache backend
- [Your mentors/advisors] for guidance and support

---

**⭐ Star this repo if you find it interesting!**

*Last Updated: [Current Date]*