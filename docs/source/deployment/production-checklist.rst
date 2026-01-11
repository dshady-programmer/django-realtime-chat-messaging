Production Checklist
====================

Essential steps before deploying to production.

.. contents:: Table of Contents
   :local:
   :depth: 2

Critical Requirements
---------------------

Redis Configuration
~~~~~~~~~~~~~~~~~~~

.. danger::
   **Never use InMemoryChannelLayer in production!**

.. code-block:: python

   # settings.py
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("redis", 6379)],
               "capacity": 1500,
               "expiry": 10,
           },
       },
   }

See :doc:`redis` for complete setup.

ASGI Server
~~~~~~~~~~~

Use production ASGI server:

.. code-block:: bash

   # Install
   pip install daphne uvicorn

   # Run with Daphne
   daphne -b 0.0.0.0 -p 8000 myproject.asgi:application

   # Or Uvicorn
   uvicorn myproject.asgi:application --host 0.0.0.0 --port 8000

Security Settings
-----------------

Django Settings
~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py
   DEBUG = False
   SECRET_KEY = env('SECRET_KEY')  # From environment
   ALLOWED_HOSTS = ['yourdomain.com']
   
   # HTTPS
   SECURE_SSL_REDIRECT = True
   SESSION_COOKIE_SECURE = True
   CSRF_COOKIE_SECURE = True
   
   # HSTS
   SECURE_HSTS_SECONDS = 31536000
   SECURE_HSTS_INCLUDE_SUBDOMAINS = True
   SECURE_HSTS_PRELOAD = True

WebSocket Security
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Use wss:// (secure WebSocket)
   # Frontend
   const socket = new WebSocket('wss://yourdomain.com/messaging/');

Database
--------

Connection Pooling
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': env('DB_NAME'),
           'USER': env('DB_USER'),
           'PASSWORD': env('DB_PASSWORD'),
           'HOST': env('DB_HOST'),
           'PORT': env('DB_PORT'),
           'CONN_MAX_AGE': 600,
       }
   }

Indexes
~~~~~~~

Ensure critical indexes exist:

.. code-block:: bash

   python manage.py sqlmigrate realtime_chat_messaging 0001
   # Verify indexes on:
   # - Message.content
   # - Message.sender
   # - Room.last_message

Environment Variables
---------------------

.. code-block:: bash

   # .env
   SECRET_KEY=your-secret-key
   DEBUG=False
   DATABASE_URL=postgres://user:pass@host:5432/dbname
   REDIS_URL=redis://localhost:6379/0
   ALLOWED_HOSTS=yourdomain.com

Monitoring
----------

.. code-block:: python

   # Install Sentry
   pip install sentry-sdk

   # settings.py
   import sentry_sdk
   
   sentry_sdk.init(
       dsn="your-sentry-dsn",
       traces_sample_rate=0.1,
   )

Static Files
------------

.. code-block:: python

   STATIC_ROOT = '/var/www/static/'
   STATIC_URL = '/static/'

   # Collect
   python manage.py collectstatic --noinput

Nginx Configuration
-------------------

See :doc:`nginx` for complete configuration.

Quick check:

.. code-block:: nginx

   upstream websocket {
       server 127.0.0.1:8000;
   }

   server {
       listen 443 ssl;
       server_name yourdomain.com;
       
       location /messaging/ {
           proxy_pass http://websocket;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }

Pre-Launch Testing
------------------

Load Testing
~~~~~~~~~~~~

.. code-block:: python

   # Install locust
   pip install locust

   # locustfile.py
   from locust import HttpUser, task, between
   import websocket

   class ChatUser(HttpUser):
       wait_time = between(1, 3)
       
       def on_start(self):
           self.ws = websocket.create_connection("wss://yourdomain.com/messaging/")
       
       @task
       def send_message(self):
           self.ws.send('{"event_type":"message.send","data":{"room_id":"...","content":"test"}}')

Run:

.. code-block:: bash

   locust -f locustfile.py

Performance Check
~~~~~~~~~~~~~~~~~

* [ ] Messages send in <100ms
* [ ] WebSocket connects in <500ms
* [ ] Database queries <50ms
* [ ] Redis latency <10ms

Final Checklist
---------------

Before Launch
~~~~~~~~~~~~~

* [ ] Redis configured and tested
* [ ] HTTPS enabled (wss://)
* [ ] Environment variables set
* [ ] Static files collected
* [ ] Database backed up
* [ ] Migrations run
* [ ] Monitoring configured
* [ ] Error logging setup

After Launch
~~~~~~~~~~~~

* [ ] Monitor error rates
* [ ] Check WebSocket connections
* [ ] Verify message delivery
* [ ] Test from mobile devices
* [ ] Monitor Redis memory
* [ ] Check database performance

Common Issues
-------------

Connection Drops
~~~~~~~~~~~~~~~~

**Symptom**: WebSockets disconnect after 30-60 seconds

**Solution**: Configure Nginx timeout:

.. code-block:: nginx

   proxy_read_timeout 86400;
   proxy_send_timeout 86400;

High Memory Usage
~~~~~~~~~~~~~~~~~

**Symptom**: Redis memory grows unbounded

**Solution**: Set eviction policy:

.. code-block:: redis

   maxmemory 2gb
   maxmemory-policy allkeys-lru

See Also
--------

* :doc:`redis` - Redis setup
* :doc:`nginx` - Nginx configuration
* :doc:`docker` - Docker deployment
* :doc:`monitoring` - Logging and metrics