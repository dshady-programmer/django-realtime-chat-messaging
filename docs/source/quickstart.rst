Quickstart
==========

This guide walks you from a fresh Django project to a working chat connection in
under ten minutes. It uses the default configuration — no custom models, no
overrides.

Step 1 — Install
----------------

.. code-block:: bash

   pip install django-realtime-chat-messaging django-channels-jwt-auth-middleware djangorestframework-simplejwt

Step 2 — Update ``settings.py``
--------------------------------

.. code-block:: python

   INSTALLED_APPS = [
       "daphne",                         # serves ASGI — see note below
       "channels",                       # required
       "django.contrib.admin",
       "django.contrib.auth",
       "polymorphic",                    # required — django-polymorphic
       "django.contrib.contenttypes",    # required by polymorphic
       "django.contrib.sessions",
       "django.contrib.messages",
       "django.contrib.staticfiles",
       "guardian",                       # required — django-guardian
       "rest_framework",                 # required — djangorestframework
       "realtime_chat_messaging",        # required
       # ... your own apps
   ]

   ASGI_APPLICATION = "yourproject.asgi.application"

   AUTHENTICATION_BACKENDS = (
       "django.contrib.auth.backends.ModelBackend",
       "guardian.backends.ObjectPermissionBackend",
   )

   # Development channel layer (use Redis in production)
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels.layers.InMemoryChannelLayer",
       }
   }

   # Development cache (use Redis in production)
   CACHES = {
       "default": {
           "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
           "LOCATION": "chat-dev",
       }
   }

   # JWT settings (adjust to your needs)
   from datetime import timedelta
   SIMPLE_JWT = {
       "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
   }

.. note::

   ``"daphne"`` at the top of ``INSTALLED_APPS`` is only required if you are
   using Daphne as your ASGI server — it overrides Django's ``runserver``
   command to serve ASGI automatically. If you are using a different ASGI server
   such as Uvicorn or Hypercorn, omit it from ``INSTALLED_APPS`` and start your
   server manually. For development the simplest option is to keep Daphne.

.. important::

   ``"polymorphic"`` and ``"guardian"`` must be present in ``INSTALLED_APPS``
   even if you are not using them directly in your own code. The package depends
   on both. Missing either will cause migration or runtime errors.

Step 3 — Create ``asgi.py``
----------------------------

.. code-block:: python

   import os
   import django

   os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yourproject.settings")
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

Step 4 — Run Migrations
------------------------

.. code-block:: bash

   python manage.py migrate

Step 5 — Add JWT Token Endpoint (optional but recommended)
-----------------------------------------------------------

Add ``djangorestframework-simplejwt`` URLs so clients can obtain tokens:

.. code-block:: python

   # urls.py
   from django.urls import path
   from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

   urlpatterns = [
       path("api/token/", TokenObtainPairView.as_view()),
       path("api/token/refresh/", TokenRefreshView.as_view()),
   ]

Step 6 — Connect and Chat
--------------------------

First, create a user to authenticate with. You can do this via the Django shell
or the admin panel:

.. code-block:: bash

   python manage.py shell

.. code-block:: python

   from django.contrib.auth import get_user_model
   User = get_user_model()

   # Create two users — you will need at least two to test a chat
   alice = User.objects.create_user(username="alice", password="secret123")
   bob   = User.objects.create_user(username="bob",   password="secret123")

   print(alice.id, bob.id)   # note the IDs — you will need them below

Now start the server and obtain a token for Alice:

.. code-block:: bash

   python manage.py runserver

.. code-block:: bash

   curl -X POST http://localhost:8000/api/token/ \
     -H "Content-Type: application/json" \
     -d '{"username": "alice", "password": "secret123"}'
   # → {"access": "<token>", "refresh": "..."}

Copy the ``access`` value. Connect to the WebSocket — the token is passed as a
query parameter (``django-channels-jwt-auth-middleware`` reads it from the query
string by default):

.. code-block:: javascript

   const token = "<your_access_token>";
   const ws = new WebSocket(`ws://localhost:8000/messaging/?token=${token}`);

   ws.onopen = () => {
     console.log("Connected!");

     // Create a one-to-one chat with Bob (use Bob's actual user ID)
     ws.send(JSON.stringify({
       event_type: "room.create",
       data: {
         type: "OneToOneChat",
         participants: [2]   // replace 2 with Bob's actual ID
       }
     }));
   };

   ws.onmessage = (e) => {
     const msg = JSON.parse(e.data);
     console.log(msg.eventType, msg.data);
   };

The server responds with a ``roomcreate.dispatch`` event containing the new
room's details. Send a message into that room:

.. code-block:: javascript

   ws.send(JSON.stringify({
     event_type: "message.send",
     data: {
       room_id: "<room_id_from_roomcreate_dispatch>",
       content: "Hello! 👋"
     }
   }));

All participants in the room — including on other devices — will receive a
``message.dispatch`` event in real time.

Testing with a GUI Tool
~~~~~~~~~~~~~~~~~~~~~~~~

If you prefer a visual interface over JavaScript, `WebSocket King
<https://websocketking.com>`_ is a browser-based WebSocket client that works
well for testing this package.

1. Open `https://websocketking.com <https://websocketking.com>`_ in your browser.
2. Enter your connection URL with the token in the query string::

      ws://localhost:8000/messaging/?token=<your_access_token>

3. Click **Connect**.
4. In the message input, paste a JSON event and click **Send**:

   .. code-block:: json

      {"event_type": "room.create", "data": {"type": "OneToOneChat", "participants": [2]}}

.. warning::

   Do not omit the ``?token=<your_access_token>`` query parameter from the
   connection URL. Without it the server cannot authenticate the connection and
   will close it immediately. There is no separate authentication step — the
   token goes in the URL when you open the socket.

What Happens Automatically
---------------------------

Once connected, the following happens without any extra code from you:

- **Pending notifications** are dispatched immediately on connect (``chat.notifications`` event).
- **Session tracking** begins. The connection is registered and your channel is
  added to all your room groups automatically.
- **Multi-device** support is active. If the same user connects on two devices,
  both receive every message.
- **Group memberships** are cached. On reconnect, the user is restored to all
  their rooms without additional round trips.

Next Steps
----------

- Read :doc:`websocket_events` for a complete reference of every event.
- Read :doc:`rooms` to understand the three room types and their differences.
- Read :doc:`custom_models` if you need to extend any of the default models.
- Read :doc:`deployment` when you are ready for production.