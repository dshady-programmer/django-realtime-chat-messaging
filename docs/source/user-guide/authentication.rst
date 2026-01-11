Authentication Guide
====================

Complete guide to authenticating WebSocket connections. Covers session authentication, JWT tokens, and custom authentication methods.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

Django Realtime Chat Messaging requires authentication for all WebSocket connections. Anonymous users are automatically disconnected with close code 4001.

The package supports:

* **Session Authentication** - Django's built-in session system (easiest for server-rendered apps)
* **JWT Authentication** - Token-based authentication (recommended for SPAs/mobile apps)
* **Custom Authentication** - Implement your own authentication middleware

How Authentication Works
-------------------------

Connection Flow
~~~~~~~~~~~~~~~

.. code-block:: text

   Client                          Server
   ------                          ------
   1. WebSocket.connect()   -->    
                            <--    2. Check authentication
                                      ├─ Valid user?
                                      │  ├─ Yes: Accept connection
                                      │  └─ No: Close with code 4001
   3. Receive events        <-->   4. Authenticated communication

**Authentication Check:**

.. code-block:: python

   # In ChatMessagingConsumer.connect()
   user = self.scope["user"]
   
   if user.id is None or user == get_anonymous_user():
       await self.close(code=4001)  # Authentication failed
       return
   
   # User authenticated, proceed
   await self.accept()

The ``user`` comes from the authentication middleware you configure in your ASGI application.

Session Authentication
----------------------

Uses Django's built-in session cookies. Best for server-rendered apps.

Setup
~~~~~

**1. Configure ASGI application:**

.. code-block:: python

   # myproject/asgi.py
   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
   django.setup()  # CRITICAL: Load Django first

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from channels.auth import AuthMiddlewareStack
   from realtime_chat_messaging.routing import websocket_urlpatterns

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           AuthMiddlewareStack(  # <-- Session authentication
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

**2. Configure session settings:**

.. code-block:: python

   # settings.py
   SESSION_COOKIE_HTTPONLY = False  # Allow JavaScript to read cookie
   SESSION_COOKIE_SAMESITE = 'Lax'
   SESSION_COOKIE_SECURE = True  # HTTPS only in production

.. warning::
   Setting ``SESSION_COOKIE_HTTPONLY = False`` allows JavaScript to read the session cookie. This is necessary for WebSocket connections but slightly reduces security. Only do this if you need WebSocket authentication via sessions.

Frontend Implementation
~~~~~~~~~~~~~~~~~~~~~~~

**Step 1: Login via Django**

.. code-block:: html

   <!-- login.html -->
   <form method="POST" action="{% url 'login' %}">
       {% csrf_token %}
       <input type="text" name="username" required>
       <input type="password" name="password" required>
       <button type="submit">Login</button>
   </form>

**Step 2: Connect to WebSocket**

After successful login, the session cookie is automatically sent:

.. code-block:: javascript

   // No additional headers needed - session cookie sent automatically
   const socket = new WebSocket('ws://localhost:8000/messaging/');
   
   socket.onopen = () => {
       console.log('✅ Connected with session authentication');
   };
   
   socket.onclose = (e) => {
       if (e.code === 4001) {
           alert('Not authenticated. Please login.');
           window.location.href = '/login/';
       }
   };

Complete Example
~~~~~~~~~~~~~~~~

.. code-block:: python

   # views.py
   from django.contrib.auth import authenticate, login
   from django.contrib.auth.decorators import login_required
   from django.shortcuts import render, redirect

   def login_view(request):
       if request.method == 'POST':
           username = request.POST['username']
           password = request.POST['password']
           user = authenticate(request, username=username, password=password)
           
           if user:
               login(request, user)
               return redirect('chat')
           else:
               return render(request, 'login.html', {'error': 'Invalid credentials'})
       
       return render(request, 'login.html')

   @login_required
   def chat_view(request):
       return render(request, 'chat.html', {
           'user': request.user
       })

.. code-block:: html

   <!-- chat.html -->
   <script>
       const socket = new WebSocket('ws://' + window.location.host + '/messaging/');
       
       socket.onopen = () => {
           console.log('Connected as {{ user.username }}');
       };
   </script>

Pros and Cons
~~~~~~~~~~~~~

**Pros:**

* ✅ Simple setup - uses Django's built-in authentication
* ✅ No token management needed
* ✅ Works with Django's session system
* ✅ CSRF protection available

**Cons:**

* ❌ Requires cookies (doesn't work with some mobile apps)
* ❌ Session must be active on same domain
* ❌ Less suitable for SPAs/mobile apps
* ❌ Requires ``SESSION_COOKIE_HTTPONLY = False``

JWT Authentication
------------------

Token-based authentication. Recommended for SPAs, mobile apps, and modern frontends.

Setup
~~~~~

**1. Install dependencies:**

.. code-block:: bash

   pip install djangorestframework-simplejwt djangochannelsrestframework django-channels-jwt-auth-middleware

**2. Configure Django REST Framework:**

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       # ...
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
       'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
       'ROTATE_REFRESH_TOKENS': True,
   }

**3. Configure ASGI with JWT middleware:**

.. code-block:: python

   # myproject/asgi.py
   import os
   import django

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
   django.setup()  # CRITICAL

   from django.core.asgi import get_asgi_application
   from channels.routing import ProtocolTypeRouter, URLRouter
   from channels.security.websocket import AllowedHostsOriginValidator
   from django_channels_jwt_auth_middleware.auth import JWTAuthMiddlewareStack
   from realtime_chat_messaging.routing import websocket_urlpatterns

   application = ProtocolTypeRouter({
       "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(
           JWTAuthMiddlewareStack(  # <-- JWT authentication
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

**4. Add token endpoints:**

.. code-block:: python

   # urls.py
   from rest_framework_simplejwt.views import (
       TokenObtainPairView,
       TokenRefreshView,
   )

   urlpatterns = [
       path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
       path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
       # ... other URLs
   ]

Frontend Implementation
~~~~~~~~~~~~~~~~~~~~~~~

**Step 1: Obtain JWT Token**

.. code-block:: javascript

   async function login(username, password) {
       const response = await fetch('/api/token/', {
           method: 'POST',
           headers: {
               'Content-Type': 'application/json',
           },
           body: JSON.stringify({username, password})
       });
       
       const data = await response.json();
       
       if (response.ok) {
           localStorage.setItem('access_token', data.access);
           localStorage.setItem('refresh_token', data.refresh);
           return data.access;
       } else {
           throw new Error('Authentication failed');
       }
   }

**Step 2: Connect with JWT Token**

.. code-block:: javascript

   function connectWebSocket() {
       const token = localStorage.getItem('access_token');
       
       if (!token) {
           window.location.href = '/login/';
           return;
       }
       
       // Pass token as query parameter
       const socket = new WebSocket(
           `ws://localhost:8000/messaging/?token=${token}`
       );
       
       socket.onopen = () => {
           console.log('✅ Connected with JWT authentication');
       };
       
       socket.onclose = (e) => {
           if (e.code === 4001) {
               // Token expired or invalid
               refreshToken().then(() => {
                   connectWebSocket();  // Retry with new token
               }).catch(() => {
                   window.location.href = '/login/';
               });
           }
       };
       
       return socket;
   }

**Step 3: Token Refresh**

.. code-block:: javascript

   async function refreshToken() {
       const refreshToken = localStorage.getItem('refresh_token');
       
       const response = await fetch('/api/token/refresh/', {
           method: 'POST',
           headers: {
               'Content-Type': 'application/json',
           },
           body: JSON.stringify({refresh: refreshToken})
       });
       
       if (response.ok) {
           const data = await response.json();
           localStorage.setItem('access_token', data.access);
           return data.access;
       } else {
           // Refresh token expired, need to login again
           localStorage.clear();
           throw new Error('Session expired');
       }
   }

Complete React Example
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   import { useState, useEffect, useRef } from 'react';

   function useWebSocket() {
       const [socket, setSocket] = useState(null);
       const [connected, setConnected] = useState(false);
       const reconnectAttempts = useRef(0);

       useEffect(() => {
           connectWebSocket();
           
           return () => {
               if (socket) {
                   socket.close();
               }
           };
       }, []);

       const connectWebSocket = () => {
           const token = localStorage.getItem('access_token');
           
           if (!token) {
               window.location.href = '/login/';
               return;
           }
           
           const ws = new WebSocket(
               `ws://localhost:8000/messaging/?token=${token}`
           );
           
           ws.onopen = () => {
               console.log('Connected');
               setConnected(true);
               reconnectAttempts.current = 0;
           };
           
           ws.onclose = (e) => {
               setConnected(false);
               
               if (e.code === 4001) {
                   // Try to refresh token
                   refreshToken().then(() => {
                       connectWebSocket();
                   }).catch(() => {
                       window.location.href = '/login/';
                   });
               } else if (reconnectAttempts.current < 5) {
                   // Reconnect with exponential backoff
                   setTimeout(() => {
                       reconnectAttempts.current++;
                       connectWebSocket();
                   }, Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000));
               }
           };
           
           setSocket(ws);
       };

       return {socket, connected};
   }

   async function refreshToken() {
       const refreshToken = localStorage.getItem('refresh_token');
       
       const response = await fetch('/api/token/refresh/', {
           method: 'POST',
           headers: {'Content-Type': 'application/json'},
           body: JSON.stringify({refresh: refreshToken})
       });
       
       if (response.ok) {
           const data = await response.json();
           localStorage.setItem('access_token', data.access);
           return data.access;
       }
       
       throw new Error('Token refresh failed');
   }

Pros and Cons
~~~~~~~~~~~~~

**Pros:**

* ✅ Stateless - no session storage required
* ✅ Works perfectly with SPAs and mobile apps
* ✅ Easy to implement token refresh
* ✅ Secure - no cookies involved
* ✅ Can pass user info in token (claims)

**Cons:**

* ❌ More complex setup
* ❌ Need to handle token refresh logic
* ❌ Token can't be invalidated server-side (until expiry)
* ❌ Requires HTTPS in production

Token Security Best Practices
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**1. Use Short Access Token Lifetime**

.. code-block:: python

   SIMPLE_JWT = {
       'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Short-lived
       'REFRESH_TOKEN_LIFETIME': timedelta(days=7),     # Long-lived
   }

**2. Store Tokens Securely**

.. code-block:: javascript

   // Good: localStorage (for web apps)
   localStorage.setItem('access_token', token);
   
   // Better: Secure storage (for mobile apps)
   // Use react-native-keychain or similar

**3. Clear Tokens on Logout**

.. code-block:: javascript

   function logout() {
       localStorage.clear();
       if (socket) {
           socket.close();
       }
       window.location.href = '/login/';
   }

**4. Use HTTPS in Production**

.. code-block:: nginx

   # nginx.conf
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location /messaging/ {
           proxy_pass http://localhost:8000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
       }
   }

Custom Authentication
---------------------

Implement your own authentication middleware for custom requirements.

Creating Custom Middleware
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/middleware.py
   from channels.db import database_sync_to_async
   from django.contrib.auth.models import AnonymousUser
   from urllib.parse import parse_qs

   @database_sync_to_async
   def get_user_from_custom_token(token):
       from myapp.models import CustomToken
       try:
           token_obj = CustomToken.objects.get(key=token, is_active=True)
           return token_obj.user
       except CustomToken.DoesNotExist:
           return AnonymousUser()

   class CustomAuthMiddleware:
       def __init__(self, app):
           self.app = app

       async def __call__(self, scope, receive, send):
           # Get token from query string
           query_string = parse_qs(scope['query_string'].decode())
           token = query_string.get('token', [None])[0]
           
           if token:
               scope['user'] = await get_user_from_custom_token(token)
           else:
               scope['user'] = AnonymousUser()
           
           return await self.app(scope, receive, send)

   def CustomAuthMiddlewareStack(inner):
       return CustomAuthMiddleware(inner)

**Use in ASGI:**

.. code-block:: python

   # asgi.py
   from myapp.middleware import CustomAuthMiddlewareStack

   application = ProtocolTypeRouter({
       "websocket": AllowedHostsOriginValidator(
           CustomAuthMiddlewareStack(
               URLRouter(websocket_urlpatterns)
           )
       ),
   })

OAuth2 / Social Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For OAuth2 providers (Google, Facebook, GitHub):

**1. Use django-allauth:**

.. code-block:: bash

   pip install django-allauth

**2. Configure OAuth:**

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       # ...
       'django.contrib.sites',
       'allauth',
       'allauth.account',
       'allauth.socialaccount',
       'allauth.socialaccount.providers.google',
   ]

   SITE_ID = 1

**3. After OAuth login, issue JWT:**

.. code-block:: python

   # views.py
   from rest_framework_simplejwt.tokens import RefreshToken

   def oauth_callback(request):
       # After successful OAuth authentication
       user = request.user
       
       refresh = RefreshToken.for_user(user)
       
       return JsonResponse({
           'access': str(refresh.access_token),
           'refresh': str(refresh)
       })

**4. Use JWT for WebSocket:**

.. code-block:: javascript

   // Frontend receives tokens from OAuth callback
   const {access, refresh} = await oauthLogin();
   
   localStorage.setItem('access_token', access);
   localStorage.setItem('refresh_token', refresh);
   
   // Connect with JWT
   const socket = new WebSocket(
       `ws://localhost:8000/messaging/?token=${access}`
   );

API Key Authentication
~~~~~~~~~~~~~~~~~~~~~~

For machine-to-machine communication:

.. code-block:: python

   # middleware.py
   from channels.db import database_sync_to_async

   @database_sync_to_async
   def get_user_from_api_key(api_key):
       from myapp.models import APIKey
       try:
           key_obj = APIKey.objects.select_related('user').get(
               key=api_key,
               is_active=True
           )
           return key_obj.user
       except APIKey.DoesNotExist:
           return AnonymousUser()

   class APIKeyAuthMiddleware:
       def __init__(self, app):
           self.app = app

       async def __call__(self, scope, receive, send):
           headers = dict(scope['headers'])
           api_key = headers.get(b'x-api-key', b'').decode()
           
           if api_key:
               scope['user'] = await get_user_from_api_key(api_key)
           else:
               scope['user'] = AnonymousUser()
           
           return await self.app(scope, receive, send)

**Frontend usage:**

.. code-block:: javascript

   // Not standard WebSocket API, need custom implementation
   // or pass in URL
   const socket = new WebSocket(
       `ws://localhost:8000/messaging/?api_key=${apiKey}`
   );

Troubleshooting
---------------

Connection Closes Immediately (Code 4001)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue:** WebSocket connects then immediately closes with code 4001.

**Cause:** User not authenticated.

**Solutions:**

For Session Auth:

1. Check if user is logged in: ``request.user.is_authenticated``
2. Verify session cookie is being sent
3. Check ``SESSION_COOKIE_HTTPONLY`` setting

For JWT Auth:

1. Verify token is valid: ``jwt.decode(token, SECRET_KEY, algorithms=['HS256'])``
2. Check token is being passed correctly: ``?token=...``
3. Ensure middleware is configured in ASGI

CORS Errors
~~~~~~~~~~~

**Issue:** WebSocket connection fails with CORS error.

**Solution:** Configure CORS headers:

.. code-block:: python

   # settings.py
   INSTALLED_APPS = [
       'corsheaders',
       # ...
   ]

   MIDDLEWARE = [
       'corsheaders.middleware.CorsMiddleware',
       # ...
   ]

   CORS_ALLOWED_ORIGINS = [
       "http://localhost:3000",  # React dev server
       "https://yourdomain.com",
   ]

   # For WebSockets
   CORS_ALLOW_CREDENTIALS = True

Token Expired During Active Connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Issue:** User connected, but token expires mid-session.

**Solution:** Implement heartbeat with token refresh:

.. code-block:: javascript

   setInterval(async () => {
       const token = localStorage.getItem('access_token');
       const decoded = jwt_decode(token);
       
       // If token expires in <5 minutes, refresh
       if (decoded.exp * 1000 - Date.now() < 5 * 60 * 1000) {
           await refreshToken();
       }
   }, 60 * 1000);  // Check every minute

Production Recommendations
--------------------------

For Session Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py (production)
   SESSION_COOKIE_SECURE = True
   SESSION_COOKIE_HTTPONLY = False  # Required for WebSocket
   SESSION_COOKIE_SAMESITE = 'Lax'
   CSRF_COOKIE_SECURE = True

For JWT Authentication
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py (production)
   SIMPLE_JWT = {
       'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
       'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
       'ROTATE_REFRESH_TOKENS': True,
       'BLACKLIST_AFTER_ROTATION': True,  # Install djangorestframework-simplejwt[crypto]
       'ALGORITHM': 'HS256',
       'SIGNING_KEY': env('SECRET_KEY'),  # Use environment variable
   }

For All Methods
~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py
   ALLOWED_HOSTS = ['yourdomain.com']
   
   # Use wss:// (WebSocket Secure) in production
   # ws://localhost:8000  (development)
   # wss://yourdomain.com (production)

See Also
--------

* :doc:`../deployment/production-checklist` - Production deployment guide
* :doc:`../deployment/nginx` - Nginx configuration
* :doc:`../troubleshooting` - Common issues
* :doc:`frontend-integration` - Complete frontend examples

Need Help?
----------

* :doc:`../faq` - Frequently asked questions
* `GitHub Discussions <https://github.com/shady-cj/django-realtime-chat-messaging/discussions>`_