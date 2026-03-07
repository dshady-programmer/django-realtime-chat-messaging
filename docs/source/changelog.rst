Changelog
=========

0.1.0 (2026-02-08)
-------------------

Initial release.

**Features**

- Three room types: ``OneToOneChat``, ``GroupChat``, ``Channel`` backed by a
  single polymorphic ``Room`` table.
- Full message lifecycle: create, reply, forward, edit, soft/hard delete.
- Message reactions (one per user per message, auto-replacing via signals).
- Read receipts and delivery tracking (``delivered_to`` M2M).
- Push notification scaffolding via ``ChatNotification`` model.
- Multi-device session tracking with inactivity-based cleanup.
- Object-level permissions via ``django-guardian`` for group admins and channel
  moderators.
- XSS sanitisation on all message content via ``bleach``.
- Recursive serialization for message replies and forwards.
- Polymorphic room serialization with ``django-rest-polymorphic``.
- All concrete models swappable via settings.
- All serializers replaceable via settings.
- Pluggable ``EventHandler``, ``PermissionHandler``, ``ExceptionHandler``, and
  consumer class.
- Configurable WebSocket URL path and event mapper.
- ``sqlite_safe_db_sync_to_async`` for SQLite compatibility under Django 6.0.
- Settings hot-reload support for ``@override_settings`` in tests.
- Media attachment support via ``MessageMediaAsset`` with MIME type validation.
- Room property (``RoomProperty``) for freeform preferences storage per room.
- Paginated message retrieval.
- Typing indicators (``message.typing``).
- Session heartbeat for connection keep-alive.
- GroupChat locking (``group_locked``), max member enforcement, and join approval
  flag.
- Channel visibility (``is_public``), max subscriber enforcement, and targeted
  send permissions.

**Dependencies**

- Django ≥ 4.2
- Python ≥ 3.11
- djangorestframework
- django-guardian
- django-polymorphic
- django-rest-polymorphic
- drf-recursive
- bleach
- channels
- channels-redis
- daphne
