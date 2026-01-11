Handler Customization
=====================

Overriding event handlers to add custom business logic.

.. contents:: Table of Contents
   :local:
   :depth: 1

Overview
--------

Event handlers contain all business logic. Override methods to customize behavior.

Basic Override
--------------

.. code-block:: python

   # myapp/handlers.py
   from realtime_chat_messaging.utils.handlers import EventHandler

   class CustomEventHandler(EventHandler):
       
 
       def create_chat_notification(self, message, type, user):
           # Call parent
           super().create_chat_notification(message, type, user)
           
           # Add custom logic
           send_push_notification(message, user)

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "EVENT_HANDLER_CLASS": "myapp.handlers.CustomEventHandler"
   }

Common Customizations
---------------------

Message Creation
~~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomEventHandler(EventHandler):
       
       def _create_message(self, data, user):
           # Extract custom fields
           priority = data.get('extra_fields', {}).get('priority', 'normal')
           
           # Call parent
           message_data = super()._create_message(data, user)
           
           # Custom processing
           if priority == 'high':
               send_urgent_notification(message_data)
           
           return message_data

Room Management
~~~~~~~~~~~~~~~

.. code-block:: python

   class CustomEventHandler(EventHandler):
       
       @staticmethod
       def _create_room(user, data):
           room = EventHandler._create_room(user, data)
           
           # Log room creation
           logger.info(f"Room created: {room['id']} by {user.username}")
           
           return room

Permission Customization
------------------------

.. code-block:: python

   # myapp/permissions.py
   from realtime_chat_messaging.permissions.handlers import PermissionHandler

   class CustomPermissionHandler(PermissionHandler):
       
       @staticmethod
       def _have_send_message_permission(user, data, default_admin_names={"group": "admins", "channel": "moderators"}):
           is_permitted, room = PermissionHandler._have_send_message_permission(user, data, default_admin_names)
           
           # Additional check
           if is_permitted and not user.profile.email_verified:
               return False, room
           
           return is_permitted, room

   # settings.py
   REALTIME_CHAT_MESSAGING = {
       "PERMISSION_HANDLER_CLASS": "myapp.permissions.CustomPermissionHandler"
   }

See Also
--------

* :doc:`consumers` - Add custom events
* :doc:`../user-guide/notifications` - Notification integration