Customizing Permissions
=======================

Permissions control who can access and modify rooms and messages. This guide shows you how to override default permission functions to implement custom access control.

Available Permission Functions
------------------------------

The package provides 6 permission functions you can override:

1. ``have_room_permission`` - Can user access a room?
2. ``have_message_permission`` - Can user access message(s)?
3. ``is_message_sender`` - Is user the sender of message(s)?
4. ``have_room_permissions_to_add_or_remove_members`` - Can user add/remove members?
5. ``have_send_message_permission`` - Can user send messages to room?
6. ``have_admin_privileges`` - Is user an admin/moderator of room?

Complete Function Signatures
-----------------------------

have_room_permission
~~~~~~~~~~~~~~~~~~~~

Check if user can access a room (for viewing, fetching messages, etc.).

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def have_room_permission(user: User, room_id: Union[str, int]) -> Tuple[bool, Room]:
       """
       Check if user can access room.
       
       Args:
           user: User requesting access
           room_id: ID of room to check
       
       Returns:
           tuple: (is_permitted: bool, room: Room instance)
       
       Default Logic:
           - OneToOneChat: User must be a participant
           - GroupChat: User must be a participant
           - Channel: User must be a subscriber
       """

**Default Implementation:**

.. code-block:: python

   @database_sync_to_async
   def have_room_permission(user, room_id):
       from django.db import connection
       connection.ensure_connection()
       
       if type(room_id) not in [str, int]:
           raise ValidationError("Invalid room_id type")
       
       room = get_object_or_404(Room, id=room_id)
       is_permitted = False
       
       if hasattr(room, "participants"):
           # OneToOneChat or GroupChat
           if room.participants.filter(pk=user.pk).exists():
               is_permitted = True
       elif hasattr(room, "subscribers"):
           # Channel
           if room.subscribers.filter(pk=user.pk).exists():
               is_permitted = True
       
       return is_permitted, room

**Custom Example: Premium Rooms**

.. code-block:: python

   from realtime_chat_messaging.permissions.helpers import have_room_permission as default_check
   
   @database_sync_to_async
   def custom_room_permission(user, room_id):
       # Check default permission first
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           return False, room
       
       # Additional check: Premium rooms require subscription
       if hasattr(room, 'is_premium') and room.is_premium:
           if not hasattr(user, 'profile') or not user.profile.is_subscribed:
               return False, room
       
       # Additional check: Time-based access
       if hasattr(room, 'access_hours'):
           from django.utils import timezone
           current_hour = timezone.now().hour
           
           if current_hour < room.access_hours['start'] or current_hour > room.access_hours['end']:
               return False, room
       
       return True, room

have_message_permission
~~~~~~~~~~~~~~~~~~~~~~~

Check if user can access message(s) (for reading, reacting, etc.).

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def have_message_permission(user: User, message_id: Union[str, int, List[Union[str, int]]]) -> bool:
       """
       Check if user can access message(s).
       
       Args:
           user: User requesting access
           message_id: Single message ID or list of IDs
       
       Returns:
           bool: True if user can access all messages, False otherwise
       
       Default Logic:
           User must be member of the room containing the message(s)
       """

**Default Implementation:**

.. code-block:: python

   @database_sync_to_async
   def have_message_permission(user, message_id):
       from django.db import connection
       connection.ensure_connection()
       
       if type(message_id) not in [list, str, int]:
           raise ValidationError("Invalid message_id type")
       
       is_permitted = True
       
       def is_member(message):
           is_mem = False
           if hasattr(message.room, "participants"):
               if message.room.participants.filter(pk=user.pk).exists():
                   is_mem = True
           elif hasattr(message.room, "subscribers"):
               if message.room.subscribers.filter(pk=user.pk).exists():
                   is_mem = True
           return is_mem
       
       if not isinstance(message_id, list):
           message_id = [message_id]
       else:
           message_id = list(set(message_id))
       
       for id in message_id:
           message = get_object_or_404(Message, pk=id)
           is_permitted = is_member(message)
           if not is_permitted:
               break
       
       return is_permitted

is_message_sender
~~~~~~~~~~~~~~~~~

Check if user is the sender of message(s) (for editing/deleting).

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def is_message_sender(user: User, message_id: Union[str, int, List[Union[str, int]]]) -> Tuple[bool, Room]:
       """
       Check if user is sender of message(s).
       
       Args:
           user: User to check
           message_id: Single message ID or list of IDs
       
       Returns:
           tuple: (is_permitted: bool, room: Room instance)
       
       Validation:
           - All messages must be from same room
           - User must be sender of ALL messages
       """

**Custom Example: Allow Admins to Modify Any Message**

.. code-block:: python

   from realtime_chat_messaging.permissions.helpers import is_message_sender as default_check
   
   @database_sync_to_async
   def custom_message_sender_check(user, message_id):
       # Check if user is sender
       is_sender, room = await default_check(user, message_id)
       
       if is_sender:
           return True, room
       
       # Allow admins/moderators to modify any message
       if hasattr(room, 'admins'):
           # GroupChat
           if user in room.admins.all() or user == room.creator:
               return True, room
       elif hasattr(room, 'moderators'):
           # Channel
           if user in room.moderators.all() or user == room.creator:
               return True, room
       
       return False, room

have_room_permissions_to_add_or_remove_members
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check if user can add or remove members from room.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def have_room_permissions_to_add_or_remove_members(
       user: User, 
       room_id: Union[str, int], 
       perm_phrase: str
   ) -> Tuple[bool, Room]:
       """
       Check if user can add or remove members.
       
       Args:
           user: User attempting action
           room_id: Room ID
           perm_phrase: "add_new" or "remove"
       
       Returns:
           tuple: (is_permitted: bool, room: Room instance)
       
       Default Logic:
           GroupChat:
               - Creator: Always permitted
               - Admins: Always permitted
               - Users with specific permission: Permitted
           
           Channel:
               - Creator: Always permitted
               - Moderators: Always permitted
               - Users with specific permission: Permitted
       """

**Custom Example: Limit Member Addition**

.. code-block:: python

   from realtime_chat_messaging.permissions.helpers import (
       have_room_permissions_to_add_or_remove_members as default_check
   )
   
   @database_sync_to_async
   def custom_member_permission(user, room_id, perm_phrase):
       # Check default permission
       is_permitted, room = await default_check(user, room_id, perm_phrase)
       
       if not is_permitted:
           return False, room
       
       # Additional check for adding members
       if perm_phrase == "add_new":
           # Free users can't add more than 5 members per day
           if not user.profile.is_premium:
               from django.utils import timezone
               from datetime import timedelta
               
               today_start = timezone.now().replace(hour=0, minute=0, second=0)
               
               # Count additions today
               additions_today = MemberAdditionLog.objects.filter(
                   user=user,
                   room=room,
                   added_at__gte=today_start
               ).count()
               
               if additions_today >= 5:
                   return False, room
       
       return True, room

have_send_message_permission
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check if user can send messages to room.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def have_send_message_permission(user: User, data: dict) -> Tuple[bool, Room]:
       """
       Check if user can send message to room.
       
       Args:
           user: User attempting to send
           data: Message data containing room_id or message_id (for replies)
       
       Returns:
           tuple: (is_permitted: bool, room: Room instance)
       
       Default Logic:
           Channel:
               - Creator: Permitted
               - Moderators: Permitted
               - Users with can_send_messages permission: Permitted
           
           GroupChat (if group_locked=True):
               - Creator: Permitted
               - Admins: Permitted
           
           GroupChat (if group_locked=False):
               - All participants: Permitted
           
           OneToOneChat:
               - Both participants: Permitted
       """

**Custom Example: Rate Limiting**

.. code-block:: python

   from realtime_chat_messaging.permissions.helpers import have_send_message_permission as default_check
   from django.core.cache import cache
   
   @database_sync_to_async
   def custom_send_permission(user, data):
       # Check default permission
       is_permitted, room = await default_check(user, data)
       
       if not is_permitted:
           return False, room
       
       # Rate limiting: 10 messages per minute for free users
       if not user.profile.is_premium:
           cache_key = f"message_rate_{user.id}_{room.id}"
           message_count = cache.get(cache_key, 0)
           
           if message_count >= 10:
               raise ValidationError(
                   "Rate limit exceeded. Premium users have unlimited messaging."
               )
           
           # Increment counter
           cache.set(cache_key, message_count + 1, 60)  # 60 seconds TTL
       
       return True, room

have_admin_privileges
~~~~~~~~~~~~~~~~~~~~~

Check if user has admin/moderator privileges in room.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def have_admin_privileges(user: User, room_id: Union[str, int]) -> Tuple[bool, Room]:
       """
       Check if user has admin privileges.
       
       Args:
           user: User to check
           room_id: Room ID
       
       Returns:
           tuple: (is_permitted: bool, room: Room instance)
       
       Default Logic:
           GroupChat:
               - Creator: Has privileges
               - Admins: Has privileges
           
           Channel:
               - Creator: Has privileges
               - Moderators: Has privileges
           
           OneToOneChat:
               - Not applicable (returns False for non-Group/Channel)
       """

Using Decorators
----------------

Permission functions are used via decorators on consumer methods:

.. code-block:: python

   from realtime_chat_messaging.permissions.decorators import (
       can_access_room,
       can_access_message,
       can_send_message_to_room,
       can_modify_message,
       can_add_members_to_room,
       can_remove_members_from_room,
       is_room_admin
   )

Example of decorator usage:

.. code-block:: python

   class CustomChatConsumer(ChatMessagingConsumer):
       
       @ExceptionHandler.exception_handler_decorator
       @can_send_message_to_room
       async def receive_message_send_event(self, data, room):
           # 'room' is injected by decorator after permission check
           # Only called if user has permission
           pass

Common Customization Patterns
------------------------------

Pattern 1: Subscription Tiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def premium_room_permission(user, room_id):
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           return False, room
       
       # Check subscription tier
       if hasattr(room, 'required_tier'):
           user_tier = user.profile.subscription_tier
           required_tier = room.required_tier
           
           tier_hierarchy = ['free', 'basic', 'premium', 'enterprise']
           
           if tier_hierarchy.index(user_tier) < tier_hierarchy.index(required_tier):
               return False, room
       
       return True, room

Pattern 2: Time-Based Access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def time_based_permission(user, room_id):
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           return False, room
       
       from django.utils import timezone
       
       # Check access schedule
       if hasattr(room, 'access_schedule'):
           now = timezone.now()
           current_day = now.strftime('%A').lower()
           current_time = now.time()
           
           schedule = room.access_schedule.get(current_day)
           
           if not schedule:
               return False, room
           
           if not (schedule['start'] <= current_time <= schedule['end']):
               return False, room
       
       return True, room

Pattern 3: Geographic Restrictions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def geo_restricted_permission(user, room_id):
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           return False, room
       
       # Check geographic restrictions
       if hasattr(room, 'allowed_countries'):
           user_country = user.profile.country
           
           if user_country not in room.allowed_countries:
               return False, room
       
       return True, room

Pattern 4: Role-Based Access
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def role_based_permission(user, room_id):
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           return False, room
       
       # Check user roles
       if hasattr(room, 'required_roles'):
           user_roles = set(user.profile.roles)
           required_roles = set(room.required_roles)
           
           if not user_roles.intersection(required_roles):
               return False, room
       
       return True, room

Pattern 5: Content Moderation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def moderation_permission(user, data):
       is_permitted, room = await default_send_permission(user, data)
       
       if not is_permitted:
           return False, room
       
       # Check if user is shadowbanned
       if hasattr(user, 'profile') and user.profile.is_shadowbanned:
           # Allow send but don't actually broadcast
           # (Handle in custom handler)
           return True, room
       
       # Check user reputation
       if user.profile.reputation_score < room.min_reputation:
           return False, room
       
       return True, room

Configuration
-------------

Override permissions in settings:

.. code-block:: python

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       'PERMISSIONS': {
           'have_room_permission': 'myapp.permissions.custom_room_permission',
           'have_message_permission': 'myapp.permissions.custom_message_permission',
           'is_message_sender': 'myapp.permissions.custom_sender_check',
           'have_room_permissions_to_add_or_remove_members': 'myapp.permissions.custom_member_permission',
           'have_send_message_permission': 'myapp.permissions.custom_send_permission',
           'have_admin_privileges': 'myapp.permissions.custom_admin_check',
       },
   }

Best Practices
--------------

1. Always Call Default First
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_permission(user, room_id):
       # Check default logic
       is_permitted, room = await default_permission(user, room_id)
       
       if not is_permitted:
           # Respect default denial
           return False, room
       
       # Add custom checks
       # ...
       
       return True, room

2. Match Return Types
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # ✅ Correct - returns (bool, Room)
   @database_sync_to_async
   def custom_room_permission(user, room_id):
       # ...
       return is_permitted, room
   
   # ❌ Wrong - returns only bool
   @database_sync_to_async
   def custom_room_permission(user, room_id):
       # ...
       return is_permitted  # Missing room!

3. Use Database Connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_permission(user, room_id):
       from django.db import connection
       connection.ensure_connection()
       
       # Your database queries
       pass

4. Handle Edge Cases
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_permission(user, room_id):
       # Validate inputs
       if not user or not user.is_authenticated:
           raise ValidationError("User must be authenticated")
       
       if not room_id:
           raise ValidationError("room_id is required")
       
       # Your logic
       pass

5. Log Permission Denials
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_permission(user, room_id):
       is_permitted, room = await default_check(user, room_id)
       
       if not is_permitted:
           logger.warning(
               f"Permission denied: user={user.id}, room={room_id}, "
               f"reason=not_member"
           )
       
       # Custom checks with logging
       if custom_check_failed:
           logger.warning(
               f"Permission denied: user={user.id}, room={room_id}, "
               f"reason=premium_required"
           )
           return False, room
       
       return True, room

Testing Custom Permissions
---------------------------

.. code-block:: python

   # tests/test_permissions.py
   from django.test import TestCase
   from asgiref.sync import async_to_sync
   from myapp.permissions import custom_room_permission
   
   class PermissionTests(TestCase):
       
       def setUp(self):
           self.user = User.objects.create_user('testuser')
           self.premium_user = User.objects.create_user('premium')
           self.premium_user.profile.is_subscribed = True
           self.premium_user.profile.save()
           
           self.premium_room = Room.objects.create(is_premium=True)
           self.premium_room.participants.add(self.user, self.premium_user)
       
       def test_premium_room_requires_subscription(self):
           """Non-premium users can't access premium rooms"""
           is_permitted, room = async_to_sync(custom_room_permission)(
               self.user,
               self.premium_room.id
           )
           
           self.assertFalse(is_permitted)
       
       def test_premium_user_can_access_premium_room(self):
           """Premium users can access premium rooms"""
           is_permitted, room = async_to_sync(custom_room_permission)(
               self.premium_user,
               self.premium_room.id
           )
           
           self.assertTrue(is_permitted)

Next Steps
----------

- :doc:`abstract-models` - Extend models with custom fields
- :doc:`overview` - Customization principles
- :doc:`settings-reference` - Configure permissions in settings