Quick Start Guide
=================

Get Django Realtime Chat Messaging up and running in 10 minutes. This guide walks you through the minimal setup needed for a working chat system.

Prerequisites
-------------

Before starting, ensure you have:

- Completed :doc:`installation`
- Redis running (test with ``redis-cli ping``)
- A Django project (Django 3.2+)

Step 1: Add to INSTALLED_APPS
------------------------------

Add the required apps to your ``settings.py``:

.. code-block:: python

   INSTALLED_APPS = [
       'django.contrib.admin',
       'django.contrib.auth',
       'django.contrib.contenttypes',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',
       
       # Third-party apps
       'channels',                     # Required for WebSocket support
       'realtime_chat_messaging',      # Our package
       'guardian',                     # Object-level permissions
       'polymorphic',                  # Polymorphic models
       'rest_framework',               # REST framework
       
       # Your apps
       'myapp',
   ]

Step 2: Configure ASGI Application
-----------------------------------

Django Channels requires ASGI configuration. Create or modify ``asgi.py`` in your project directory:

.. code-block:: python

   """
   ASGI config for your project.
   """
   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')

   # Initialize Django - IMPORTANT for Daphne
   django.setup()

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from channels.auth import AuthMiddlewareStack

   # Import WebSocket routing from the package
   from realtime_chat_messaging.routing import websocket_urlpatterns

   # Initialize Django ASGI application
   django_asgi_app = get_asgi_application()

   application = ProtocolTypeRouter({
       "http": django_asgi_app,
       "websocket": AllowedHostsOriginValidator(
           AuthMiddlewareStack(
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

.. important::
   The ``django.setup()`` call is **required** when running with Daphne directly. It prevents ``AppRegistryNotReady`` errors. Not needed when using ``python manage.py runserver``.

Step 3: Set ASGI Application
-----------------------------

In your ``settings.py``, specify the ASGI application:

.. code-block:: python

   ASGI_APPLICATION = 'yourproject.asgi.application'

Replace ``yourproject`` with your actual project name.

Step 4: Configure Channel Layers
---------------------------------

Development Setup (In-Memory)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For quick development and testing:

.. code-block:: python

   # settings.py
   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels.layers.InMemoryChannelLayer'
       }
   }

.. warning::
   In-memory backend doesn't support multiple server processes. Messages won't sync across workers. Use only for development.

Production Setup (Redis)
~~~~~~~~~~~~~~~~~~~~~~~~~

For production or multi-worker development:

.. code-block:: python

   # settings.py
   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": [('127.0.0.1', 6379)],
           },
       },
   }

**With Redis authentication:**

.. code-block:: python

   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": ['redis://:password@localhost:6379/0'],
           },
       },
   }

**Using environment variables (recommended):**

.. code-block:: python

   import os

   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": [os.environ.get('REDIS_URL', 'redis://localhost:6379')],
           },
       },
   }

Step 5: Configure Guardian
---------------------------

Add guardian to authentication backends:

.. code-block:: python

   # settings.py
   AUTHENTICATION_BACKENDS = (
       'django.contrib.auth.backends.ModelBackend',  # Default
       'guardian.backends.ObjectPermissionBackend',  # Guardian
   )

Step 6: Run Migrations
----------------------

Create the necessary database tables:

.. code-block:: bash

   python manage.py migrate

This creates tables for:

- ``Room`` (polymorphic base)
- ``OneToOneChat``
- ``GroupChat``
- ``Channel``
- ``Message``
- ``ReadReceipt``
- ``ChatNotification``
- ``Reaction``
- ``MessageMediaAsset``

Step 7: Create Superuser (Optional)
------------------------------------

Create an admin user to test with:

.. code-block:: bash

   python manage.py createsuperuser

Step 8: Start the Development Server
-------------------------------------

.. code-block:: bash

   python manage.py runserver

The server will start on ``http://127.0.0.1:8000``

Testing Your Setup
------------------

Verify Channel Layer Connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test that the channel layer is working:

.. code-block:: python

   # In Django shell
   python manage.py shell

.. code-block:: python

   >>> from channels.layers import get_channel_layer
   >>> from asgiref.sync import async_to_sync
   >>> 
   >>> channel_layer = get_channel_layer()
   >>> async_to_sync(channel_layer.send)('test', {'type': 'test.message'})
   # Should complete without errors

WebSocket Connection URL
~~~~~~~~~~~~~~~~~~~~~~~~

Your WebSocket endpoint is available at:

.. code-block:: text

   ws://127.0.0.1:8000/messaging/

For HTTPS/WSS in production:

.. code-block:: text

   wss://yourdomain.com/messaging/

Creating Your First Chat Room
------------------------------

Via Django Shell
~~~~~~~~~~~~~~~~

.. code-block:: python

   python manage.py shell

.. code-block:: python

   from django.contrib.auth import get_user_model
   from realtime_chat_messaging.models import OneToOneChat, GroupChat, Channel

   User = get_user_model()

   # Create two users
   user1 = User.objects.create_user('alice', 'alice@example.com', 'password')
   user2 = User.objects.create_user('bob', 'bob@example.com', 'password')

   # Create a one-to-one chat
   chat = OneToOneChat.objects.create()
   chat.participants.add(user1, user2)

   # Create a group chat
   group = GroupChat.objects.create(
       name="Project Team",
       description="Team discussion",
       creator=user1
   )
   group.participants.add(user2)  # user1 added automatically

   # Create a public channel
   channel = Channel.objects.create(
       name="Announcements",
       description="Company updates",
       creator=user1,
       is_public=True
   )
   channel.subscribers.add(user2)

Via Django Admin
~~~~~~~~~~~~~~~~

1. Navigate to ``http://127.0.0.1:8000/admin/``
2. Log in with your superuser credentials
3. Go to **Realtime Chat Messaging** section
4. Click **Add** next to the room type you want to create
5. Fill in the details and save

Frontend Integration Preview
-----------------------------

Here's a minimal JavaScript example to connect and send a message:

.. code-block:: javascript

   // Connect to WebSocket
   const ws = new WebSocket('ws://127.0.0.1:8000/messaging/');

   ws.onopen = () => {
       console.log('Connected!');
       
       // Send a message
       ws.send(JSON.stringify({
           event_type: "message.send",
           data: {
               room_id: "your-room-uuid-here",
               content: "Hello, World!"
           }
       }));
   };

   ws.onmessage = (event) => {
       const response = JSON.parse(event.data);
       console.log('Received:', response);
   };

   ws.onerror = (error) => {
       console.error('WebSocket error:', error);
   };

.. note::
   This example assumes you're using session-based authentication. See :doc:`authentication-setup` for JWT and other authentication methods.

What's Next?
------------

Now that you have the basics working, explore:

**Core Concepts**

- :doc:`understanding-room-types` - Learn about OneToOne, Group, and Channel differences
- :doc:`authentication-setup` - Configure JWT, session, or custom authentication

**Use Case Guides**

- :doc:`guides/whatsapp-style` - Build WhatsApp-like one-to-one chat
- :doc:`guides/slack-style` - Implement Slack-style team communication
- :doc:`guides/discord-style` - Create Discord-style public channels

**WebSocket Events**

- :doc:`websocket/message-events` - Sending, editing, reacting to messages
- :doc:`websocket/room-events` - Creating, joining, managing rooms
- :doc:`websocket/member-management` - Adding and removing users

**Customization**

- :doc:`customization/overview` - Overview of customization options
- :doc:`customization/settings-reference` - Complete settings reference

Troubleshooting
---------------

Server Won't Start
~~~~~~~~~~~~~~~~~~

**Error**: ``django.core.exceptions.ImproperlyConfigured: ASGI_APPLICATION not set``

**Solution**: Add ``ASGI_APPLICATION = 'yourproject.asgi.application'`` to settings.py

**Error**: ``ImportError: No module named 'channels'``

**Solution**: Install channels: ``pip install channels``

WebSocket Connection Fails
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error**: WebSocket connection to ws://... failed

**Solutions**:

1. Verify server is running: ``python manage.py runserver``
2. Check ASGI configuration in ``asgi.py``
3. Ensure ``ASGI_APPLICATION`` points to correct module
4. Check browser console for detailed error messages

Redis Connection Issues
~~~~~~~~~~~~~~~~~~~~~~~

**Error**: ``redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379``

**Solution**: Start Redis server:

.. code-block:: bash

   # Check if Redis is running
   redis-cli ping

   # Start Redis if not running
   redis-server

**Error**: ``WRONGPASS invalid username-password pair``

**Solution**: Update Redis configuration with correct password:

.. code-block:: python

   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": ['redis://:your_password@localhost:6379/0'],
           },
       },
   }

Migration Errors
~~~~~~~~~~~~~~~~

**Error**: ``django.db.utils.OperationalError: no such table: realtime_chat_messaging_room``

**Solution**: Run migrations:

.. code-block:: bash

   python manage.py migrate realtime_chat_messaging

AppRegistryNotReady Error
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error**: ``django.core.exceptions.AppRegistryNotReady: Apps aren't loaded yet``

**Solution**: Add ``django.setup()`` to your ``asgi.py`` file:

.. code-block:: python

   import django
   django.setup()
   # ... rest of asgi.py

This is **required** when running Daphne directly in production.

Authentication Failed (4001)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error**: WebSocket closes immediately with code 4001

**Solution**: User is not authenticated. Ensure:

1. User is logged in
2. Authentication middleware is configured in ``asgi.py``
3. Session/token is being sent with WebSocket connection

For detailed authentication setup, see :doc:`authentication-setup`.

Production Deployment Preview
------------------------------

For production, use an ASGI server like Daphne or Uvicorn:

**With Daphne:**

.. code-block:: bash

   pip install daphne
   daphne -b 0.0.0.0 -p 8000 yourproject.asgi:application

**With Uvicorn:**

.. code-block:: bash

   pip install uvicorn
   uvicorn yourproject.asgi:application --host 0.0.0.0 --port 8000

See :doc:`advanced/deployment` for complete production deployment guide.