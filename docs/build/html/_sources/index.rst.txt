Django Realtime Chat Messaging
===============================

**WebSocket chat infrastructure for Django applications**

Django Realtime Chat Messaging is a production-ready package that adds real-time chat capabilities to your Django project with minimal setup. Built on Django Channels, it provides a complete WebSocket-based messaging system that handles everything from one-on-one chats to large broadcast channels.

.. image:: https://img.shields.io/pypi/v/django-realtime-chat-messaging.svg
   :target: https://pypi.org/project/django-realtime-chat-messaging/
   :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/django-realtime-chat-messaging.svg
   :target: https://pypi.org/project/django-realtime-chat-messaging/
   :alt: Python Versions

.. image:: https://img.shields.io/pypi/djversions/django-realtime-chat-messaging.svg
   :target: https://pypi.org/project/django-realtime-chat-messaging/
   :alt: Django Versions

.. image:: https://img.shields.io/github/license/shady-cj/django-realtime-chat-messaging.svg
   :target: https://github.com/shady-cj/django-realtime-chat-messaging/blob/main/LICENSE
   :alt: License

Why Choose This Package?
-------------------------

Most real-time chat implementations require extensive WebSocket handling, message persistence logic, permission systems, and state management. **Django Realtime Chat Messaging** provides all of this out of the box, allowing you to focus on your application's unique features.

✨ **Zero Boilerplate** - Import one consumer, configure ASGI, and start chatting

🏗️ **Three Chat Types Built-In** - One-to-one, group chats, and broadcast channels

🔐 **Comprehensive Permissions** - Object-level permissions via django-guardian

💬 **Rich Messaging** - Replies, reactions, forwarding, media attachments, typing indicators

📱 **Production Ready** - Built for scale with Redis backend support

🎨 **Fully Customizable** - Override any behavior without forking

Quick Example
-------------

After installation and basic setup, your users can start chatting immediately:

.. code-block:: python

   # All you need in your routing.py
   from realtime_chat_messaging.routing import websocket_urlpatterns
   
   # Use in ASGI application
   application = ProtocolTypeRouter({
       "websocket": AuthMiddlewareStack(
           URLRouter(websocket_urlpatterns)
       ),
   })

That's it! The package handles:

- WebSocket connection management
- Message persistence and retrieval
- Room membership and permissions
- Real-time event broadcasting
- Typing indicators and read receipts
- Reactions and message threading

Chat Types Explained
---------------------

**OneToOneChat** - Private conversations between two users
   Perfect for direct messaging, customer support, or private discussions. Automatically prevents duplicate conversations between the same pair of users.

**GroupChat** - Multi-user conversations with admin controls
   Ideal for team discussions, project rooms, or community groups. Features include admins, member management, message permissions, and optional group locking.

**Channel** - Broadcast-style communication with moderated posting
   Great for announcements, public discussions, or large communities. Only moderators can post by default, but permissions can be granted to specific users.

What's Included vs What You Build
----------------------------------

**The Package Provides:**

- Complete WebSocket consumer with 14+ event handlers
- Database models for rooms, messages, reactions, and notifications
- Polymorphic room system (OneToOneChat, GroupChat, Channel)
- Permission decorators and helpers
- Message serialization and validation
- Real-time event broadcasting to room participants
- Read receipt and delivery tracking
- Typing indicator support

**You Provide:**

- Frontend implementation (React, Vue, vanilla JS, etc.)
- Authentication middleware for WebSocket connections
- UI/UX for chat interface
- File upload handling (if using media attachments)
- Push notification integration (optional)

Use Cases
---------

This package is perfect for:

- **SaaS Applications** - Add real-time team collaboration
- **Customer Support** - Build live chat support systems  
- **Social Platforms** - Enable user-to-user messaging
- **Educational Tools** - Create classroom discussion spaces
- **Gaming Platforms** - Implement in-game chat systems
- **Marketplaces** - Facilitate buyer-seller communication

Installation Preview
--------------------

.. code-block:: bash

   pip install django-realtime-chat-messaging

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       ...
       'channels',
       'realtime_chat_messaging',
   ]

   ASGI_APPLICATION = 'yourproject.asgi.application'
   
   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {"hosts": [('127.0.0.1', 6379)]},
       },
   }

.. code-block:: bash

   python manage.py migrate
   python manage.py runserver

See :doc:`quickstart` for the complete setup guide.

Documentation Contents
----------------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart
   understanding-room-types
   authentication-setup


.. toctree::
   :maxdepth: 2
   :caption: WebSocket API

   websocket/connection
   websocket/message-events
   websocket/room-events
   websocket/member-management
   websocket/error-codes


.. toctree::
   :maxdepth: 2
   :caption: Customization

   customization/overview
   customization/serializers
   customization/event-handlers
   customization/permissions
   customization/abstract-models
   customization/member-management
   customization/settings-reference


.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/models
   api/serializers
   api/consumers
   api/decorators
   api/signals

.. toctree::
   :maxdepth: 1
   :caption: Additional Resources

   configuration
   troubleshooting
   contributing
   changelog

Version Information
-------------------

.. warning::
   This is version 0.1.0. The API may change before reaching 1.0.0. We'll maintain backwards compatibility where possible and document breaking changes clearly.

**Current Limitations:**

- One active connection per user (multi-device support coming in v0.2.0)
- Message deletion requires explicit handling in frontend (soft delete vs hard delete)
- Group invite links not yet implemented (can be added via customization)

Support & Community
-------------------

- **Report bugs**: `GitHub Issues <https://github.com/shady-cj/django-realtime-chat-messaging/issues>`_
- **Source code**: `GitHub Repository <https://github.com/shady-cj/django-realtime-chat-messaging>`_
- **PyPI package**: `django-realtime-chat-messaging <https://pypi.org/project/django-realtime-chat-messaging/>`_

License
-------

This project is licensed under the MIT License - see the LICENSE file for details.

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`