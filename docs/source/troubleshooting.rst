Troubleshooting
===============

This page covers the most common issues developers encounter when integrating
this package, along with their root causes and fixes.

Events Fire But No Broadcast Is Received
-----------------------------------------

This is the most common issue new users hit. You send an event — ``message.send``,
``room.create``, etc. — the server processes it without error, but the expected
broadcast dispatch never arrives on one or more connected clients.

Before diving into the two root causes, it helps to understand what the cache
and the database each store, because the two issues stem from different layers.

What the Database Stores
~~~~~~~~~~~~~~~~~~~~~~~~~

Every WebSocket connection creates a **Session** record in the database. A
session holds the user's ``channel_name`` (the unique identifier Django Channels
assigns to each connection) and a ``last_seen`` timestamp that is updated each
time a ``session.heartbeat`` event is received.

Sessions are classified as **active** or **inactive** based on whether
``last_seen`` falls within the ``INACTIVITY_THRESHOLD`` window (default: 60
seconds). This is a DB-level query — only sessions whose ``last_seen`` is recent
enough are returned as active.

What the Cache Stores
~~~~~~~~~~~~~~~~~~~~~~

The cache stores each user's **group membership** under a namespaced key — the
list of channel layer group names the user currently belongs to (one per room
they have joined). This is referred to as ``user_groups``.

Every time a connection is established, the consumer fetches ``user_groups``
from the cache and adds the new connection's ``channel_name`` to every group in
that list. This is what ensures a reconnecting user immediately starts receiving
broadcasts for all their existing rooms — without having to re-join anything.

This is also what enables **multi-device support**: every active session's
``channel_name`` ends up in the same groups, so a broadcast reaches all of a
user's connected devices simultaneously.

Cause 1 — Session Expired (Missing Heartbeat)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a new room is created or a user is added to an existing room,
``add_channel_to_group`` is called for each user involved. This method:

1. Queries the database for all **active** sessions belonging to that user
   (filtered by ``last_seen`` within ``INACTIVITY_THRESHOLD``)
2. Adds each active session's ``channel_name`` to the room's channel layer group

This is where multi-device support happens — each active session or device
for that user gets its channel name added to the group independently.

If no active sessions are found — because the current session never sent a
heartbeat and ``last_seen`` became stale — the user's channel is never added
to the group. The result: the user appears connected, the room is created
successfully, but that user receives no broadcasts from that room at all.
No error is raised.

**Fix:** Send ``session.heartbeat`` from your client on a regular interval.
Every 15–30 seconds is recommended — well within the default 60 second threshold:

.. code-block:: javascript

   setInterval(() => {
     if (ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify({
         event_type: "session.heartbeat",
         data: {}
       }));
     }
   }, 20000);  // every 20 seconds

You can also raise ``INACTIVITY_THRESHOLD`` for use cases that involve long
reading periods:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "INACTIVITY_THRESHOLD": 300,  # 5 minutes
   }

.. warning::

   Raising ``INACTIVITY_THRESHOLD`` alone is not a substitute for heartbeats in
   production — it only delays the problem. Implement the heartbeat interval on
   the client side.

.. note::

   In production it is worth considering limiting the number of simultaneous
   active sessions per user. Since ``add_channel_to_group`` adds every active
   session to every group, an unbounded number of devices per user means an
   unbounded number of channel names being written to the channel layer on every
   room operation. A session cap (e.g. 5 concurrent devices) keeps this
   predictable.

Cause 2 — Cache Wiped (Non-Persistent Cache Backend)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a user connects, the consumer fetches their ``user_groups`` from the cache
— the list of channel layer groups (rooms) they belong to — and adds the new
connection's ``channel_name`` to each of those groups. This is what makes
existing room membership work across reconnections: the database holds the room
membership records, but the channel layer group wiring is rebuilt from the cache
on every connect.

The development configuration uses ``LocMemCache``:

.. code-block:: python

   # settings.py — development default
   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
           "LOCATION": "chat-dev",
       }
   }

``LocMemCache`` stores everything in the running process's memory. **Every time
the development server restarts, the entire cache is wiped.** When a user
reconnects after a restart, ``user_groups`` is empty — not because they left
any rooms, but because the record of which groups they belong to no longer
exists.

The consequence: the user is a full member of multiple rooms in the database,
but their channel name is added to zero groups in the channel layer. They
receive no broadcasts from any room. From their perspective the connection is
open and working — events are accepted — but the chat is completely silent.

**Fix in development:** Reconnect the WebSocket after every server restart.
The ``connect()`` lifecycle fully rebuilds group membership from the cache —
but the cache itself needs to be warm first. The faster long-term fix is to
switch to Redis even in development so state survives restarts:

.. code-block:: python

   # settings.py — use Redis even in development to avoid this entirely
   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.redis.RedisCache",
           "LOCATION": "redis://127.0.0.1:6379",
       }
   }

**Fix for production:** Redis is not optional. Use it for both the cache and
the channel layer:

.. code-block:: python

   # settings.py — production
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
       }
   }

   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.redis.RedisCache",
           "LOCATION": "redis://127.0.0.1:6379",
       }
   }

See :doc:`deployment` for the full production configuration.

Summary
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 38 32 30

   * - Symptom
     - Root cause
     - Fix
   * - No broadcasts from a newly created room
     - Session expired — ``add_channel_to_group`` found no active sessions,
       channel was never added to the new room's group
     - Send ``session.heartbeat`` every 15–30 seconds
   * - No broadcasts from any room after reconnect
     - ``LocMemCache`` wiped on server restart — ``user_groups`` empty,
       channel added to zero groups on reconnect
     - Use Redis cache in production; reconnect after restart in development
   * - No broadcasts in production only
     - In-memory backends used in production settings
     - Switch both cache and channel layer to Redis
   * - No broadcasts at all, fresh connection
     - ``ALLOWED_HOSTS`` misconfigured — connections rejected at ASGI level
     - Set ``ALLOWED_HOSTS`` correctly — see :doc:`installation`

WebSocket Connection Closes Immediately
-----------------------------------------

If the WebSocket connection closes as soon as it is opened with no error
message on the client, the most likely cause is authentication or origin
validation failing before the consumer is even reached.

Check the following in order:

1. **Token missing or invalid** — The token must be passed as a query parameter:
   ``ws://localhost:8000/messaging/?token=<your_access_token>``. An expired,
   malformed, or missing token causes the consumer to close the connection with
   code ``4001``.

2. **``ALLOWED_HOSTS`` not set** — ``AllowedHostsOriginValidator`` rejects the
   connection before it reaches the consumer. No close code is sent — the
   handshake is simply refused. See :doc:`installation`.

3. **``ASGI_APPLICATION`` not set** — If Django is still serving HTTP only, the
   WebSocket upgrade request is never handled. Confirm ``ASGI_APPLICATION`` is
   set in ``settings.py`` and that you are running an ASGI server (Daphne,
   Uvicorn), not ``runserver`` without Daphne in ``INSTALLED_APPS``.