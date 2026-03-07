Installation
============

Requirements
------------

Before installing, ensure your environment meets these requirements:

- Python ≥ 3.11
- Django ≥ 4.2
- Redis ≥ 6 (required in production for channel layer and cache)

Dependencies
------------

The package installs the following libraries automatically:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Package
     - Purpose
   * - ``djangorestframework``
     - Serializers used throughout the package (required even if you have no REST views)
   * - ``django-guardian``
     - Object-level permissions for group admins and channel moderators
   * - ``django-polymorphic``
     - Single-table polymorphic Room model
   * - ``django-rest-polymorphic``
     - Polymorphic serializers for room lists
   * - ``drf-recursive``
     - Recursive serialization for message replies and forwards
   * - ``bleach``
     - XSS sanitisation on message content
   * - ``channels``
     - Django Channels ASGI WebSocket support
   * - ``channels-redis``
     - Redis channel layer for production
   * - ``daphne``
     - ASGI server (recommended)

Install the Package
-------------------

.. code-block:: bash

   pip install django-realtime-chat-messaging

Configure ``INSTALLED_APPS``
----------------------------

Add the following apps to your ``INSTALLED_APPS`` in ``settings.py``. **Order
matters** — ``daphne`` must come before ``django.contrib.staticfiles``.

.. code-block:: python

   INSTALLED_APPS = [
       "daphne",            # only add if using daphne as your ASGI server
       "channels",
       "django.contrib.admin",
       "django.contrib.auth",
       "polymorphic",
       "django.contrib.contenttypes",
       "django.contrib.sessions",
       "django.contrib.messages",
       "django.contrib.staticfiles",
       "guardian",
       "realtime_chat_messaging",
       # ... your other apps
   ]

.. note::

   Add ``"daphne"`` to ``INSTALLED_APPS`` only when you want ``python manage.py
   runserver`` to use Daphne in development. In production you will start Daphne
   directly from the command line and do not need it in ``INSTALLED_APPS``.

Add Guardian Authentication Backend
------------------------------------

``django-guardian`` requires its object permission backend to be registered:

.. code-block:: python

   AUTHENTICATION_BACKENDS = (
       "django.contrib.auth.backends.ModelBackend",
       "guardian.backends.ObjectPermissionBackend",
   )

Configure the ASGI Application
--------------------------------

Set your ASGI application in ``settings.py``:

.. code-block:: python

   ASGI_APPLICATION = "yourproject.asgi.application"

Then create or update ``asgi.py``. The example below uses
``django-channels-jwt-auth-middleware`` for JWT-based WebSocket authentication,
which is the recommended approach:

.. code-block:: python

   import os
   import django

   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yourproject.settings")

   # django.setup() must be called before importing anything that uses the app registry.
   # This prevents AppRegistryNotReady errors when running with Daphne.
   django.setup()

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from realtime_chat_messaging.routing import websocket_urlpatterns
   from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack

   django_asgi_app = get_asgi_application()

   application = ProtocolTypeRouter(
       {
           "http": django_asgi_app,
           "websocket": AllowedHostsOriginValidator(
               JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))
           ),
       }
   )

.. note::

   The package does not enforce any specific authentication method. The consumer
   only requires that ``scope["user"]`` contains an authenticated Django user
   object. How that user gets into the scope is entirely up to your middleware
   stack. Common options include:

   - ``django-channels-jwt-auth-middleware`` (shown above, recommended for
     token-based APIs)
   - Django Channels' built-in ``AuthMiddlewareStack`` (for session-based auth)
   - Any custom middleware that populates ``scope["user"]``

Configure Channel Layers
------------------------

**Development** (in-memory, single process only):

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels.layers.InMemoryChannelLayer",
       }
   }

**Production** (Redis, required for multi-process deployments):

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {"hosts": [("localhost", 6379)]},
       }
   }

Configure Cache
---------------

The package uses Django's cache framework to store user group memberships across
reconnections. These cached memberships allow users to be automatically
re-subscribed to their rooms on reconnect without a database query.

**Development** (local memory):

.. code-block:: python

   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
           "LOCATION": "unique-dev-cache",
       }
   }

**Production** (Redis, same instance as channel layer is fine):

.. code-block:: python

   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.redis.RedisCache",
           "LOCATION": "redis://localhost:6379", # localhost is used here as demo, replace with your redis server prepared for production
       }
   }

Run Migrations
--------------

The package ships with its own migrations. Run them after completing the
configuration above:

.. code-block:: bash

   python manage.py migrate

.. warning::

   If you plan to use **custom (swappable) models**, do **not** run migrations
   yet. Set up your custom models first, then migrate. See :doc:`custom_models`
   for the full workflow including the important circular dependency fix.

Verify the Installation
-----------------------

Start your development server:

.. code-block:: bash

   python manage.py runserver

Open a WebSocket client (e.g., the browser console or a tool like ``wscat``) and
attempt to connect:

.. code-block:: javascript

   const ws = new WebSocket("ws://localhost:8000/messaging/");
   ws.onopen = () => console.log("Connected");
   ws.onmessage = (e) => console.log(JSON.parse(e.data));

An unauthenticated connection will be closed immediately with code ``4001``. Once
you have authentication middleware in place and send a valid token, the connection
will be accepted and any pending notifications will be dispatched automatically.
