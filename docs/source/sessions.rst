Sessions
========

The package tracks every active WebSocket connection as a ``Session`` record.
This enables multi-device support (a single user connected on multiple devices
simultaneously) and clean session management across reconnections.

How Sessions Work
-----------------

1. **On connect** — ``channel_cleanup()`` runs first, removing any expired
   session channel names from all channel groups (preventing message delivery
   to disconnected clients). Then ``channel_setup()`` registers a new ``Session``
   record for the current connection and restores the user's group memberships
   from cache.

2. **During the connection** — The client sends periodic ``session.heartbeat``
   events to update the ``last_seen`` timestamp and keep the session alive.

3. **On disconnect** — ``channel_cleanup()`` runs again to remove the expired
   session from groups.

Session Model Fields
---------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Description
   * - ``user``
     - FK to ``User``. The authenticated user this session belongs to.
   * - ``channel_name``
     - The Django Channels layer channel name for this specific connection.
   * - ``last_seen``
     - Timestamp of the last heartbeat. Used to determine if the session is active.

Inactivity Threshold
---------------------

Sessions older than ``INACTIVITY_THRESHOLD`` seconds (default: 60) are
considered expired. Expired sessions are:

- Removed from all channel groups during the next connection's cleanup phase.
- Excluded from ``get_active_sessions()`` so messages are not sent to
  disconnected channels.

The default of 60 seconds works well for most applications. Adjust it in
settings if your use case requires longer idle periods:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "INACTIVITY_THRESHOLD": 300  # 5 minutes
   }

Heartbeat
---------

Clients must send heartbeats to prevent their session from expiring. The
recommended interval is every **15–30 seconds** (2–3 times within the default
60-second threshold).

Client payload::

   {
     "event_type": "session.heartbeat",
     "data": {}
   }

The server responds immediately:

.. code-block:: json

   {"status": "success"}

No need to ``await`` or listen for this response on the frontend — it is purely
confirmatory.

Multi-Device Support
--------------------

When a user connects from multiple devices, each connection creates its own
``Session`` record with a unique ``channel_name``. When a message is sent to a
room, the package fetches **all active sessions** for each recipient and adds
every channel name to the broadcast group. This means all connected devices
receive every message simultaneously.

Group membership cache (``user:<user_id>:groups``) is keyed per user, not per
session. All of the user's sessions share the same group memberships, which is
why restoring groups on reconnect works correctly for any device.

Cache Storage
-------------

Group memberships are stored in Django's cache under the key
``user:<user_id>:groups`` as a JSON-serialised list. This cache entry has no
expiration (``timeout=None``) so memberships survive application restarts.

When a user joins or leaves a room, the cache is updated atomically via
``add_group_to_user_groups()`` or ``remove_group_from_user_groups()``. The cache
entries are the authoritative source for group restoration; the ``Session``
database records are the authoritative source for active channel names.
