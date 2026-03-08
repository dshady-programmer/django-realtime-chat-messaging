Deployment
==========

This guide covers the configuration changes required to move from development to
a production environment.

Redis
-----

Both the channel layer and the Django cache must use Redis in production.
In-memory channel layers do not work across multiple processes or machines — if
you run more than one worker, messages sent by one worker will not reach
consumers on another.

Install Redis and ``channels-redis`` (already a dependency):

.. code-block:: bash

   # Ubuntu/Debian
   sudo apt install redis-server

   # macOS
   brew install redis

Configure Django:

.. code-block:: python

   # settings.py

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("127.0.0.1", 6379)],
           },
       }
   }

   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.redis.RedisCache",
           "LOCATION": "redis://127.0.0.1:6379",
       }
   }

You can use the same Redis instance for both. If you need separate instances for
isolation or scaling, use different databases or separate URLs:

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {"hosts": [("127.0.0.1", 6379)]},
       }
   }

   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.redis.RedisCache",
           "LOCATION": "redis://127.0.0.1:6379/1",  # DB 1 for cache
       }
   }

ASGI Server
-----------

Daphne is the recommended ASGI server and is included as a dependency. In
production, **do not** add ``"daphne"`` to ``INSTALLED_APPS`` — that setting is
only for development convenience with ``runserver``.

Start Daphne directly:

.. code-block:: bash

   daphne -b 0.0.0.0 -p 8000 yourproject.asgi:application

For a typical production setup behind Nginx, bind to a Unix socket instead of a
TCP port:

.. code-block:: bash

   daphne -u /run/daphne/daphne.sock yourproject.asgi:application

Uvicorn also works:

.. code-block:: bash

   uvicorn yourproject.asgi:application --host 0.0.0.0 --port 8000 --workers 4

.. warning::

   When using Uvicorn with multiple workers, ensure you are using a Redis channel
   layer. The default in-memory layer only works with a single process.

Nginx Configuration
-------------------

Nginx should proxy both HTTP and WebSocket traffic to Daphne:

.. code-block:: nginx

   server {
       listen 80;
       server_name example.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_read_timeout 86400;   # Keep WebSocket connections alive
       }
   }

The ``proxy_read_timeout 86400`` setting is important — without it Nginx will
close idle WebSocket connections after 60 seconds (the default).

systemd Service
---------------

Manage Daphne with systemd:

.. code-block:: ini

   # /etc/systemd/system/daphne.service
   [Unit]
   Description=Daphne ASGI Server
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/path/to/yourproject
   ExecStart=/path/to/venv/bin/daphne \
       -b 0.0.0.0 \
       -p 8000 \
       yourproject.asgi:application
   Restart=on-failure
   RestartSec=5s

   [Install]
   WantedBy=multi-user.target

.. code-block:: bash

   sudo systemctl enable daphne
   sudo systemctl start daphne

Production Settings Checklist
-------------------------------

.. code-block:: python

   # settings.py (production)

   DEBUG = False
   ALLOWED_HOSTS = ["example.com", "www.example.com"]  # required — AllowedHostsOriginValidator reads this
   SECRET_KEY = os.environ["SECRET_KEY"]

   # Redis channel layer
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {"hosts": [os.environ.get("REDIS_URL", "redis://localhost:6379")]},
       }
   }

   # Redis cache
   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.redis.RedisCache",
           "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379"),
       }
   }

   # ASGI
   ASGI_APPLICATION = "yourproject.asgi.application"

   # Guardian
   AUTHENTICATION_BACKENDS = (
       "django.contrib.auth.backends.ModelBackend",
       "guardian.backends.ObjectPermissionBackend",
   )

   # Chat settings
   REALTIME_CHAT_MESSAGING = {
       "INACTIVITY_THRESHOLD": 120,  # 2 minutes is reasonable for most apps
       "MESSAGE_SOFT_DELETE": True,
       "ENABLE_NOTIFICATION": True,
   }

Database
--------

PostgreSQL is strongly recommended for production. The package is compatible with
any database Django supports, but PostgreSQL handles the concurrent writes from
multiple WebSocket connections most reliably.

SQLite is supported for development via the ``sqlite_safe_db_sync_to_async``
wrapper, but is not suitable for production WebSocket applications due to its
write serialisation model.

Security Considerations
------------------------

WebSocket Origin Validation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``AllowedHostsOriginValidator`` wraps the WebSocket stack in ``asgi.py`` and
validates every incoming connection's ``Origin`` header against Django's
``ALLOWED_HOSTS`` setting. If the origin is not in the list, the WebSocket
handshake is rejected before it reaches the consumer. This prevents cross-site
WebSocket hijacking (CSWSH).

This is already wired in the ``asgi.py`` example — but it only works if
``ALLOWED_HOSTS`` is populated correctly. The production settings block above
already sets this:

.. code-block:: python

   ALLOWED_HOSTS = ["example.com"]

For development, use ``["*"]`` or ``["localhost", "127.0.0.1"]``:

.. code-block:: python

   # settings.py (development)
   ALLOWED_HOSTS = ["*"]

.. warning::

   Never use ``ALLOWED_HOSTS = ["*"]`` in production. List only the exact
   hostnames your app is served from. An empty ``ALLOWED_HOSTS`` (the Django
   default when ``DEBUG = False``) will cause every WebSocket connection to be
   rejected silently — the handshake fails with no error in your application logs,
   which makes it an easy misconfiguration to miss.

Keep ``AllowedHostsOriginValidator`` in your production ``asgi.py`` at all times.
Do not remove it to "fix" connection issues — the correct fix is always to update
``ALLOWED_HOSTS``.

Authentication
~~~~~~~~~~~~~~

Never expose the WebSocket endpoint without authentication middleware. The
consumer rejects unauthenticated connections with close code ``4001``, but the
middleware layer should ideally refuse them before they even reach the consumer.

Token Expiry
~~~~~~~~~~~~

If you use JWT authentication, tokens should expire and be refreshed. When a
token expires mid-session, the connection is not automatically closed — the
existing connection continues until it disconnects naturally. Only new connections
will be rejected. Implement token refresh in your client WebSocket reconnect
logic.

Session Heartbeat Interval
~~~~~~~~~~~~~~~~~~~~~~~~~~

For production, send heartbeats every 15–30 seconds. The default
``INACTIVITY_THRESHOLD`` is 60 seconds. Expired sessions are cleaned up on the
next connection by that user — stale sessions do not cause data leakage but do
occupy rows in the ``Session`` table.

Run the following periodically (e.g. a daily Celery task) to clean up very old
sessions that were never cleaned by a reconnect:

.. code-block:: python

   from django.utils import timezone
   import datetime
   from realtime_chat_messaging.utils.loader import get_model

   Session = get_model("Session")
   cutoff = timezone.now() - datetime.timedelta(hours=24)
   Session.objects.filter(last_seen__lt=cutoff).delete()