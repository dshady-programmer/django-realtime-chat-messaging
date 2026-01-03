Authentication Setup
====================

Django Realtime Chat Messaging requires authenticated users for WebSocket connections. This guide covers various authentication methods.

Authentication Requirement
--------------------------

The package expects ``scope["user"]`` to contain an authenticated user object. If the user is anonymous or None, the connection is rejected with close code 4001.

.. code-block:: python

   # In ChatMessagingConsumer.connect()
   user = self.scope["user"]
   
   if user.id is None or user is AnonymousUser:
       await self.close(code=4001)  # Authentication failed
       return

Available Authentication Methods
---------------------------------

Method 1: Session Authentication (Default)
-------------------------------------------

Best for: Traditional Django apps with session-based auth

How It Works
~~~~~~~~~~~~

Django sessions work with WebSocket connections using Channels' ``AuthMiddlewareStack``.

Configuration
~~~~~~~~~~~~~

**ASGI Setup:**

.. code-block:: python

   # asgi.py
   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')
   django.setup()

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from channels.auth import AuthMiddlewareStack  # Session auth
   from realtime_chat_messaging.routing import websocket_urlpatterns

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           AuthMiddlewareStack(  # Provides session authentication
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

**Settings:**

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       ...
       'django.contrib.sessions',  # Required
   ]

   MIDDLEWARE = [
       ...
       'django.contrib.sessions.middleware.SessionMiddleware',  # Required
       'django.contrib.auth.middleware.AuthenticationMiddleware',  # Required
   ]

Frontend Usage
~~~~~~~~~~~~~~

**JavaScript (Browser):**

.. code-block:: javascript

   // Browser automatically sends session cookie
   const ws = new WebSocket('ws://127.0.0.1:8000/messaging/');

   ws.onopen = () => {
       console.log('Connected with session auth');
   };

**Important**: Session cookies are automatically included in WebSocket connections from the same domain.

Pros and Cons
~~~~~~~~~~~~~

**Pros:**

- Simple to implement
- Works automatically with Django admin
- No additional packages needed
- Cookies handled by browser

**Cons:**

- Limited to same-domain connections
- CSRF considerations
- Not ideal for mobile apps or third-party clients

Method 2: JWT Authentication
-----------------------------

Best for: SPAs, mobile apps, cross-domain requests

How It Works
~~~~~~~~~~~~

JWT tokens are passed via query parameters or headers and validated by middleware.

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install django-channels-jwt-auth-middleware

Configuration
~~~~~~~~~~~~~

**ASGI Setup:**

.. code-block:: python

   # asgi.py
   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')
   django.setup()  # Important!

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack
   from realtime_chat_messaging.routing import websocket_urlpatterns

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           JWTAuthMiddlewareStack(  # JWT authentication
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

**Settings:**

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       ...
       'rest_framework',
       'rest_framework_simplejwt',
   ]

   REST_FRAMEWORK = {
       'DEFAULT_AUTHENTICATION_CLASSES': [
           'rest_framework_simplejwt.authentication.JWTAuthentication',
       ],
   }

   from datetime import timedelta

   SIMPLE_JWT = {
       'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
       'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
   }

Frontend Usage
~~~~~~~~~~~~~~

**JavaScript:**

.. code-block:: javascript

   // Get JWT token from your auth endpoint
   const token = localStorage.getItem('access_token');

   // Connect with token in query parameter
   const ws = new WebSocket(
       `ws://127.0.0.1:8000/messaging/?token=${token}`
   );

   ws.onopen = () => {
       console.log('Connected with JWT');
   };

   ws.onerror = (error) => {
       console.error('Connection failed - check token validity');
   };

**React Example:**

.. code-block:: javascript

   import { useEffect, useState } from 'react';

   function ChatComponent() {
       const [ws, setWs] = useState(null);

       useEffect(() => {
           const token = localStorage.getItem('access_token');
           const socket = new WebSocket(
               `ws://localhost:8000/messaging/?token=${token}`
           );

           socket.onopen = () => console.log('Connected');
           socket.onclose = (e) => {
               if (e.code === 4001) {
                   console.error('Authentication failed');
                   // Refresh token or redirect to login
               }
           };

           setWs(socket);

           return () => socket.close();
       }, []);

       return <div>Chat UI</div>;
   }

Token Refresh Handling
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   let ws = null;
   let reconnectInterval = null;

   function connect() {
       const token = localStorage.getItem('access_token');
       ws = new WebSocket(`ws://localhost:8000/messaging/?token=${token}`);

       ws.onclose = (event) => {
           if (event.code === 4001) {
               // Token expired, try to refresh
               refreshToken().then(newToken => {
                   localStorage.setItem('access_token', newToken);
                   // Reconnect with new token
                   setTimeout(connect, 1000);
               }).catch(() => {
                   // Refresh failed, redirect to login
                   window.location.href = '/login';
               });
           }
       };
   }

   async function refreshToken() {
       const refresh = localStorage.getItem('refresh_token');
       const response = await fetch('/api/token/refresh/', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           body: JSON.stringify({ refresh })
       });
       const data = await response.json();
       return data.access;
   }

Pros and Cons
~~~~~~~~~~~~~

**Pros:**

- Works cross-domain
- Great for mobile apps
- Stateless authentication
- Easy token refresh

**Cons:**

- Requires additional package
- More complex setup
- Token management on frontend
- Security considerations (XSS)

Method 3: Token Authentication
-------------------------------

Best for: API-based authentication without JWT complexity

How It Works
~~~~~~~~~~~~

Uses Django REST Framework's token authentication.

Installation
~~~~~~~~~~~~

.. code-block:: bash

   pip install channels-auth-token-middleware

Configuration
~~~~~~~~~~~~~

**ASGI Setup:**

.. code-block:: python

   # asgi.py
   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')
   django.setup()

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from channels_auth_token_middleware.middleware import SimpleJWTAuthMiddlewareStack
   from realtime_chat_messaging.routing import websocket_urlpatterns

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           TokenAuthMiddlewareStack(
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

**Settings:**

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       ...
       'rest_framework',
       'rest_framework.authtoken',
   ]

   REST_FRAMEWORK = {
       'DEFAULT_AUTHENTICATION_CLASSES': [
           'rest_framework.authentication.TokenAuthentication',
       ],
   }

Frontend Usage
~~~~~~~~~~~~~~

.. code-block:: javascript

   const token = localStorage.getItem('auth_token');
   const ws = new WebSocket(
       `ws://127.0.0.1:8000/messaging/?token=${token}`
   );

Method 4: Custom Authentication
--------------------------------

Best for: Custom authentication schemes or legacy systems

How It Works
~~~~~~~~~~~~

You create a custom middleware that extracts and validates user credentials.

Implementation
~~~~~~~~~~~~~~

**Create Middleware:**

.. code-block:: python

   # yourproject/middleware.py
   from channels.db import database_sync_to_async
   from channels.middleware import BaseMiddleware
   from django.contrib.auth import get_user_model
   from django.contrib.auth.models import AnonymousUser

   User = get_user_model()

   @database_sync_to_async
   def get_user_from_custom_token(token):
       """
       Custom token validation logic
       """
       try:
           # Your custom validation here
           user = User.objects.get(custom_token=token)
           return user
       except User.DoesNotExist:
           return AnonymousUser()

   class CustomAuthMiddleware(BaseMiddleware):
       async def __call__(self, scope, receive, send):
           # Extract token from query string
           query_string = scope.get('query_string', b'').decode()
           params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
           token = params.get('token')

           if token:
               scope['user'] = await get_user_from_custom_token(token)
           else:
               scope['user'] = AnonymousUser()

           return await super().__call__(scope, receive, send)

   def CustomAuthMiddlewareStack(inner):
       return CustomAuthMiddleware(inner)

**ASGI Setup:**

.. code-block:: python

   # asgi.py
   from yourproject.middleware import CustomAuthMiddlewareStack

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           CustomAuthMiddlewareStack(
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

Frontend Usage
~~~~~~~~~~~~~~

.. code-block:: javascript

   const customToken = getUserCustomToken();
   const ws = new WebSocket(
       `ws://127.0.0.1:8000/messaging/?token=${customToken}`
   );

Testing Authentication
----------------------

Test in Django Shell
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from channels.testing import WebsocketCommunicator
   from yourproject.asgi import application
   from django.contrib.auth import get_user_model

   User = get_user_model()
   user = User.objects.get(username='testuser')

   # Create communicator
   communicator = WebsocketCommunicator(application, "/messaging/")
   communicator.scope['user'] = user

   # Test connection
   connected, _ = await communicator.connect()
   assert connected

   await communicator.disconnect()

Test with Browser DevTools
~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open browser DevTools (F12)
2. Go to Network tab
3. Filter by "WS" (WebSocket)
4. Attempt connection
5. Check connection status and headers

Security Best Practices
-----------------------

Session Authentication
~~~~~~~~~~~~~~~~~~~~~~

1. **Enable CSRF Protection:**

   .. code-block:: python

      # settings.py
      CSRF_COOKIE_HTTPONLY = True
      CSRF_COOKIE_SECURE = True  # In production
      SESSION_COOKIE_SECURE = True  # In production

2. **Set Secure Cookie Settings:**

   .. code-block:: python

      SESSION_COOKIE_SAMESITE = 'Lax'
      CSRF_COOKIE_SAMESITE = 'Lax'

JWT Authentication
~~~~~~~~~~~~~~~~~~

1. **Use Short-Lived Tokens:**

   .. code-block:: python

      SIMPLE_JWT = {
          'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
          'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
      }

2. **Implement Token Rotation:**

   .. code-block:: python

      SIMPLE_JWT = {
          'ROTATE_REFRESH_TOKENS': True,
          'BLACKLIST_AFTER_ROTATION': True,
      }

3. **Store Tokens Securely:**

   .. code-block:: javascript

      // Use httpOnly cookies or secure storage
      // Never store in localStorage if XSS is a concern
      
      // Better approach:
      document.cookie = `token=${token}; Secure; SameSite=Strict`;

General Security
~~~~~~~~~~~~~~~~

1. **Use WSS in Production:**

   .. code-block:: text

      wss://yourdomain.com/messaging/

2. **Validate Origin:**

   .. code-block:: python

      # Already included in setup
      from channels.security.websocket import AllowedHostsOriginValidator

3. **Rate Limiting:**

   Implement connection rate limiting (see :doc:`advanced/scaling`)

Troubleshooting
---------------

Connection Closes Immediately (Code 4001)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Cause**: User not authenticated or token invalid

**Solutions**:

1. Verify user is logged in (session auth)
2. Check token validity (JWT/Token auth)
3. Ensure middleware is configured correctly
4. Check authentication backend is installed

Invalid Token Format
~~~~~~~~~~~~~~~~~~~~

**Error**: Connection accepted but user is AnonymousUser

**Solutions**:

1. Verify token is being sent: Check browser Network tab
2. Check query parameter name matches middleware expectation
3. Ensure token hasn't expired

CORS Issues
~~~~~~~~~~~

**Error**: WebSocket connection blocked by CORS

**Solution**: Configure CORS for WebSocket:

.. code-block:: python

   # settings.py
   CORS_ALLOWED_ORIGINS = [
       "http://localhost:3000",
       "https://yourdomain.com",
   ]

   CORS_ALLOW_CREDENTIALS = True

Session Not Persisting
~~~~~~~~~~~~~~~~~~~~~~~

**Error**: Session works for HTTP but not WebSocket

**Solutions**:

1. Ensure session middleware is enabled
2. Check cookie domain settings
3. Verify SameSite cookie settings
4. Use same domain for HTTP and WebSocket

Next Steps
----------

Now that authentication is configured:

- :doc:`websocket/connection` - Learn about connection lifecycle
- :doc:`websocket/message-events` - Start sending messages
- :doc:`frontend/javascript-examples` - See complete frontend examples
- :doc:`advanced/deployment` - Deploy to production