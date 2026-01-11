Permission Customization
========================

Creating custom permission decorators and handlers for advanced access control.

.. contents:: Table of Contents
   :local:
   :depth: 2

Custom Permission Decorators
-----------------------------

Creating New Decorators
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/decorators.py
   from functools import wraps
   from django.core.exceptions import PermissionDenied
   from channels.db import database_sync_to_async

   def requires_verified_email(method):
       """Only allow users with verified email."""
       @wraps(method)
       async def wrapper(self, data, *args, **kwargs):
           @database_sync_to_async
           def check_verified():
               return self.user.profile.email_verified
           
           if not await check_verified():
               raise PermissionDenied("Email must be verified to perform this action")
           
           return await method(self, data, *args, **kwargs)
       return wrapper

   def requires_premium_subscription(method):
       """Only allow premium users."""
       @wraps(method)
       async def wrapper(self, data, *args, **kwargs):
           @database_sync_to_async
           def check_premium():
               return self.user.profile.is_premium
           
           if not await check_premium():
               raise PermissionDenied("This feature requires premium subscription")
           
           return await method(self, data, *args, **kwargs)
       return wrapper

   def rate_limit(max_calls=10, period=60):
       """Rate limit decorator."""
       from django.core.cache import cache
       
       def decorator(method):
           @wraps(method)
           async def wrapper(self, data, *args, **kwargs):
               key = f"rate_limit:{self.user.id}:{method.__name__}"
               
               @database_sync_to_async
               def check_rate():
                   current = cache.get(key, 0)
                   if current >= max_calls:
                       return False
                   cache.set(key, current + 1, period)
                   return True
               
               if not await check_rate():
                   raise PermissionDenied(f"Rate limit exceeded. Max {max_calls} calls per {period}s")
               
               return await method(self, data, *args, **kwargs)
           return wrapper
       return decorator

Usage in Custom Consumer
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/consumers.py
   from realtime_chat_messaging.consumers import ChatMessagingConsumer
   from myapp.decorators import requires_verified_email, requires_premium_subscription, rate_limit

   class CustomChatConsumer(ChatMessagingConsumer):
       
       @requires_verified_email
       async def receive_message_send_event(self, data, room):
           """Override to require email verification."""
           return await super().receive_message_send_event(data, room)
       
       @requires_premium_subscription
       @rate_limit(max_calls=5, period=60)
       async def handle_create_channel(self, data):
           """Premium feature with rate limiting."""
           # Your channel creation logic
           pass

Custom Permission Handlers
---------------------------

Extending Permission Logic
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/permissions.py
   from realtime_chat_messaging.permissions.handlers import PermissionHandler
   from channels.db import database_sync_to_async

   class CustomPermissionHandler(PermissionHandler):
       
       @staticmethod
       @database_sync_to_async
       def _have_send_message_permission(user, data, default_admin_names={"group": "admins", "channel": "moderators"}):
           """Override to add custom checks."""
           is_permitted, room = PermissionHandler._have_send_message_permission(
               user, data, default_admin_names
           )
           
           if not is_permitted:
               return False, room
           
           # Additional check: user must have verified email
           if not user.profile.email_verified:
               return False, room
           
           # Check if user is banned in this room
           from myapp.models import RoomBan
           if RoomBan.objects.filter(room=room, user=user, is_active=True).exists():
               return False, room
           
           # Check message quota (premium vs free users)
           if not user.profile.is_premium:
               from myapp.models import MessageQuota
               today_count = MessageQuota.get_today_count(user, room)
               if today_count >= 100:  # Free tier limit
                   return False, room
           
           return True, room
       
       @staticmethod
       @database_sync_to_async
       def _have_admin_privileges(user, room_id, default_admin_names={"group": "admins", "channel": "moderators"}):
           """Custom admin check with additional verification."""
           is_permitted, room = PermissionHandler._have_admin_privileges(
               user, room_id, default_admin_names
           )
           
           if not is_permitted:
               return False, room
           
           # Additional check: admins must have 2FA enabled
           if not user.profile.two_factor_enabled:
               return False, room
           
           return True, room

Register Custom Handler
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler"
   }

Advanced Permission Patterns
-----------------------------

Role-Based Permissions
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # myapp/models.py
   from django.db import models

   class RoomRole(models.Model):
       ROLE_CHOICES = [
           ('member', 'Member'),
           ('moderator', 'Moderator'),
           ('admin', 'Admin'),
           ('owner', 'Owner'),
       ]
       
       room = models.ForeignKey('realtime_chat_messaging.Room', on_delete=models.CASCADE)
       user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
       role = models.CharField(max_length=20, choices=ROLE_CHOICES)
       
       class Meta:
           unique_together = ['room', 'user']

   # myapp/decorators.py
   def requires_role(min_role='moderator'):
       """Check if user has minimum role in room."""
       role_hierarchy = {'member': 0, 'moderator': 1, 'admin': 2, 'owner': 3}
       
       def decorator(method):
           @wraps(method)
           async def wrapper(self, data, *args, **kwargs):
               from myapp.models import RoomRole
               from channels.db import database_sync_to_async
               
               @database_sync_to_async
               def check_role(user, room_id):
                   try:
                       user_role = RoomRole.objects.get(user=user, room_id=room_id)
                       return role_hierarchy.get(user_role.role, 0) >= role_hierarchy.get(min_role, 0)
                   except RoomRole.DoesNotExist:
                       return False
               
               room_id = data.get('room_id')
               if not await check_role(self.user, room_id):
                   raise PermissionDenied(f"Requires {min_role} role or higher")
               
               return await method(self, data, *args, **kwargs)
           return wrapper
       return decorator

Time-Based Permissions
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def during_business_hours(method):
       """Only allow during business hours (9 AM - 5 PM)."""
       @wraps(method)
       async def wrapper(self, data, *args, **kwargs):
           from django.utils import timezone
           
           now = timezone.now()
           if not (9 <= now.hour < 17):
               raise PermissionDenied("This action is only available during business hours (9 AM - 5 PM)")
           
           return await method(self, data, *args, **kwargs)
       return wrapper

Content-Based Permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def prohibit_links(method):
       """Don't allow messages with links (spam prevention)."""
       @wraps(method)
       async def wrapper(self, data, *args, **kwargs):
           import re
           
           content = data.get('content', '')
           url_pattern = r'https?://[^\s]+'
           
           if re.search(url_pattern, content):
               # Check if user has permission to post links
               @database_sync_to_async
               def can_post_links():
                   return self.user.has_perm('can_post_links') or self.user.profile.is_premium
               
               if not await can_post_links():
                   raise PermissionDenied("You don't have permission to post links")
           
           return await method(self, data, *args, **kwargs)
       return wrapper

Combining Multiple Decorators
------------------------------

.. code-block:: python

   class CustomChatConsumer(ChatMessagingConsumer):
       
       @ExceptionHandler.exception_handler_decorator
       @requires_verified_email
       @rate_limit(max_calls=30, period=60)
       @prohibit_links
       @can_send_message_to_room
       async def receive_message_send_event(self, data, room):
           """
           Multiple permission checks:
           1. Email must be verified
           2. Max 30 messages per minute
           3. Links prohibited (unless premium)
           4. User can send to this room
           """
           return await super().receive_message_send_event(data, room)

Permission Groups
-----------------

.. code-block:: python

   # myapp/models.py
   class PermissionGroup(models.Model):
       name = models.CharField(max_length=100)
       permissions = models.JSONField(default=list)
       # e.g., ['can_pin_messages', 'can_delete_others_messages', 'can_mute_users']

   class UserPermissionGroup(models.Model):
       user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
       room = models.ForeignKey('realtime_chat_messaging.Room', on_delete=models.CASCADE)
       group = models.ForeignKey(PermissionGroup, on_delete=models.CASCADE)

   # myapp/decorators.py
   def requires_permission(permission_name):
       """Check if user has specific permission in room."""
       def decorator(method):
           @wraps(method)
           async def wrapper(self, data, *args, **kwargs):
               from myapp.models import UserPermissionGroup
               from channels.db import database_sync_to_async
               
               @database_sync_to_async
               def has_permission(user, room_id, perm):
                   groups = UserPermissionGroup.objects.filter(
                       user=user,
                       room_id=room_id
                   ).select_related('group')
                   
                   for upg in groups:
                       if perm in upg.group.permissions:
                           return True
                   return False
               
               room_id = data.get('room_id')
               if not await has_permission(self.user, room_id, permission_name):
                   raise PermissionDenied(f"Missing permission: {permission_name}")
               
               return await method(self, data, *args, **kwargs)
           return wrapper
       return decorator

   # Usage
   @requires_permission('can_pin_messages')
   async def handle_pin_message(self, data, room):
       pass

Testing Permissions
-------------------

.. code-block:: python

   import pytest
   from channels.testing import WebsocketCommunicator
   from myapp.consumers import CustomChatConsumer

   @pytest.mark.asyncio
   async def test_requires_verified_email():
       """Test that unverified users can't send messages."""
       communicator = WebsocketCommunicator(
           CustomChatConsumer.as_asgi(),
           "/messaging/"
       )
       
       # Mock unverified user
       communicator.scope['user'] = create_unverified_user()
       
       connected, _ = await communicator.connect()
       assert connected
       
       # Try to send message
       await communicator.send_json_to({
           "event_type": "message.send",
           "data": {"room_id": "uuid", "content": "test"}
       })
       
       # Should receive permission denied error
       response = await communicator.receive_json_from()
       assert response["error"]["code"] == 4002
       
       await communicator.disconnect()

Best Practices
--------------

1. **Layer Permissions**: Start with broad checks, then narrow down:

   .. code-block:: python

      @is_authenticated  # Broad
      @is_room_member    # Narrower
      @has_role('admin') # Specific

2. **Clear Error Messages**:

   .. code-block:: python

      raise PermissionDenied("Email verification required. Check your inbox.")

3. **Log Permission Denials**:

   .. code-block:: python

      import logging
      logger = logging.getLogger(__name__)
      
      if not permitted:
          logger.warning(f"Permission denied: {user.username} attempted {action}")
          raise PermissionDenied(message)

4. **Cache Permission Checks**:

   .. code-block:: python

      from django.core.cache import cache
      
      cache_key = f"user_perms:{user.id}:{room.id}"
      permissions = cache.get(cache_key)
      
      if permissions is None:
          permissions = calculate_permissions(user, room)
          cache.set(cache_key, permissions, timeout=300)

See Also
--------

* :doc:`../user-guide/permissions` - Permission system overview
* :doc:`consumers` - Custom consumer events
* :doc:`handlers` - Custom business logic