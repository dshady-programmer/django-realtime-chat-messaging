Troubleshooting
===============

This page covers the most common issues developers encounter when integrating
this package, along with their root causes and fixes.

Events Fire But No Broadcast Is Received
-----------------------------------------

This is the most common issue new users hit. You send an event — ``message.send``,
``room.create``, etc. — the server processes it without error, but the expected
broadcast dispatch never arrives on one or more connected clients. There are two
distinct root causes that produce this identical symptom.

Understanding Why This Happens
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a user connects, the consumer calls ``add_channel_to_group`` for every room
the user belongs to. This method works by first querying the cache for all of the
user's **active sessions**, then adding each session's channel name to the
relevant channel groups. This is how real-time delivery works — when a message is
broadcast to a group, Django Channels looks up every channel name in that group
and delivers the dispatch to each one.

The key point is this: **if a channel name is not in a group, it receives
nothing.** Group membership is not stored in the database — it lives entirely in
the channel layer (in-memory or Redis). And the session records that power
``add_channel_to_group`` live in the cache.

If either the cache or the channel layer loses its state, the user's channel is
no longer in any group, and broadcasts silently disappear.

Cause 1 — In-Memory Cache or Channel Layer Restarted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The development configuration uses in-memory backends for both the cache and the
channel layer:

.. code-block:: python

   # settings.py — development defaults
   CHANNEL_LAYERS = {
       "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
   }

   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
           "LOCATION": "chat-dev",
       }
   }

Both of these store their data in the running process's memory. **Every time you
restart the development server, all of that state is wiped.** Any client that was
connected before the restart is now in an inconsistent state:

- The WebSocket connection itself may still appear open on the client side
- But the server has no record of that session in the cache
- And the channel layer has no group memberships for that channel

The result: the client appears connected, events are accepted, but no dispatches
arrive.

**Fix in development:** Reconnect the WebSocket after every server restart.
The ``connect()`` lifecycle method re-registers the session and re-adds the
channel to all groups — but only on a fresh connection.

**Fix for production:** Use Redis for both. Redis persists independently of your
application process:

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

Cause 2 — Session Expired Due to Inactivity (Missing Heartbeat)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Every connected session has a ``last_seen`` timestamp that is updated each time
a ``session.heartbeat`` event is received. If the time since ``last_seen``
exceeds ``INACTIVITY_THRESHOLD`` (default: 60 seconds), the session is
considered expired.

When a new event arrives that requires adding the current user's channel to a
group — for example, after creating a new room — ``add_channel_to_group``
queries the cache for the user's **active** sessions. An expired session is
excluded from this query. This means:

- The user's channel is never added to the new room's group
- Any broadcast to that group never reaches the user
- No error is raised — the operation completes silently

This is especially easy to miss in development because you may leave a
connection open for longer than 60 seconds while reading docs or inspecting
responses.

**Fix:** Send ``session.heartbeat`` from your client on a regular interval.
Every 15–30 seconds is recommended:

.. code-block:: javascript

   // Send a heartbeat every 20 seconds
   setInterval(() => {
     if (ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify({
         event_type: "session.heartbeat",
         data: {}
       }));
     }
   }, 20000);

The server responds with ``{"status": "success"}`` and updates ``last_seen``.
As long as heartbeats arrive before ``INACTIVITY_THRESHOLD`` elapses, the
session stays active and group membership works correctly.

You can also increase ``INACTIVITY_THRESHOLD`` in settings if your use case
involves long periods of reading without sending:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "INACTIVITY_THRESHOLD": 300,  # 5 minutes
   }

.. warning::

   Do not rely on increasing ``INACTIVITY_THRESHOLD`` alone as a substitute for
   heartbeats in production. It only delays the problem. Implement the heartbeat
   interval on the client and use a value that comfortably fits within your
   threshold.

Summary
~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 35 35 30

   * - Symptom
     - Root cause
     - Fix
   * - No broadcasts after server restart
     - In-memory cache/channel layer wiped on restart
     - Reconnect WebSocket after restart in dev; use Redis in production
   * - No broadcasts after idle period
     - Session expired — channel not added to new groups
     - Send ``session.heartbeat`` every 15–30 seconds from the client
   * - No broadcasts in production only
     - In-memory backends used in production config
     - Switch both cache and channel layer to Redis
   * - No broadcasts at all, fresh connection
     - ``ALLOWED_HOSTS`` misconfigured — connections rejected at ASGI level
     - See :doc:`installation` — set ``ALLOWED_HOSTS`` correctly

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
