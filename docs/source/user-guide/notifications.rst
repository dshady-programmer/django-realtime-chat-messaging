Notifications Guide
===================

Understanding the notification system and integrating with push notification services.

.. contents:: Table of Contents
   :local:
   :depth: 2

How Notifications Work
----------------------

When ``ENABLE_NOTIFICATION=True``, the package tracks undelivered messages using ``ChatNotification`` model.

Lifecycle
~~~~~~~~~

.. code-block:: text

   Message Sent
        ↓
   ChatNotification Created
   recipients = [all room members except sender]
        ↓
   User Acknowledges Message
        ↓
   User Removed from recipients
        ↓
   recipients.count() == 0?
        ↓
   Delete Notification

On Connect
~~~~~~~~~~

When a user connects, all pending notifications are sent:

.. code-block:: json

   {
       "eventType": "chat.notifications",
       "data": {
           "room-uuid-1": [
               {
                   "id": "notif-uuid",
                   "message": {
                       "id": "msg-uuid",
                       "content": "Hello!",
                       "sender": {"username": "alice"}
                   },
                   "notification_type": "NEW_MESSAGE"
               }
           ],
           "room-uuid-2": [...]
       }
   }

Notification Types
------------------

.. code-block:: python

   NOTIFICATION_TYPE = (
       ('REACTION', 'Reaction'),
       ('NEW_MESSAGE', 'New Message'),
       ('REPLY', 'Reply')
   )

Handling in Frontend
~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   socket.onmessage = (e) => {
       const response = JSON.parse(e.data);
       
       if (response.eventType === 'chat.notifications') {
           const notifications = response.data;
           
           Object.entries(notifications).forEach(([roomId, notifs]) => {
               const unreadCount = notifs.length;
               updateBadge(roomId, unreadCount);
               
               notifs.forEach(notif => {
                   if (notif.notification_type === 'NEW_MESSAGE') {
                       showNotification(notif.message);
                   }
               });
           });
       }
   };

Acknowledging Messages
-----------------------

Mark messages as delivered:

.. code-block:: javascript

   // When message appears in UI
   socket.send(JSON.stringify({
       event_type: 'message.acknowledged',
       data: {
           message_id: messageId
       }
   }));

This removes the user from ``ChatNotification.recipients``.

Push Notification Integration
------------------------------

Firebase Cloud Messaging (FCM)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**1. Install Firebase Admin SDK:**

.. code-block:: bash

   pip install firebase-admin

**2. Override notification handler:**

.. code-block:: python

   # myapp/handlers.py
   from realtime_chat_messaging.utils.handlers import EventHandler
   import firebase_admin
   from firebase_admin import messaging

   # Initialize Firebase
   cred = firebase_admin.credentials.Certificate('path/to/serviceAccountKey.json')
   firebase_admin.initialize_app(cred)

   class CustomEventHandler(EventHandler):
       
       @staticmethod
       def create_chat_notification(message, type, user):
           # Create database notification
           EventHandler.create_chat_notification(message, type, user)
           
           # Send push notification
           room = message.room
           recipients = room.participants.exclude(id=user.id) if hasattr(room, 'participants') else room.subscribers.exclude(id=user.id)
           
           for recipient in recipients:
               if hasattr(recipient, 'fcm_token') and recipient.fcm_token:
                   notification = messaging.Message(
                       notification=messaging.Notification(
                           title=f"New message from {user.username}",
                           body=message.content[:100]
                       ),
                       data={
                           'room_id': str(room.id),
                           'message_id': str(message.id)
                       },
                       token=recipient.fcm_token
                   )
                   messaging.send(notification)

**3. Register in settings:**

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler"
   }

**4. Store FCM tokens:**

.. code-block:: python

   # myapp/models.py
   from django.contrib.auth.models import AbstractUser

   class User(AbstractUser):
       fcm_token = models.CharField(max_length=255, null=True, blank=True)

**5. Update token from frontend:**

.. code-block:: javascript

   // Request permission and get token
   import { getMessaging, getToken } from "firebase/messaging";

   const messaging = getMessaging();
   const token = await getToken(messaging, {
       vapidKey: 'YOUR_VAPID_KEY'
   });

   // Send to backend
   await fetch('/api/update-fcm-token/', {
       method: 'POST',
       headers: {'Content-Type': 'application/json'},
       body: JSON.stringify({token})
   });

AWS SNS
~~~~~~~

.. code-block:: python

   import boto3

   class CustomEventHandler(EventHandler):
       
       @staticmethod
       def create_chat_notification(message, type, user):
           EventHandler.create_chat_notification(message, type, user)
           
           sns = boto3.client('sns', region_name='us-east-1')
           room = message.room
           recipients = room.participants.exclude(id=user.id) if hasattr(room, 'participants') else room.subscribers.exclude(id=user.id)
           
           for recipient in recipients:
               if hasattr(recipient, 'device_endpoint') and recipient.device_endpoint:
                   sns.publish(
                       TargetArn=recipient.device_endpoint,
                       Message=json.dumps({
                           'default': f"New message from {user.username}",
                           'GCM': json.dumps({
                               'notification': {
                                   'title': f"New message from {user.username}",
                                   'body': message.content[:100]
                               }
                           })
                       }),
                       MessageStructure='json'
                   )

OneSignal
~~~~~~~~~

.. code-block:: python

   import requests

   class CustomEventHandler(EventHandler):
       
       @staticmethod
       def create_chat_notification(message, type, user):
           EventHandler.create_chat_notification(message, type, user)
           
           room = message.room
           recipients = room.participants.exclude(id=user.id) if hasattr(room, 'participants') else room.subscribers.exclude(id=user.id)
           
           player_ids = [r.onesignal_player_id for r in recipients if hasattr(r, 'onesignal_player_id') and r.onesignal_player_id]
           
           if player_ids:
               requests.post(
                   'https://onesignal.com/api/v1/notifications',
                   headers={
                       'Authorization': f'Basic {ONESIGNAL_API_KEY}',
                       'Content-Type': 'application/json'
                   },
                   json={
                       'app_id': ONESIGNAL_APP_ID,
                       'include_player_ids': player_ids,
                       'headings': {'en': f"New message from {user.username}"},
                       'contents': {'en': message.content[:100]},
                       'data': {
                           'room_id': str(room.id),
                           'message_id': str(message.id)
                       }
                   }
               )

Disabling Notifications
-----------------------

To disable tracking entirely:

.. code-block:: python

   REALTIME_CHAT_MESSAGING = {
       "ENABLE_NOTIFICATION": False
   }

**Impact:**

* No ``ChatNotification`` records created
* ``chat.notifications`` event not sent on connect
* ``message.acknowledged`` still works (updates ``delivered_to`` field)
* Saves database writes

When to Disable
~~~~~~~~~~~~~~~

* Simple chat without unread counts
* High-volume messaging (performance critical)
* Using external notification system
* Notifications handled elsewhere

Best Practices
--------------

Batch Notifications
~~~~~~~~~~~~~~~~~~~

Don't send push notification for every message in active chat:

.. code-block:: python
    class CustomEventHandler(EventHandler):
        
        def create_chat_notification(self, message, type, user):
            recipients = super().create_chat_notification(message, type, user)
            
            for recipient in recipients:
                send_push_notification(recipient, message)

Notification Preferences
~~~~~~~~~~~~~~~~~~~~~~~~~

Let users control notifications:

.. code-block:: python

   class UserProfile(models.Model):
       user = models.OneToOneField(User, on_delete=models.CASCADE)
       notification_settings = models.JSONField(default=dict)
       # {
       #     'push_enabled': True,
       #     'mentions_only': False,
       #     'muted_rooms': []
       # }

   # Check before sending
   if recipient.profile.notification_settings.get('push_enabled'):
       if str(room.id) not in recipient.profile.notification_settings.get('muted_rooms', []):
           send_push_notification(recipient, message)

See Also
--------

* :doc:`../customization/handlers` - Customizing event handlers
* :doc:`../api-reference/settings` - ENABLE_NOTIFICATION setting