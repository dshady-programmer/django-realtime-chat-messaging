Redis Configuration
===================

Setting up Redis as the channel layer backend for production.

Installation
------------

Ubuntu/Debian
~~~~~~~~~~~~~

.. code-block:: bash

   sudo apt update
   sudo apt install redis-server
   sudo systemctl enable redis-server
   sudo systemctl start redis-server

macOS
~~~~~

.. code-block:: bash

   brew install redis
   brew services start redis

Docker
~~~~~~

.. code-block:: yaml

   # docker-compose.yml
   services:
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"
       volumes:
         - redis_data:/data
       command: redis-server --appendonly yes

   volumes:
     redis_data:

Django Configuration
--------------------

.. code-block:: python

   # settings.py
   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("127.0.0.1", 6379)],
               "capacity": 1500,
               "expiry": 10,
           },
       },
   }

With Password
~~~~~~~~~~~~~

.. code-block:: python

   "CONFIG": {
       "hosts": [("redis://:<password>@127.0.0.1:6379/0")],
   }

Production Settings
-------------------

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [env('REDIS_URL')],
               "capacity": 1500,
               "expiry": 10,
               "group_expiry": 86400,
           },
       },
   }

Monitoring
----------

.. code-block:: bash

   # Check status
   redis-cli ping  # Should return PONG

   # Monitor commands
   redis-cli monitor

   # Check memory
   redis-cli info memory

Performance Tuning
------------------

.. code-block:: redis

   # /etc/redis/redis.conf
   maxmemory 2gb
   maxmemory-policy allkeys-lru
   appendonly yes

Managed Redis
-------------

AWS ElastiCache
~~~~~~~~~~~~~~~

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [("your-cluster.cache.amazonaws.com", 6379)],
           },
       },
   }

Redis Cloud
~~~~~~~~~~~

.. code-block:: python

   CHANNEL_LAYERS = {
       "default": {
           "BACKEND": "channels_redis.core.RedisChannelLayer",
           "CONFIG": {
               "hosts": [env('REDIS_CLOUD_URL')],
           },
       },
   }

See Also
--------

* :doc:`production-checklist` - Complete deployment guide
* :doc:`docker` - Docker setup