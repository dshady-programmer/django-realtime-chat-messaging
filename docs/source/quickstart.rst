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
       "daphne",
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

Obtain a JWT token:

.. code-block:: bash

   curl -X POST http://localhost:8000/api/token/ \
     -H "Content-Type: application/json" \
     -d '{"username": "alice", "password": "secret"}'
   # → {"access": "<token>", "refresh": "..."}

Connect to the WebSocket (pass the token as a query parameter — depends on your
middleware; ``django-channels-jwt-auth-middleware`` reads it from the query string
by default):

.. code-block:: javascript

   const token = "<your_access_token>";
   const ws = new WebSocket(`ws://localhost:8000/messaging/?token=${token}`);

   ws.onopen = () => {
     console.log("Connected!");

     // Create a one-to-one chat with user ID 2
     ws.send(JSON.stringify({
       event_type: "room.create",
       data: {
         type: "OneToOneChat",
         participants: [2]
       }
     }));
   };

   ws.onmessage = (e) => {
     const msg = JSON.parse(e.data);
     console.log(msg.eventType, msg.data);
   };

The server will respond with a ``roomcreate.dispatch`` event containing the new
room's details. To send a message into that room:

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
