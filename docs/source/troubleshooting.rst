Troubleshooting
===============

Common issues and solutions.

.. contents:: Table of Contents
   :local:
   :depth: 2

Installation Issues
-------------------

ModuleNotFoundError: No module named 'daphne'
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution:**

.. code-block:: bash

   pip install daphne

Ensure it's in ``INSTALLED_APPS`` before ``django.contrib.staticfiles``.

ImproperlyConfigured: ASGI_APPLICATION not set
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution:**

.. code-block:: python

   # settings.py
   ASGI_APPLICATION = 'myproject.asgi.application'

AppRegistryNotReady: Apps aren't loaded yet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Solution:**

Add ``django.setup()`` at top of ``asgi.py``:

.. code-block:: python

   import os
   import django
   
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
   django.setup()  # Add this

Connection Issues
-----------------

WebSocket connection failed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

* Connection refused
* 404 error
* Connection closes immediately

**Solutions:**

1. Check server is running:

   .. code-block:: bash

      python manage.py runserver

2. Verify WebSocket URL:

   .. code-block:: javascript

      // Correct
      const socket = new WebSocket('ws://localhost:8000/messaging/');
      
      // Wrong
      const socket = new WebSocket('http://localhost:8000/messaging/');

3. Check routing configured:

   .. code-block:: python

      # urls.py or routing.py
      from realtime_chat_messaging.routing import websocket_urlpatterns

Connection closes with code 4001
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause:** Authentication failed

**Solutions:**

For session auth:

* Ensure user is logged in
* Check session cookie is sent
* Verify ``SESSION_COOKIE_HTTPONLY = False``

For JWT auth:

* Verify token is valid
* Check token is passed correctly: ``?token=...``
* Ensure middleware is configured

Connection drops after 30-60 seconds
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause:** Nginx/proxy timeout

**Solution:**

.. code-block:: nginx

   # nginx.conf
   location /messaging/ {
       proxy_read_timeout 86400;
       proxy_send_timeout 86400;
   }

Message Issues
--------------

Messages not appearing in real-time
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause:** Using InMemoryChannelLayer in production

**Solution:**

.. code-block:: python

   # settings.py
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("127.0.0.1", 6379)],
           },
       },
   }

Messages save but don't broadcast
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

* Messages appear after page refresh
* Messages save to database
* WebSocket connected

**Causes:**

1. InMemoryChannelLayer (use Redis)
2. Redis not running
3. Channel layer misconfigured

**Solutions:**

.. code-block:: bash

   # Check Redis
   redis-cli ping  # Should return PONG
   
   # Test channel layer
   python manage.py shell
   >>> from channels.layers import get_channel_layer
   >>> channel_layer = get_channel_layer()
   >>> import asyncio
   >>> asyncio.run(channel_layer.send('test', {'type': 'test'}))

Chat already exists error (Code 4005)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause:** Trying to create duplicate OneToOneChat

**Solution:**

Check for existing chat first:

.. code-block:: javascript

   socket.send(JSON.stringify({
       event_type: 'room.list',
       data: {}
   }));
   
   // Check if chat exists before creating

Permission Issues
-----------------

Permission denied (Code 4002)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**

* Cannot send messages
* Cannot add/remove members
* Cannot modify room

**Solutions:**

1. Check user is room member
2. Verify user has required permissions
3. For GroupChat: Check if user is admin
4. For Channel: Check if user is moderator

**Debug:**

.. code-block:: javascript

   // Get room info
   socket.send(JSON.stringify({
       event_type: 'room.info',
       data: {room_id: 'room-uuid'}
   }));
   
   // Check current user's role
   console.log(room.admins);  // GroupChat
   console.log(room.moderators);  // Channel

Cannot send to locked GroupChat
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause:** ``group_locked=True`` and user is not admin

**Solution:**

.. code-block:: javascript

   // Unlock group
   socket.send(JSON.stringify({
       event_type: 'room.modify',
       data: {
           room_id: 'group-uuid',
           action: 'update',
           data: {group_locked: false}
       }
   }));

Database Issues
---------------

django.db.utils.IntegrityError
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Causes:**

* Duplicate OneToOneChat
* Invalid foreign key
* Unique constraint violation

**Solutions:**

Check error message for specific constraint:

.. code-block:: python

   # Duplicate OneToOneChat
   # Solution: Use room.list to check existing chats
   
   # Invalid foreign key
   # Solution: Verify IDs exist in database

Migration conflicts
~~~~~~~~~~~~~~~~~~~

**Cause:** Swapping models after migrations

**Solution:**

.. code-block:: bash

   # 1. Create new migrations
   python manage.py makemigrations
   
   # 2. If conflicts, squash migrations
   python manage.py squashmigrations app_name 0001 0005

Performance Issues
------------------

Slow message sending
~~~~~~~~~~~~~~~~~~~~

**Symptoms:** Messages take >1 second to send

**Solutions:**

1. Add database indexes
2. Optimize queries
3. Use ``select_related`` and ``prefetch_related``
4. Check Redis latency

High memory usage
~~~~~~~~~~~~~~~~~

**Cause:** Redis memory not limited

**Solution:**

.. code-block:: redis

   # redis.conf
   maxmemory 2gb
   maxmemory-policy allkeys-lru

Frontend Issues
---------------

CORS errors
~~~~~~~~~~~

**Solution:**

.. code-block:: python

   # settings.py
   INSTALLED_APPS = ['corsheaders', ...]
   MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', ...]
   CORS_ALLOWED_ORIGINS = ['http://localhost:3000']
   CORS_ALLOW_CREDENTIALS = True

Token expired during session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause:** JWT token expired

**Solution:**

Implement token refresh:

.. code-block:: javascript

   setInterval(async () => {
       const token = localStorage.getItem('access_token');
       const decoded = jwt_decode(token);
       
       if (decoded.exp * 1000 - Date.now() < 5 * 60 * 1000) {
           await refreshToken();
       }
   }, 60 * 1000);

Getting Help
------------

If your issue isn't listed:

1. **Check logs:**

   .. code-block:: bash

      # Django logs
      python manage.py runserver
      
      # Daphne logs
      daphne -v 2 myproject.asgi:application

2. **Enable debug mode temporarily:**

   .. code-block:: python

      DEBUG = True  # Only for debugging!

3. **GitHub Issues:**
   
   https://github.com/shady-cj/django-realtime-chat-messaging/issues

4. **Stack Overflow:**
   
   Tag: ``django-realtime-chat-messaging``

See Also
--------

* :doc:`faq` - Frequently asked questions
* :doc:`deployment/production-checklist` - Deployment guide