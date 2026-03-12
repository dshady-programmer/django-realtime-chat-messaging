Introduction
============

**django-realtime-chat-messaging** is a reusable Django package that adds
production-ready real-time chat to any existing Django application. Connect a
WebSocket, configure Django Channels, and you get three chat room types, message
reactions, read receipts, delivery tracking, push notification scaffolding,
multi-device session support, and a granular permission system. No chat business
logic required.

What It Does
------------

The package exposes a single WebSocket endpoint (``ws://<host>/messaging/`` by
default). All chat interactions happen over that connection using a structured
event protocol. Your frontend sends events like ``message.send`` or
``room.create``; the server responds with dispatches like ``message.dispatch`` or
``roomcreate.dispatch`` broadcast to all relevant participants.

Under the hood the package manages:

- **Three room types.** Private one-to-one chats, multi-user group chats, and
  broadcast channels. All three are backed by a single polymorphic ``Room`` table
  so you can query across types in one query.
- **Full message lifecycle.** Create, reply, forward, edit, and delete (soft or
  hard), with XSS-safe HTML sanitisation on every message body.
- **Reactions.** One reaction per user per message, automatically replacing the
  previous one via database signals.
- **Read receipts and delivery tracking.** Per-message, per-user, with bulk
  operations supported.
- **Push notification scaffolding.** A ``ChatNotification`` model that tracks
  undelivered messages per recipient, designed to plug into Firebase, AWS SNS,
  or any push provider.
- **Multi-device sessions.** Every WebSocket connection is a tracked ``Session``;
  messages reach all of a user's active connections simultaneously.
- **Object-level permissions.** Powered by ``django-guardian``, group admins and
  channel moderators receive granular permissions automatically via signals.

What It Does Not Do
-------------------

- It does not store media files. ``MessageMediaAsset`` stores a URL you provide
  after uploading to your own storage backend (S3, Cloudflare R2, etc.).
- It does not send push notifications. It creates the data your own notification
  service needs to do so.
- It does not expose REST endpoints. Everything is WebSocket-only.
- It does not handle user authentication. It delegates entirely to whatever
  authentication middleware you place in your ASGI stack.

Design Philosophy
-----------------

Every major component (models, serializers, event handlers, permission handlers,
the consumer itself, and the WebSocket URL path) is swappable via settings. You
can adopt the package with zero custom code and have chat working in minutes, or
you can override only the pieces you need without touching the rest. Nothing
requires you to fork or modify the package source.

Requirements
------------

- Python 3.11 or higher
- Django 4.2 or higher
- Redis (for production channel layer and cache)

For the full dependency list see :doc:`installation`.