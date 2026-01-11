Installation
============

This guide walks you through installing Django Realtime Chat Messaging and all its dependencies.

Requirements
------------

Before installing, ensure you have:

* Python 3.8 or higher
* Django 3.2 or higher
* A Django project (existing or new)
* pip package manager

Supported Versions
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Component
     - Supported Versions
   * - Python
     - 3.8, 3.9, 3.10, 3.11, 3.12
   * - Django
     - 3.2, 4.0, 4.1, 4.2, 5.0
   * - Django Channels
     - 3.0+
   * - Django REST Framework
     - 3.14+

Installing the Package
----------------------

Using pip (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to install is via pip:

.. code-block:: bash

   pip install django-realtime-chat-messaging

This automatically installs all required dependencies:

* ``Django>=4.2`` - Django Web Framework
* ``djangorestframework`` - REST API and serializers
* ``channels`` - WebSocket support for Django
* ``channels-redis`` - Redis channel layer backend
* ``daphne`` - ASGI HTTP and WebSocket server
* ``django-polymorphic`` - Polymorphic model support
* ``django-rest-polymorphic`` - For exposing polymorphic serialization
* ``django-guardian`` - Object-level permissions
* ``bleach`` - HTML sanitization (XSS protection)
* ``drf-recursive`` - For adding Recursive Field for serialization 


Installing a Specific Version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To install a specific version:

.. code-block:: bash

   pip install django-realtime-chat-messaging==0.1.0

To upgrade to the latest version:

.. code-block:: bash

   pip install --upgrade django-realtime-chat-messaging

From Source (Development)
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you want to contribute or modify the package:

.. code-block:: bash

   git clone https://github.com/yourusername/django-realtime-chat-messaging.git
   cd django-realtime-chat-messaging
   pip install -e .[dev]

This installs the package in editable mode with development dependencies (pytest, coverage, etc.).

Django Configuration
--------------------

INSTALLED_APPS
~~~~~~~~~~~~~~

Add required apps to your ``settings.py``:

.. code-block:: python

   INSTALLED_APPS = [
       # IMPORTANT: daphne must be BEFORE django.contrib.staticfiles
       'daphne',

       # Django built-ins
       'django.contrib.admin',
       'django.contrib.auth',
       'django.contrib.contenttypes',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',
       
       
       # Required dependencies
       'channels',
       'rest_framework',
       'polymorphic',
       'guardian',
       
       # The chat package
       'realtime_chat_messaging',
       
       # Your apps
       'myapp',
   ]

.. warning::
   **Place ``daphne`` BEFORE ``django.contrib.staticfiles``** or you'll encounter static file serving issues in development.

ASGI Configuration
~~~~~~~~~~~~~~~~~~

Set your ASGI application in ``settings.py``:

.. code-block:: python

   ASGI_APPLICATION = 'myproject.asgi.application'

Channel Layers
~~~~~~~~~~~~~~

For **development**, you can use the in-memory channel layer:

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels.layers.InMemoryChannelLayer"
       }
   }

.. danger::
   **Never use InMemoryChannelLayer in production!** It doesn't work across multiple server instances and loses data on restart.

For **production**, use Redis (see :doc:`../deployment/redis`):

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("127.0.0.1", 6379)],
           },
       },
   }

Authentication Backends
~~~~~~~~~~~~~~~~~~~~~~~

Add django-guardian's authentication backend:

.. code-block:: python

   AUTHENTICATION_BACKENDS = (
       'django.contrib.auth.backends.ModelBackend',  # Default
       'guardian.backends.ObjectPermissionBackend',  # For object-level permissions
   )

This enables object-level permissions for rooms, messages, and other models.

ASGI Application Setup
----------------------

Create or update ``myproject/asgi.py``:

.. code-block:: python

   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

   # CRITICAL: Load Django before importing any apps
   django.setup()

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from channels.auth import AuthMiddlewareStack
   from realtime_chat_messaging.routing import websocket_urlpatterns

   django_asgi_app = get_asgi_application()

   application = ProtocolTypeRouter({
       "http": django_asgi_app,
       "websocket": AllowedHostsOriginValidator(
           AuthMiddlewareStack(
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

.. note::
   **Why ``django.setup()``?**
   
   Calling ``django.setup()`` before imports prevents ``AppRegistryNotReady`` errors, especially when using JWT authentication middleware or custom Django apps in your ASGI configuration.

Alternative: JWT Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For token-based authentication (recommended for SPAs):

.. code-block:: bash

   pip install djangorestframework-simplejwt django-channels-jwt-auth-middleware

Update ``asgi.py``:

.. code-block:: python

   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
   django.setup()  # Still required!

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack
   from realtime_chat_messaging.routing import websocket_urlpatterns

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           JWTAuthMiddlewareStack(
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

See :doc:`../user-guide/authentication` for complete JWT setup instructions.

Database Migrations
-------------------

Run migrations to create the required database tables:

.. code-block:: bash

   python manage.py migrate

This creates tables for:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Model
     - Purpose
   * - ``Room``
     - Base model for all chat rooms (polymorphic)
   * - ``OneToOneChat``
     - Private chats between two users
   * - ``GroupChat``
     - Group conversations with admins
   * - ``Channel``
     - Broadcast channels with moderators
   * - ``Message``
     - All messages with replies/forwarding support
   * - ``MessageMediaAsset``
     - Media attachments (images, videos, files)
   * - ``ReadReceipt``
     - Track who read each message
   * - ``Reaction``
     - Emoji reactions on messages
   * - ``ChatNotification``
     - Unread message tracking
   as well as their through tables for many to many relationship

Running the Development Server
-------------------------------

Start the server with Daphne (automatically configured):

.. code-block:: bash

   python manage.py runserver

You'll see output like:

.. code-block:: text

   Performing system checks...
   
   System check identified no issues (0 silenced).
   January 10, 2024 - 12:00:00
   Django version 4.2, using settings 'myproject.settings'
   Starting ASGI/Daphne version 4.0.0 development server at http://127.0.0.1:8000/
   Quit the server with CONTROL-C.

Daphne now handles both HTTP and WebSocket connections on port 8000.

Or run daphne in production with
.. code-block:: bash
   daphne -b 0.0.0.0 -p <:PORT:> myproject.asgi:application

Verifying Installation
-----------------------

Test Database Tables
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python manage.py shell

.. code-block:: python

   from realtime_chat_messaging.models import Room, Message, OneToOneChat
   
   # Should not raise ImportError

   # Check table exists
   print(f"✓ Room table exists: {Room.objects.exists() or True}")

Test WebSocket Endpoint
~~~~~~~~~~~~~~~~~~~~~~~~

Using your browser console or a WebSocket client i recommend using `WebSocket King <https://websocketking.com/>`_ for testing:

.. code-block:: javascript

   const socket = new WebSocket('ws://localhost:8000/messaging/');
   
   socket.onopen = () => console.log('✓ WebSocket connected!');
   socket.onerror = (e) => console.error('✗ WebSocket error:', e);
   socket.onclose = (e) => {
       if (e.code === 4001) {
           console.log('⚠ Authentication required (expected)');
       }
   };

If you see "Authentication required", that's correct! Anonymous users cannot connect.

Next Steps
----------

Now that installation is complete:

1. **Follow the Quickstart** - :doc:`quickstart` to create your first chat
2. **Set up Authentication** - :doc:`../user-guide/authentication` for user login
3. **Learn Room Types** - :doc:`../user-guide/room-types` to understand OneToOne, GroupChat, and Channels

Troubleshooting
---------------

``ModuleNotFoundError: No module named 'daphne'``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution**: Daphne not installed. Run:

.. code-block:: bash

   pip install daphne

``ImproperlyConfigured: ASGI_APPLICATION not set``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution**: Add to ``settings.py``:

.. code-block:: python

   ASGI_APPLICATION = 'myproject.asgi.application'

``AppRegistryNotReady: Apps aren't loaded yet``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution**: Add ``django.setup()`` at the top of ``asgi.py`` (see ASGI setup above).

``Static files not loading after adding daphne``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution**: Ensure ``daphne`` is BEFORE ``django.contrib.staticfiles`` in ``INSTALLED_APPS``.

``Connection refused (WebSocket)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution**: Make sure the development server is running and you're connecting to the correct port (default: 8000).

Still Having Issues?
~~~~~~~~~~~~~~~~~~~~

See :doc:`../troubleshooting` for more solutions, or open an issue on `GitHub <https://github.com/yourusername/django-realtime-chat-messaging/issues>`_.