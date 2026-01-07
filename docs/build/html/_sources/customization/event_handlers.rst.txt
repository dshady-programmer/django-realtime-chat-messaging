Customizing Event Handlers
===========================

Event handlers contain the business logic for WebSocket events. This guide shows you how to override them to add custom functionality while maintaining compatibility with the package.

Available Event Handlers
------------------------

The package provides 15 event handlers you can override:

**Notifications**

- ``get_and_group_chat_notifications`` - Retrieve and group user notifications

**Messages**

- ``create_message`` - Create new message
- ``react_to_message`` - Add/remove reactions
- ``message_acknowledged`` - Mark message as delivered
- ``modify_message`` - Update or delete messages
- ``create_read_receipt`` - Mark messages as read

**Rooms**

- ``create_room`` - Create new room (OneToOne, Group, Channel)
- ``list_rooms`` - List user's rooms
- ``retreive_room`` - Get room details
- ``retreive_messages`` - Get room messages with pagination
- ``modify_room`` - Update room settings/permissions

**Members**

- ``add_members_to_room`` - Add users to group/channel
- ``remove_members_from_room`` - Remove users from group/channel
- ``leave_room`` - User leaves room voluntarily
- ``join_room`` - User joins public channel

Complete Function Signatures
-----------------------------

get_and_group_chat_notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Retrieve all unread notifications for a user, grouped by room.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def get_and_group_chat_notifications(user: User) -> Dict[str, List[dict]]:
       """
       Get user's notifications grouped by room.
       
       Args:
           user (User): The user requesting notifications
       
       Returns:
           dict: Notifications grouped by room_id
                 {
                     "room-uuid-1": [notification1, notification2],
                     "room-uuid-2": [notification3]
                 }
       """

**Default Implementation:**

.. code-block:: python

   @database_sync_to_async
   def get_and_group_chat_notifications(user):
       from collections import defaultdict
       
       chat_notifications = ChatNotification.objects.filter(
           recipients=user
       ).prefetch_related(
           Prefetch("message__room", queryset=Room.objects.all())
       ).distinct().order_by("-message__room__created_at")
       
       serialized = ChatNotificationSerializer(chat_notifications, many=True).data
       
       grouped = defaultdict(list)
       for notification in serialized:
           room_id = notification["message"]["room"]["id"]
           grouped[room_id].append(notification)
       
       return grouped

**Custom Example: Integrate Push Notifications**

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import (
       get_and_group_chat_notifications as default_notifications
   )
   
   @database_sync_to_async
   def custom_get_notifications(user):
       # Get default notifications
       notifications = await default_notifications(user)
       
       # Send push notifications for any unread
       from myapp.push import send_push_notification
       total_count = sum(len(msgs) for msgs in notifications.values())
       
       if total_count > 0:
           send_push_notification(
               user,
               f"You have {total_count} unread messages"
           )
       
       return notifications

create_message
~~~~~~~~~~~~~~

Create a new message with optional media, replies, or forwards.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def create_message(data: dict, user: User) -> dict:
       """
       Create new message.
       
       Args:
           data (dict): Message data
               {
                   "room_id": str/int (required),
                   "content": str (required unless media),
                   "parent_message": str/int (optional - for replies),
                   "extra_fields": {
                       "is_forwarded": bool,
                       "forwarded_from_id": str/int,
                       "media": [
                           {
                               "media_url": str,
                               "media_type": str,  # "image", "video", "audio", "file"
                               "file_size": int,
                               "mime_type": str,
                               "caption": str (optional),
                               "metadata": dict (optional)
                           }
                       ]
                   }
               }
           user (User): User creating the message
       
       Returns:
           dict: Serialized message data
       """

**Custom Example: Upload Files to S3**

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import create_message
   import boto3
   from django.conf import settings
   
   @database_sync_to_async
   def custom_create_message(data, user):
       # Handle file upload if present
       if 'file' in data:
           file = data.pop('file')
           
           # Upload to S3
           s3 = boto3.client(
               's3',
               aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
               aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
           )
           
           file_key = f"chat-uploads/{user.id}/{file.name}"
           s3.upload_fileobj(file, settings.AWS_STORAGE_BUCKET_NAME, file_key)
           
           # Generate presigned URL
           file_url = s3.generate_presigned_url(
               'get_object',
               Params={
                   'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                   'Key': file_key
               },
               ExpiresIn=3600  # 1 hour
           )
           
           # Add to media array
           data.setdefault('extra_fields', {})
           data['extra_fields']['media'] = [{
               'media_url': file_url,
               'media_type': 'file',
               'file_size': file.size,
               'mime_type': file.content_type,
               'metadata': {'original_name': file.name}
           }]
       
       # Call default handler
       result = await create_message(data, user)
       
       # Log for analytics
       from myapp.analytics import track_event
       track_event('message_sent', user.id, {
           'room_id': data['room_id'],
           'has_media': 'media' in data.get('extra_fields', {})
       })
       
       return result

react_to_message
~~~~~~~~~~~~~~~~~

Add or remove reaction from a message.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def react_to_message(data: dict, user: User) -> dict:
       """
       Add or remove message reaction.
       
       Args:
           data (dict): Reaction data
               {
                   "type": "add" | "remove",
                   "message_id": str/int,
                   "reaction_content": str (required if type="add")
               }
           user (User): User reacting
       
       Returns:
           dict: Response with status and updated message
               {
                   "status": "successful" | "failed",
                   "type": "add" | "remove",
                   "message": {...}  # Full message object
               }
       """

message_acknowledged
~~~~~~~~~~~~~~~~~~~~

Mark message(s) as delivered to user's device.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def message_acknowledged(user: User, message_id: Union[str, int, List[Union[str, int]]]) -> None:
       """
       Mark message(s) as delivered.
       
       Args:
           user (User): User acknowledging
           message_id: Single ID or list of IDs
       
       Returns:
           None (updates ChatNotification internally)
       """

modify_message
~~~~~~~~~~~~~~

Update or delete message(s).

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def modify_message(user: User, data: dict) -> dict:
       """
       Update or delete message(s).
       
       Args:
           user (User): User modifying (must be message sender)
           data (dict): Modification data
               {
                   "action": "update" | "delete",
                   "message_id": str/int | List[str/int],
                   "extra_fields": {  # Required if action="update"
                       "content": str
                   }
               }
       
       Returns:
           dict: Result
               For update:
                   {"status": "successful", "action": "update", "message": {...}}
               For delete:
                   {"status": "successful", "action": "delete", "message_ids": [...]}
       """

**Custom Example: Log Message Deletions**

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import modify_message
   
   @database_sync_to_async
   def custom_modify_message(user, data):
       action = data.get('action')
       message_ids = data.get('message_id')
       
       # Log deletion for compliance
       if action == 'delete':
           from myapp.audit import log_deletion
           log_deletion(
               user=user,
               message_ids=message_ids if isinstance(message_ids, list) else [message_ids],
               timestamp=timezone.now()
           )
       
       # Call default handler
       return await modify_message(user, data)

create_read_receipt
~~~~~~~~~~~~~~~~~~~

Mark message(s) as read by user.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def create_read_receipt(user: User, message_id: Union[str, int, List[Union[str, int]]]) -> Tuple[Union[str, Set[str], None], Union[dict, Dict[str, list]]]:
       """
       Create read receipt(s).
       
       Args:
           user (User): User who read the message(s)
           message_id: Single ID or list of IDs
       
       Returns:
           tuple: (room_id(s), serialized_message(s))
               For single message:
                   (room_id: str, message_data: dict)
               For multiple messages:
                   (room_ids: Set[str], messages_by_room: Dict[str, list])
               If user is message sender:
                   (None, {})
       """

create_room
~~~~~~~~~~~

Create new OneToOneChat, GroupChat, or Channel.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def create_room(user: User, data: dict) -> dict:
       """
       Create new room.
       
       Args:
           user (User): User creating the room (becomes creator for Group/Channel)
           data (dict): Room data
               {
                   "type": "OneToOneChat" | "GroupChat" | "Channel",
                   
                   # For OneToOneChat
                   "participants": [user_id1, user_id2],
                   
                   # For GroupChat
                   "name": str (required),
                   "description": str (optional),
                   "participants": [user_ids],
                   
                   # For Channel
                   "name": str (required),
                   "description": str (optional),
                   "subscribers": [user_ids],
                   
                   "extra_fields": {
                       "max_participants": int (GroupChat),
                       "max_subscribers": int (Channel),
                       "avatar": str (url),
                       "group_locked": bool (GroupChat),
                       "join_approval_required": bool (GroupChat),
                       "is_public": bool (Channel),
                       "preferences": dict
                   }
               }
       
       Returns:
           dict: Serialized room data
       """

**Custom Example: Limit Free Users to 3 Groups**

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import create_room
   from django.core.exceptions import ValidationError
   
   @database_sync_to_async
   def custom_create_room(user, data):
       room_type = data.get('type')
       
       # Enforce limits for free users
       if room_type == 'GroupChat' and not user.profile.is_premium:
           from realtime_chat_messaging.models import GroupChat
           user_groups = GroupChat.objects.filter(creator=user).count()
           
           if user_groups >= 3:
               raise ValidationError(
                   "Free users can only create 3 groups. Upgrade to premium!"
               )
       
       # Call default handler
       room = await create_room(user, data)
       
       # Track in analytics
       from myapp.analytics import track_event
       track_event('room_created', user.id, {
           'type': room_type,
           'is_premium': user.profile.is_premium
       })
       
       return room

list_rooms
~~~~~~~~~~

List all rooms user belongs to.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def list_rooms(user: User) -> List[dict]:
       """
       List user's rooms.
       
       Args:
           user (User): User requesting room list
       
       Returns:
           list: List of serialized rooms (simplified format)
                 Ordered by last_message timestamp (newest first)
       """

retreive_room
~~~~~~~~~~~~~

Get full details of a specific room.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def retreive_room(room: Room) -> dict:
       """
       Get room details.
       
       Args:
           room (Room): Room instance (already fetched and validated)
       
       Returns:
           dict: Full serialized room data
       """

retreive_messages
~~~~~~~~~~~~~~~~~

Get messages for a room with optional pagination.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def retreive_messages(room: Room, data: dict) -> dict:
       """
       Get room messages.
       
       Args:
           room (Room): Room instance
           data (dict): Request data
               {
                   "paginate": {  # Optional
                       "page": int (required if paginating),
                       "size": int (required if paginating)
                   }
               }
       
       Returns:
           dict: Paginated response
               {
                   "has_next": bool,
                   "has_previous": bool,
                   "next_page_number": int | None,
                   "prev_page_number": int | None,
                   "page": int,
                   "size": int,
                   "data": {
                       "room_id": str,
                       "messages": [...]
                   }
               }
       """

**Custom Example: Track Message Views**

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import retreive_messages
   
   @database_sync_to_async
   def custom_retreive_messages(room, data):
       # Call default handler
       result = await retreive_messages(room, data)
       
       # Track analytics
       from myapp.analytics import track_event
       track_event('messages_viewed', {
           'room_id': str(room.id),
           'message_count': len(result['data']['messages']),
           'is_paginated': 'paginate' in data
       })
       
       return result

modify_room
~~~~~~~~~~~

Update room settings, permissions, or roles.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def modify_room(user: User, data: dict, room: Room) -> dict:
       """
       Modify room settings/permissions/roles.
       
       Args:
           user (User): User making changes (must be admin/moderator)
           data (dict): Modification data
               {
                   "action": "update" | "add_permission" | "remove_permission" |
                            "add_admin" | "remove_admin" |
                            "add_moderator" | "remove_moderator",
                   "data": {
                       # For action="update"
                       "name": str (optional),
                       "description": str (optional),
                       "preferences": dict (optional),
                       
                       # For permission actions
                       "users": [user_ids] (required),
                       "permission": [permission_names] (required),
                       
                       # For role actions
                       "users": [user_ids] (required)
                   }
               }
           room (Room): Room instance
       
       Returns:
           dict: Updated room data
       """

add_members_to_room
~~~~~~~~~~~~~~~~~~~

Add users to GroupChat or Channel.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def add_members_to_room(user_ids: List[Union[str, int]], room: Room) -> Tuple[List[User], dict, List[str]]:
       """
       Add members to room.
       
       Args:
           user_ids: List of user IDs to add
           room: Room instance (GroupChat or Channel)
       
       Returns:
           tuple: (added_users, serialized_room, usernames)
               added_users: List of User objects that were added
               serialized_room: Full room data
               usernames: List of usernames of added users
       """

remove_members_from_room
~~~~~~~~~~~~~~~~~~~~~~~~

Remove users from GroupChat or Channel.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def remove_members_from_room(user_ids: List[Union[str, int]], room: Room, session_user: User) -> Tuple[List[User], dict, List[str]]:
       """
       Remove members from room.
       
       Args:
           user_ids: List of user IDs to remove
           room: Room instance (GroupChat or Channel)
           session_user: User performing the removal (cannot remove creator unless self)
       
       Returns:
           tuple: (removed_users, serialized_room, usernames)
               removed_users: List of User objects that were removed
               serialized_room: Full room data
               usernames: List of usernames of removed users
       """

leave_room
~~~~~~~~~~

User leaves a GroupChat or Channel voluntarily.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def leave_room(user: User, room: Room) -> dict:
       """
       User leaves room.
       
       Args:
           user: User leaving
           room: Room instance (must be GroupChat or Channel)
       
       Returns:
           dict: Serialized room data
       
       Raises:
           ValidationError: If trying to leave OneToOneChat
       """

join_room
~~~~~~~~~

User joins a public Channel.

**Signature:**

.. code-block:: python

   @database_sync_to_async
   def join_room(user: User, room_id: Union[str, int]) -> dict:
       """
       User joins room.
       
       Args:
           user: User joining
           room_id: Room ID to join
       
       Returns:
           dict: Serialized room data
       
       Raises:
           ValidationError: If room is not public Channel or is GroupChat
       """

Common Customization Patterns
------------------------------

Pattern 1: Pre-Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add logic before default handler:

.. code-block:: python

   @database_sync_to_async
   def custom_handler(data, user):
       # Validate premium feature
       if data.get('premium_feature') and not user.profile.is_premium:
           raise ValidationError("Premium feature requires subscription")
       
       # Log attempt
       logger.info(f"User {user.id} attempting action")
       
       # Call default
       return await default_handler(data, user)

Pattern 2: Post-Processing
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add logic after default handler:

.. code-block:: python

   @database_sync_to_async
   def custom_handler(data, user):
       # Call default
       result = await default_handler(data, user)
       
       # Send notification
       send_push_notification(user, "Action completed")
       
       # Update cache
       cache.set(f'last_action_{user.id}', timezone.now())
       
       return result

Pattern 3: Wrapping with Error Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_handler(data, user):
       try:
           result = await default_handler(data, user)
           
           # Success tracking
           track_success('handler_name', user.id)
           
           return result
           
       except Exception as e:
           # Error tracking
           sentry_sdk.capture_exception(e)
           track_error('handler_name', user.id, str(e))
           
           raise  # Re-raise after tracking

Pattern 4: Conditional Logic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_handler(data, user):
       # Different logic based on conditions
       if user.is_staff:
           # Staff bypass some checks
           result = await staff_handler(data, user)
       elif user.profile.is_premium:
           # Premium gets extra features
           result = await premium_handler(data, user)
       else:
           # Regular users
           result = await default_handler(data, user)
       
       return result

Best Practices
--------------

1. Always Use @database_sync_to_async
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from channels.db import database_sync_to_async
   
   @database_sync_to_async
   def custom_handler(data, user):
       # Your code
       pass

2. Call Default When Possible
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from realtime_chat_messaging.utils.event_handlers import create_message
   
   @database_sync_to_async
   def custom_create_message(data, user):
       # Custom pre-processing
       data = preprocess(data)
       
       # Call default - reuse validation, serialization, etc.
       result = await create_message(data, user)
       
       # Custom post-processing
       postprocess(result)
       
       return result

3. Match Function Signatures
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your custom handler must accept the same arguments and return the same type:

.. code-block:: python

   # ✅ Correct signature
   @database_sync_to_async
   def custom_create_message(data: dict, user: User) -> dict:
       pass
   
   # ❌ Wrong signature - will break
   @database_sync_to_async
   def custom_create_message(user: User, data: dict):  # Wrong order
       pass

4. Handle Errors Gracefully
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @database_sync_to_async
   def custom_handler(data, user):
       try:
           # Your logic
           result = await default_handler(data, user)
           return result
       except ValidationError as e:
           # Re-raise validation errors
           raise
       except Exception as e:
           # Log unexpected errors
           logger.error(f"Handler failed: {e}")
           sentry_sdk.capture_exception(e)
           raise

5. Ensure Database Connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For handlers that don't call default (rare), ensure connection:

.. code-block:: python

   @database_sync_to_async
   def completely_custom_handler(data, user):
       from django.db import connection
       connection.ensure_connection()
       
       # Your database operations
       pass

Testing Custom Handlers
------------------------

.. code-block:: python

   # tests/test_handlers.py
   from django.test import TestCase
   from asgiref.sync import async_to_sync
   from myapp.handlers import custom_create_message
   
   class CustomHandlerTests(TestCase):
       
       def setUp(self):
           self.user = User.objects.create_user('testuser')
           self.room = Room.objects.create(...)
       
       def test_custom_create_message_uploads_to_s3(self):
           data = {
               'room_id': self.room.id,
               'content': 'Test',
               'file': MockFile('test.pdf')
           }
           
           result = async_to_sync(custom_create_message)(data, self.user)
           
           self.assertIsNotNone(result)
           self.assertIn('media', result['extra_fields'])
           # Verify S3 upload occurred
           self.assertTrue(s3_upload_called)

Next Steps
----------

- :doc:`permissions` - Custom access control
- :doc:`abstract-models` - Extend database models
- :doc:`settings-reference` - Configure handlers in settings