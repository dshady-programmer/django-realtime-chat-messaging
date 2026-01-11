Django Realtime Chat Messaging Documentation
============================================

**Django Realtime Chat Messaging** is a production-ready Django package that adds real-time chat functionality to your application with minimal setup. Simply configure Django Channels, and you're ready to go—no additional WebSocket code required!

.. image:: https://img.shields.io/pypi/v/django-realtime-chat-messaging.svg
   :target: https://pypi.org/project/django-realtime-chat-messaging/
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/django-realtime-chat-messaging.svg
   :target: https://pypi.org/project/django-realtime-chat-messaging/
   :alt: Python versions

.. image:: https://img.shields.io/badge/django-3.2%20%7C%204.0%20%7C%204.1%20%7C%204.2%20%7C%205.0-blue.svg
   :target: https://www.djangoproject.com/
   :alt: Django versions

.. image:: https://readthedocs.org/projects/django-realtime-chat-messaging/badge/?version=latest
   :target: https://django-realtime-chat-messaging.readthedocs.io/
   :alt: Documentation Status

Why Choose This Package?
-------------------------

Most real-time chat solutions require extensive setup: custom WebSocket consumers, routing configuration, permission systems, and complex frontend integration. **Django Realtime Chat Messaging** eliminates all that complexity.

✨ **Key Features**

* **Zero Additional Code**: Just configure Django Channels and start chatting
* **Three Room Types**: OneToOneChat, GroupChat, and Channels (broadcast)
* **Rich Messaging**: Replies, forwarding, reactions, read receipts, typing indicators
* **Media Support**: Store urls of Images, videos, audio, documents with metadata
* **Granular Permissions**: Object-level permissions with django-guardian
* **Fully Customizable**: Swap models, serializers, handlers, and permissions
* **Production Ready**: Scales with Redis, handles concurrent connections

Quick Example
-------------

After installation and basic Django Channels setup:

.. code-block:: javascript

   // Connect to WebSocket
   const socket = new WebSocket('ws://localhost:8000/messaging/');
   
   // Create a one-to-one chat
   socket.send(JSON.stringify({
       event_type: "room.create",
       data: {
           type: "OneToOneChat",
           participants: [2]  // Other user"s ID
       }
   }));
   
   // Send a message
   socket.send(JSON.stringify({
       event_type: "message.send",
       data: {
           room_id: "room-uuid",
           content: "Hello, world! 👋"
       }
   }));

That's it! You now have fully functional real-time chat with persistence, permissions, and all features.

The Three Room Types
--------------------

**OneToOneChat**
   Private conversations between exactly two users. Perfect for direct messages, customer support, or private discussions.

**GroupChat**
   Group conversations with multiple participants, admins, and granular permissions. Ideal for team collaboration, project discussions, or social groups.

**Channel**
   Broadcast channels where only moderators can post (like Telegram channels). Perfect for announcements, news feeds, or community updates.

What Makes This Different?
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Feature
     - Traditional Approach
     - This Package
   * - WebSocket Code
     - Write custom consumers
     - ✅ Pre-built, ready to use
   * - Room Management
     - Implement yourself
     - ✅ Three types included
   * - Permissions
     - Custom permission system
     - ✅ Object-level built-in
   * - Message Features
     - Build from scratch
     - ✅ Replies, reactions, receipts
   * - Scaling
     - Figure it out
     - ✅ Redis-ready
   * - Customization
     - Fork and modify
     - ✅ Swappable components

Documentation Contents
----------------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/installation
   getting-started/quickstart
   getting-started/concepts
   getting-started/minimal-example

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/authentication
   user-guide/room-types
   user-guide/messages
   user-guide/permissions
   user-guide/notifications
   user-guide/frontend-integration

.. toctree::
   :maxdepth: 2
   :caption: Customization

   customization/models
   customization/serializers
   customization/handlers
   customization/consumers
   customization/permissions
   customization/settings

.. toctree::
   :maxdepth: 2
   :caption: Advanced Topics

   advanced/architecture
   advanced/scaling
   advanced/performance
   advanced/testing
   advanced/security

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api-reference/events
   api-reference/models
   api-reference/serializers
   api-reference/permissions
   api-reference/settings

.. toctree::
   :maxdepth: 2
   :caption: Deployment

   deployment/production-checklist
   deployment/redis
   deployment/docker
   deployment/nginx
   deployment/monitoring

.. toctree::
   :maxdepth: 1
   :caption: Additional Information

   troubleshooting
   faq
   changelog
   contributing

Indices and Tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Community & Support
===================

* **GitHub**: `Report issues and contribute <https://github.com/yourusername/django-realtime-chat-messaging>`_
* **Stack Overflow**: Tag questions with ``django-realtime-chat-messaging``
* **Discussions**: `Join the conversation <https://github.com/yourusername/django-realtime-chat-messaging/discussions>`_

Quick Links
===========

* :doc:`getting-started/quickstart` - Get started in 10 minutes
* :doc:`api-reference/events` - Complete WebSocket event reference
* :doc:`customization/models` - Extend models and add custom fields
* :doc:`deployment/production-checklist` - Deploy to production
* :doc:`troubleshooting` - Common issues and solutions

License
=======

This project is licensed under the MIT License - see the LICENSE file for details.