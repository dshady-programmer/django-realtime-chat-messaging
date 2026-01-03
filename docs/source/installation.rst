Installation
============

This guide covers installing Django Realtime Chat Messaging and its dependencies.

Requirements
------------

System Requirements
~~~~~~~~~~~~~~~~~~~

- Python 3.8 or higher
- Django 3.2 or higher
- Django Channels 3.0 or higher
- Redis server (for production)

The package automatically installs these required dependencies:

- ``django-channels`` - WebSocket support
- ``channels-redis`` - Redis channel layer backend
- ``django-polymorphic`` - Polymorphic model support
- ``django-guardian`` - Object-level permissions
- ``djangorestframework`` - Serialization
- ``django-rest-polymorphic`` - Polymorphic serializers
- ``drf-recursive`` - Recursive serializer fields
- ``bleach`` - HTML sanitization

Installing the Package
----------------------

Using pip
~~~~~~~~~

The recommended way to install:

.. code-block:: bash

   pip install django-realtime-chat-messaging

This installs the package and all required dependencies.

Using Poetry
~~~~~~~~~~~~

If you're using Poetry for dependency management:

.. code-block:: bash

   poetry add django-realtime-chat-messaging

Using pipenv
~~~~~~~~~~~~

For pipenv users:

.. code-block:: bash

   pipenv install django-realtime-chat-messaging

Development Installation
~~~~~~~~~~~~~~~~~~~~~~~~

To install from source for development:

.. code-block:: bash

   git clone https://github.com/shady-cj/django-realtime-chat-messaging.git
   cd django-realtime-chat-messaging
   pip install -e .

Installing Redis
----------------

Redis is required for production deployments and recommended for development.

Ubuntu/Debian
~~~~~~~~~~~~~

.. code-block:: bash

   sudo apt-get update
   sudo apt-get install redis-server
   sudo systemctl start redis
   sudo systemctl enable redis

macOS
~~~~~

Using Homebrew:

.. code-block:: bash

   brew install redis
   brew services start redis

Windows
~~~~~~~

**Option 1: WSL2 (Recommended)**

Install Windows Subsystem for Linux and follow Ubuntu instructions above.

**Option 2: Redis for Windows**

Download from `Redis Windows Port <https://github.com/microsoftarchive/redis/releases>`_

**Option 3: Docker**

.. code-block:: bash

   docker run -d -p 6379:6379 --name redis redis:latest

Verifying Installation
----------------------

Test Redis Connection
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   redis-cli ping

Expected output: ``PONG``

Test Package Import
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   python -c "import realtime_chat_messaging; print(realtime_chat_messaging.__version__)"

Expected output: ``0.1.0``

Virtual Environment Setup
--------------------------

We strongly recommend using a virtual environment:

.. code-block:: bash

   # Create virtual environment
   python -m venv venv

   # Activate it
   # On Linux/macOS:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate

   # Install package
   pip install django-realtime-chat-messaging

Dependencies Overview
---------------------

Understanding what gets installed:

**Core Dependencies**

.. code-block:: text

   channels>=4.0.0          # WebSocket protocol support
   channels-redis>=4.0.0    # Redis backend for channels
   django>=3.2              # Django framework
   redis>=4.0.0             # Redis client

**Data & Serialization**

.. code-block:: text

   djangorestframework>=3.14.0              # REST framework
   django-polymorphic>=3.1.0                # Polymorphic models
   django-rest-polymorphic>=0.1.10          # Polymorphic serializers
   drf-recursive>=0.4.0                     # Recursive fields

**Security & Permissions**

.. code-block:: text

   django-guardian>=2.4.0                   # Object-level permissions
   bleach>=6.0.0                            # HTML sanitization

**ASGI Server (Production)**

.. code-block:: text

   daphne>=4.0.0           # ASGI server (install separately)
   # OR
   uvicorn>=0.20.0         # Alternative ASGI server

Next Steps
----------

After installation, proceed to :doc:`quickstart` to configure your Django project.

Troubleshooting
---------------

Common Installation Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue**: ``ModuleNotFoundError: No module named 'channels'``

**Solution**: The package should install channels automatically. If not:

.. code-block:: bash

   pip install channels

**Issue**: Redis connection errors during testing

**Solution**: Verify Redis is running:

.. code-block:: bash

   redis-cli ping

If not running:

.. code-block:: bash

   # Linux/macOS
   redis-server

   # Or with systemd
   sudo systemctl start redis

   # Windows (WSL)
   sudo service redis-server start

**Issue**: ``ImportError: cannot import name 'get_user_model'``

**Solution**: Ensure Django is installed and up to date:

.. code-block:: bash

   pip install --upgrade django

**Issue**: Permission denied when installing

**Solution**: Use virtual environment or install with ``--user``:

.. code-block:: bash

   pip install --user django-realtime-chat-messaging

**Issue**: Conflicting dependencies

**Solution**: Create a fresh virtual environment:

.. code-block:: bash

   python -m venv fresh_env
   source fresh_env/bin/activate  # or fresh_env\Scripts\activate on Windows
   pip install django-realtime-chat-messaging

Dependency Version Compatibility
---------------------------------

Tested Configurations
~~~~~~~~~~~~~~~~~~~~~

The package is tested with these combinations:

.. list-table::
   :header-rows: 1
   :widths: 20 20 20

   * - Python
     - Django
     - Channels
   * - 3.8
     - 3.2, 4.0, 4.1, 4.2
     - 3.0, 4.0
   * - 3.9
     - 3.2, 4.0, 4.1, 4.2
     - 3.0, 4.0
   * - 3.10
     - 4.0, 4.1, 4.2, 5.0
     - 4.0
   * - 3.11
     - 4.1, 4.2, 5.0
     - 4.0
   * - 3.12
     - 4.2, 5.0
     - 4.0

Upgrading
---------

To upgrade to the latest version:

.. code-block:: bash

   pip install --upgrade django-realtime-chat-messaging

Check the :doc:`changelog` for breaking changes before upgrading.

Uninstalling
------------

To completely remove the package:

.. code-block:: bash

   pip uninstall django-realtime-chat-messaging

.. warning::
   Run migrations to remove database tables before uninstalling if you want to clean up your database:

   .. code-block:: bash

      # This will remove all chat data
      python manage.py migrate realtime_chat_messaging zero