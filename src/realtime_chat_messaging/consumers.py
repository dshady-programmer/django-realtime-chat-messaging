"""
WebSocket consumer for real-time chat messaging using Django Channels.

This module defines the main AsyncWebsocketConsumer responsible for:
- Authentication and session lifecycle management
- Event dispatching and routing
- Room, message, and notification handling
- Group/channel subscription management
"""


from channels.db import database_sync_to_async
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from guardian.utils import get_anonymous_user
from django.contrib.auth import get_user_model

from realtime_chat_messaging.conf import realtime_chat_settings 
from realtime_chat_messaging.utils.loader import import_and_verify_type_class, import_and_verify_type_function
import json
from .utils.cache_utils import (
    fetch_user_groups,
    update_user_groups,
    add_group_to_user_groups,
    remove_group_from_user_groups
)

from .permissions.decorators import (
    can_access_message, can_access_room,
    can_add_members_to_room, can_remove_members_from_room,
    can_send_message_to_room, can_modify_message,
    is_room_admin

)
User = get_user_model()



# Application-level WebSocket close codes.
# These are intentionally distinct from standard WebSocket codes
# to allow frontend clients to handle domain-specific failures.

# 4001: Authentication failed.
# 4002: Permission failed.
# 4003: Validation error.
# 4004: Resource not found.
# 4005: Integrity error.
# 4006: Internal server error.

# Canonical group name formats used across the system.
# These must remain stable to ensure compatibility with
# cached group memberships and session restoration.
USER_OWN_GROUP = "user-{user_id}"
GROUP_STRING = "group-{group_id}"


"""
dispatch_chat_notification (message, reaction, reply)
send_message / receive_message (forwarded, reply)
message_reaction_dispatch
create_chat
create_group_chat
create_channel
user_typing
read_receipt_dispatch
group_join
channel_join
group_leave
channel_leave
modify_group_admins
modify_channel_moderators
remove_subscriber (admin only)
remove_participant (admin only)
add_user_chat_permission (channel and group)

"""


"""
frontend events:

chat.notifications
message.dispatch
messagetyping.dispatch
messagemodification.dispatch
messagedelivered.dispatch
reaction.dispatch
readreceipt.dispatch
roomcreate.dispatch
roomlist.dispatch
roommessages.dispatch
roominfo.dispatch
roomaddmembers.dispatch
roomremovemembers.dispatch
roomexit.dispatch
roomdelete.dispatch
roomupdate.dispatch


"""

# Runtime-configurable handlers loaded via settings to allow
# pluggable behavior across different projects.
event_handler_class = realtime_chat_settings.EVENT_HANDLER_CLASS
exception_handler_class = realtime_chat_settings.EXCEPTION_HANDLER_CLASS
enable_notification = realtime_chat_settings.ENABLE_NOTIFICATION
EventHandler = import_and_verify_type_class(event_handler_class, "EVENT_HANDLER_CLASS")()

class ChatMessagingConsumer(AsyncWebsocketConsumer):
    """
        Asynchronous WebSocket consumer handling real-time chat functionality.

        Responsibilities:
        - Connection authentication and lifecycle management
        - Event routing and dispatch
        - Message, room, and notification workflows
        - Channel group synchronization across sessions
    """
    
    ExceptionHandler = import_and_verify_type_class(exception_handler_class, "EXCEPTION_HANDLER_CLASS")
    async def connect(self):
        """
            Authenticate the WebSocket connection and initialize session state.

            Anonymous or unauthenticated users are rejected with a custom
            close code. On successful authentication, the user's previous
            channel state is restored and pending notifications may be sent.
        """
        user = self.scope["user"]
        
        if user.id is None or user == await database_sync_to_async(get_anonymous_user)():
            await self.close(code=4001)  # custom close code
            return
        

        self.user = user
        await self.channel_cleanup()
        await self.channel_setup()
        
        # print(self.session, self.session.channel_name)
        await self.accept()
        # dispatch all notifications.
        if enable_notification:
            await self.dispatch_chat_notifications()

    async def disconnect(self, close_code):
        """
            Handle WebSocket disconnection.

            Ensures stale channel memberships are removed to prevent
            message leakage across expired sessions.
        """
        if hasattr(self, "user"):
            if self.user.id:
                await self.channel_cleanup()


    async def receive(self, text_data = None, bytes_data = None):
        """
        Route incoming events to their corresponding handlers.

        Incoming payloads must define an ``event_type`` key that maps
        to a callable defined by the configured EVENT_MAPPER.
        
        Args:
            text_data : {
                event_type: string,
                data: {
                    ...
                }
            }
        """
        event_mapper = realtime_chat_settings.EVENT_MAPPER
        EventMapper = import_and_verify_type_function(event_mapper, "EVENT_MAPPER")
        data = json.loads(text_data)

        event_type = data.get("event_type")
        map_event_type_to_handlers = EventMapper(self)
        try:
            await map_event_type_to_handlers[event_type](data.get("data"))
        except KeyError:
            error_msg = {"error": "invalid event type"}
            await self.send(text_data=json.dumps(error_msg))

    @ExceptionHandler.exception_handler_decorator
    async def dispatch_chat_notifications(self):
        """
            Dispatch all pending chat notifications for the connected user.

            This method is typically invoked on initial connection but may
            also be reused by consumers implementing notification refresh
            semantics.
        """
        chat_notifications = await EventHandler.get_and_group_chat_notifications(self.user)

        data = {"eventType": "chat.notifications", "data": chat_notifications}
        await self.send(text_data=json.dumps(data))

    @ExceptionHandler.exception_handler_decorator
    @can_send_message_to_room
    async def receive_message_send_event(self, data, room):
        """
            Handle the ``message.send`` event.

            This event is emitted by the client when a user sends a new message
            to a room. The message may be a standard message, a forwarded message,
            or a reply, depending on the provided payload.

            Message validation, persistence, and serialization are delegated
            to the configured ``EventHandler`` implementation.

            Args:
                data (dict): Event payload containing message data.
                    Expected structure::
                    
                        {
                            "room_id": int | str,
                            "content": str,
                            "extra_fields": {
                                "forwarded_from_id": int,          # optional
                                "parent_message_id": int,          # optional (reply)
                                "media": [                          # optional
                                    {
                                        "media_url": str,
                                        "media_type": str,
                                        "file_size": int,
                                        "mime_type": str,
                                        "metadata": dict
                                    }
                                ]
                            }
                        }

                room (Room): Resolved room instance injected by the
                    ``can_send_message_to_room`` permission decorator.

            Emits:
                - ``message.dispatch``: Broadcast to all room participants.

            Example:
                Client payload::

                    {
                        "event_type": "message.send",
                        "data": {
                            "room_id": 12,
                            "content": "Hello everyone 👋",
                            "extra_fields": {}
                        }
                    }
            note: extra field value must contain model fields validated by the provided serializer
        """
        room_id = room.id
        message = await EventHandler.create_message(data, self.user)
        group_string = GROUP_STRING.format(group_id=room_id)
        # print(group_string)
        await self.send_group(group_string, "message.dispatch", message)
            

    @ExceptionHandler.exception_handler_decorator
    @can_access_message
    async def receive_message_acknowledged_event(self, data):
        """
            Handle the ``message.acknowledged`` event.

            This event indicates that one or more messages have been successfully
            delivered to the recipient. Delivery acknowledgements are sent only
            to the original message sender(s).

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "message_id": int | str | list[int | str]
                        }

            Emits:
                - ``messagedelivered.dispatch``: Sent to the original sender(s).

            Example:
                Client payload::

                    {
                        "event_type": "message.acknowledged",
                        "data": {
                            "message_id": [45, 46]
                        }
                    }
        """

        message_senders = await EventHandler.message_acknowledged(self.user, data["message_id"])
        for sender_id, message in message_senders.items():
            user_group = USER_OWN_GROUP.format(user_id=sender_id)
            await self.send_group(user_group, "messagedelivered.dispatch", message)


    @ExceptionHandler.exception_handler_decorator
    @can_access_message
    async def receive_message_read_event(self, data):
        """
            Handle the ``message.read`` event.

            This event marks one or more messages as read by the current user.
            Read receipts are broadcast to all participants in the affected room(s)
            to update their UI accordingly.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "message_id": int | str | list[int | str]
                        }

            Emits:
                - ``readreceipt.dispatch``: Broadcast to all room participants.

            Example:
                Client payload::

                    {
                        "event_type": "message.read",
                        "data": {
                            "message_id": [45, 46, 47]
                        }
                    }
        """

        room_id, message = await EventHandler.create_read_receipt(self.user, data["message_id"])
        
        if room_id:
            if isinstance(room_id, set):
                for id in room_id:
                    group = GROUP_STRING.format(group_id=id)
                    await self.send_group(group, "readreceipt.dispatch", message[id])
            else:
                group = GROUP_STRING.format(group_id=room_id)
                await self.send_group(group, "readreceipt.dispatch", message)

    @ExceptionHandler.exception_handler_decorator
    @can_access_message
    async def receive_message_reaction_event(self, data):
        """
            Handle the ``message.react`` event.

            This event allows users to add or remove emoji reactions to messages.
            Reaction changes are broadcast to all room participants.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "type": "add" | "remove",
                            "message_id": int | str,
                            "reaction_content": str
                        }

            Emits:
                - ``reaction.dispatch``: Broadcast to all room participants.

            Example:
                Client payload::

                    {
                        "event_type": "message.react",
                        "data": {
                            "type": "add",
                            "message_id": 123,
                            "reaction_content": "👍"
                        }
                    }
        """

        response = await EventHandler.react_to_message(data, self.user)
        room_id = response['message']['room']['id']
        group_string = GROUP_STRING.format(group_id=room_id)
        # print(group_string)
        await self.send_group(group_string, "reaction.dispatch", response)





    @ExceptionHandler.exception_handler_decorator
    @can_send_message_to_room
    async def receive_message_typing_event(self, data, room):
        """
            Handle the ``message.typing`` event.

            This event is emitted by the client to indicate that a user is
            actively typing in a room. Typing events are transient and are
            not persisted.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str
                        }

                room (Room): Resolved room instance injected by the
                    ``can_send_message_to_room`` decorator.

            Emits:
                - ``messagetyping.dispatch``: Broadcast to room participants.

            Example:
                Client payload::

                    {
                        "event_type": "message.typing",
                        "data": {
                            "room_id": 12
                        }
                    }
        """
        
        group_string = GROUP_STRING.format(group_id=room.id)
        # print(group_string)
        await self.send_group(group_string, "messagetyping.dispatch", {"username": self.user.username})


    @ExceptionHandler.exception_handler_decorator
    @can_modify_message
    @can_access_message
    async def receive_message_modify_event(self, data, room):
        """
            Handle the ``message.modify`` event.

            This event allows message authors or authorized users to update or
            delete messages. Update operations modify message content, while delete
            operations mark messages as deleted (if MESSAGE_SOFT_DELETE is enabled).

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "action": "update" | "delete",
                            "message_id": int | str | list[int | str],
                            "extra_fields": {
                                "content": str  # required for update action
                            }
                        }

                room (Room): Resolved room instance injected by the
                    ``can_access_message`` decorator.

            Emits:
                - ``messagemodification.dispatch``: Broadcast to all room participants.

            Example:
                Client payload (update)::

                    {
                        "event_type": "message.modify",
                        "data": {
                            "action": "update",
                            "message_id": 123,
                            "extra_fields": {
                                "content": "Updated message text"
                            }
                        }
                    }

                Client payload (delete)::

                    {
                        "event_type": "message.modify",
                        "data": {
                            "action": "delete",
                            "message_id": [123, 124]
                        }
                    }

            Note:
                For update action, when using a custom message model and serializer,
                ensure that the data passed in ``extra_fields`` is validated and
                cleaned to prevent updating sensitive fields, which could lead to
                security vulnerabilities.

                By default, the provided MessageSerializer will only update the
                content field regardless of other fields passed in ``extra_fields``.
                If you have a custom message model and serializer, consider
                overriding the update method in your serializer to properly clean
                and validate the data.
        """


        response = await EventHandler.modify_message(data)
        if response:
            group_string = GROUP_STRING.format(group_id=room.id)
            await self.send_group(group_string, "messagemodification.dispatch", response)



    @ExceptionHandler.exception_handler_decorator
    @can_access_room
    async def receive_message_list(self, data, room):
        """
        Handle the ``room.messages`` event.

        This event retrieves a paginated list of messages from the specified
        room. Pagination parameters are optional; if not provided, all messages
        in the chat would be retrieved

        Args:
            data (dict): Event payload.
                Expected structure::

                    {
                        "room_id": int | str,
                        "paginate": {               # optional
                            "page": int,
                            "size": int
                        }
                    }

            room (Room): Resolved room instance injected by the
                ``can_access_room`` decorator.

        Emits:
            - ``roommessages.dispatch``: Sent to the requesting user only.

        Example:
            Client payload::

                {
                    "event_type": "room.messages",
                    "data": {
                        "room_id": 12,
                        "paginate": {
                            "page": 1,
                            "size": 50
                        }
                    }
                }
        """

        response = await EventHandler.retreive_messages(room, data)
    

        user_group = USER_OWN_GROUP.format(user_id=self.user.id)
        await self.send_group(user_group, "roommessages.dispatch", response)
        





    @ExceptionHandler.exception_handler_decorator
    async def receive_room_create_event(self, data):
        """
            Handle the ``room.create`` event.

            This event creates a new chat room of the specified type. The room
            type determines which fields are required and how the room is
            configured.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "type": "OneToOneChat" | "GroupChat" | "Channel",
                            "participants": [int | str, ...],  # for OneToOneChat and GroupChat
                            "subscribers": [int | str, ...],   # for Channel only
                            "name": str,                       # for GroupChat and Channel only
                            "description": str,                # optional, for GroupChat and Channel
                            "extra_fields": {
                                "property": {                  # optional
                                    "preferences": dict,       # must be a dict if provided
                                    ...                        # other custom RoomProperty fields
                                },
                                ...                            # other fields matching your model
                            }
                        }

            Emits:
                - ``roomcreate.dispatch``: Broadcast to all room members.

            Example:
                Client payload (GroupChat)::

                    {
                        "event_type": "room.create",
                        "data": {
                            "type": "GroupChat",
                            "name": "Project Team",
                            "description": "Discussion for Project X",
                            "participants": [1, 2, 3, 4],
                            "extra_fields": {
                                "property": {
                                    "preferences": {
                                        "notifications": true
                                    }
                                }
                            }
                        }
                    }

            Note:
                Extra field values must match your custom model fields. If you
                don't pass a ``property`` field, a default property will be
                created based on the model defaults.

                if you have custom property model ensure to handle it properly 
                in the case of empty property field.
        """


        room = await EventHandler.create_room(self.user, data)
        members = None
        if "participants" in room:
            participants = room["participants"]
            members = participants

        elif "subscribers" in room:
            subscribers = room["subscribers"]
            members = subscribers
        group = GROUP_STRING.format(group_id=room["id"])
        if members:
            for member in members:
                member_id = member["id"] # always ensure this is a dict and id field is included in the dict for both participants and subscribers
                await self.add_channel_to_group(group, member_id)
        await self.send_group(group, "roomcreate.dispatch", room)

        

    @ExceptionHandler.exception_handler_decorator
    async def receive_get_rooms(self, _):
        """
            Handle the ``room.list`` event.

            This event retrieves all rooms that the current user has access to,
            including one-to-one chats, group chats, and channels.

            Args:
                _ (dict): Empty payload (no data required).

            Emits:
                - ``roomlist.dispatch``: Sent to the requesting user only.

            Example:
                Client payload::

                    {
                        "event_type": "room.list",
                        "data": {}
                    }
        """

        rooms = await EventHandler.list_rooms(self.user)

        await self.send_group(
            USER_OWN_GROUP.format(user_id=self.user.id),
            "roomlist.dispatch", 
            rooms
        )


    @ExceptionHandler.exception_handler_decorator
    @can_access_room
    async def receive_get_room_info(self, data, room):
        """
            Handle the ``room.info`` event.

            This event retrieves detailed information about a specific room,
            including its members, properties, and metadata.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str
                        }

                room (Room): Resolved room instance injected by the
                    ``can_access_room`` decorator.

            Emits:
                - ``roominfo.dispatch``: Sent to the requesting user only.

            Example:
                Client payload::

                    {
                        "event_type": "room.info",
                        "data": {
                            "room_id": 12
                        }
                    }
        """



        room = await EventHandler.retreive_room(room)

        
        await self.send_group(
            USER_OWN_GROUP.format(user_id=self.user.id),
            "roominfo.dispatch", 
            room
        )


    @ExceptionHandler.exception_handler_decorator
    @can_add_members_to_room
    async def receive_add_members_to_room(self, data, room):
        """
            Handle the ``room.add_members`` event.

            This event adds new members to an existing room. Only users with
            appropriate permissions can add members.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str,
                            "members": [int | str, ...]
                        }

                room (Room): Resolved room instance injected by the
                    ``can_add_members_to_room`` decorator.

            Emits:
                - ``roomaddmembers.dispatch``: Broadcast to all room members.

            Example:
                Client payload::

                    {
                        "event_type": "room.add_members",
                        "data": {
                            "room_id": 12,
                            "members": [5, 6, 7]
                        }
                    }
        """



        users_added, serialized_room, new_member_usernames = await EventHandler.add_members_to_room(data.get('members'), room)
        group = GROUP_STRING.format(group_id=room.id)
        for user in users_added:
            await self.add_channel_to_group(group, user.id)
        await self.send_group(group, "roomaddmembers.dispatch", {"room": serialized_room, "new_members": new_member_usernames, "added_by": self.user.username})

    @ExceptionHandler.exception_handler_decorator
    @can_remove_members_from_room
    async def receive_remove_members_from_room(self, data, room):
        """
            Handle the ``room.remove_members`` event.

            This event removes members from an existing room. Only users with
            appropriate permissions can remove members. Removed users will be
            notified and their channels will be discarded from the room group.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str,
                            "members": [int | str, ...]
                        }

                room (Room): Resolved room instance injected by the
                    ``can_remove_members_from_room`` decorator.

            Emits:
                - ``roomexit.dispatch``: Sent to each removed member.
                - ``roomremovemembers.dispatch``: Broadcast to remaining room members.

            Example:
                Client payload::

                    {
                        "event_type": "room.remove_members",
                        "data": {
                            "room_id": 12,
                            "members": [5, 6]
                        }
                    }
        """


        users_removed, serialized_room, removed_member_usernames = await EventHandler.remove_members_from_room(data.get('members'), room, self.user)
        group = GROUP_STRING.format(group_id=room.id) 

        for user in users_removed:
            await self.discard_channel_from_group(group, user.id)
            user_group = USER_OWN_GROUP.format(user_id=user.id)
            await self.send_group(user_group, "roomexit.dispatch", {"room": serialized_room, "message": f"You have been removed by {self.user.username}"})
        await self.send_group(group, "roomremovemembers.dispatch", {"room": serialized_room, "removed_members": removed_member_usernames, "removed_by": self.user.username})



    @ExceptionHandler.exception_handler_decorator
    @can_access_room
    async def receive_leave_room_event(self, data, room):
        """
            Handle the ``room.leave`` event.

            This event allows a user to voluntarily leave a room. The user's
            channel is removed from the room group, and other members are notified.
            If the room becomes empty as a result, it may be deleted (if default configs are retained).

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str
                        }

                room (Room): Resolved room instance injected by the
                    ``can_access_room`` decorator.

            Emits:
                - ``roomexit.dispatch``: Sent to the leaving user.
                - ``roomremovemembers.dispatch``: Broadcast to remaining room members.
                - ``roomdelete.dispatch``: Sent to the user if the room is deleted.

            Example:
                Client payload::

                    {
                        "event_type": "room.leave",
                        "data": {
                            "room_id": 12
                        }
                    }
        """


        serialized_room = await EventHandler.leave_room(self.user, room)



        group = GROUP_STRING.format(group_id=room.id)
        user_group = USER_OWN_GROUP.format(user_id=self.user.id)
        await self.discard_channel_from_group(group) # remove user channel from group

        if not serialized_room and not room.pk:
            return await self.send_group(user_group, "roomdelete.dispatch", {"room_id": str(room.id)})    

        await self.send_group(user_group, "roomexit.dispatch", {"room": serialized_room, "message": f"You left {room.name}"})

        await self.send_group(group, "roomremovemembers.dispatch", {"room": serialized_room, "removed_members": [self.user.username], "removed_by": "self"}) # frontend should handle displaying the right information when removed_by is self ("username left") or and when it isn't ("username1 removed username2")

    
    @ExceptionHandler.exception_handler_decorator
    async def receive_join_room_event(self, data):
        """
            Handle the ``room.join`` event.

            This event allows a user to join an existing room (typically a Channel
            or public GroupChat). The user's channel is added to the room group,
            and other members are notified.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str
                        }

            Emits:
                - ``roomaddmembers.dispatch``: Broadcast to all room members.

            Example:
                Client payload::

                    {
                        "event_type": "room.join",
                        "data": {
                            "room_id": 12
                        }
                    }

            Note:
                Frontend should handle displaying the appropriate message based on
                the ``added_by`` value: when ``added_by`` is "self", display
                "username joined"; otherwise display "username1 added username2".
        """

        serialized_room = await EventHandler.join_room(self.user, data.get('room_id'))

        group = GROUP_STRING.format(group_id=serialized_room["id"])
        await self.add_channel_to_group(group)
        await self.send_group(group, "roomaddmembers.dispatch", {"room": serialized_room, "new_members": [self.user.username], "added_by": "self"}) # same logic used in room leave/remove applies here



    @ExceptionHandler.exception_handler_decorator
    @is_room_admin
    async def receive_modify_room_event(self, data, room):
        """
            Handle the ``room.modify`` event.

            This event allows room administrators to perform various modifications
            including updating room details, deleting rooms, and managing
            permissions, moderators, and admins.

            Args:
                data (dict): Event payload.
                    Expected structure::

                        {
                            "room_id": int | str,
                            "action": "update" | "delete" | "add_permission" | 
                                    "remove_permission" | "add_moderator" | 
                                    "add_admin" | "remove_moderator" | "remove_admin",
                            "data": {
                                "users": [int | str, ...],              # for role/permission actions
                                "permissions": [str, ...],              # valid room permissions
                                "name": str,                            # for update action (room name for GroupChat|Channels)
                                "description": str,                     # for update action (room description for GroupChat|Channels)
                                "property": {                           # optional, for update action
                                    "preferences": dict,
                                    ...                                 # other custom RoomProperty fields
                                }
                            }
                        }

                room (Room): Resolved room instance injected by the
                    ``is_room_admin`` decorator.

            Emits:
                - ``roomdelete.dispatch``: Broadcast to all members if room is deleted.
                - ``roomupdate.dispatch``: Broadcast to all members for other actions.

            Example:
                Client payload (update)::

                    {
                        "event_type": "room.modify",
                        "data": {
                            "room_id": 12,
                            "action": "update",
                            "data": {
                                "name": "Updated Room Name",
                                "description": "New description"
                            }
                        }
                    }

                Client payload (add moderator)::

                    {
                        "event_type": "room.modify",
                        "data": {
                            "room_id": 12,
                            "action": "add_moderator",
                            "data": {
                                "users": [5, 6]
                            }
                        }
                    }

            Note:
                If you have a custom Room/GroupChat/Channel model different from
                the default provided, or if you extended the default room models,
                the update and other actions might not work as intended especially
                if you have custom implementations or extra fields that needs to 
                be updated asides the default Room fields. Consider rewriting 
                the ``_modify_room`` helper method. See documentation for
                proper implementation guidelines.
        """

        room_data = await EventHandler.modify_room(data, room)
        

        group = GROUP_STRING.format(group_id=room.id)
        if "room_deleted" in room_data and room_data['room_deleted'] is True and room.pk is None:
            await self.send_group(group, "roomdelete.dispatch", {"room_id": str(room.id)})
            for m in room_data["members"]:
                await self.discard_channel_from_group(group, m.id)
            return None
        await self.send_group(group, "roomupdate.dispatch", room_data)

    @ExceptionHandler.exception_handler_decorator    
    async def receive_update_session_heartbeat(self, _):
        """
            Handle the ``session.heartbeat`` event.

            This event updates the last activity timestamp for the user's current
            session, preventing premature session expiration. Clients should send
            heartbeats at regular intervals.

            Args:
                _ (dict): Empty payload (no data required).

            Returns:
                Sends a success confirmation to the client. (no need to await reply in frontend)

            Example:
                Client payload::

                    {
                        "event_type": "session.heartbeat",
                        "data": {}
                    }

            Note:
                The heartbeat interval depends on the client implementation but
                should ideally be sent 2-3 times within the inactivity threshold
                period to ensure reliable session maintenance.
        """

        await EventHandler.update_session(self.session)
        await self.send(text_data=json.dumps({"status": "success"}))


    















    
    
    
    
    
    # --------------------------------------------- #

    # Utils for adding and discarding channels to groups.

    # --------------------------------------------- #

    async def add_channel_to_group(self, group, user_id=None):
        """
            Add user channel(s) to a specified group.

            This helper retrieves all active sessions for a user and adds their
            corresponding channel names to the specified group. It also updates
            the cached group membership for the user.

            Args:
                group (str): The group name to add channels to.
                user_id (int, optional): The user ID whose channels should be added.
                    Defaults to the current user.

            Note:
                All active sessions for the user are added to enable multi-device
                support. Group membership is cached to allow quick restoration on
                reconnection.
        """
        if user_id is None or user_id == self.user.id:
            user_id = self.user.id
 
        active_sessions = await EventHandler.get_active_sessions(user_id)
        
        for channel_name in active_sessions:
            await self.channel_layer.group_add(group, channel_name)

        # store all user groups so it can be added it to their channel layer on every new connection
        await add_group_to_user_groups(user_id, group)

    async def discard_channel_from_group(self, group, user_id=None):
        """
            Remove user channel(s) from a specified group.

            This helper retrieves all active sessions for a user and removes their
            corresponding channel names from the specified group. It also updates
            the cached group membership for the user.

            Args:
                group (str): The group name to remove channels from.
                user_id (int, optional): The user ID whose channels should be removed.
                    Defaults to the current user.

            Note:
                All active sessions for the user are removed to ensure messages are
                not leaked to users who have left a room or been removed.
        """
        if user_id is None or user_id == self.user.id:
            user_id = self.user.id
    
        active_sessions = await EventHandler.get_active_sessions(user_id)
        
        for channel_name in active_sessions:
            await self.channel_layer.group_discard(group, channel_name)

        # store all user groups so that can add it to their channel layer on every new connection
        await remove_group_from_user_groups(user_id, group)


    # --------------------------------------------- #

    # Catch/all broadcast to client helpers

    # --------------------------------------------- #

    async def send_group(self, group, event_type, data):
        """
            Broadcast a message to all members of a group.

            This helper wraps the channel layer's group_send method with a
            standardized message format.

            Args:
                group (str): The group name to broadcast to.
                event_type (str): The event type identifier for the frontend.
                data (dict): The event payload to send.

            Note:
                The message is formatted with a ``type`` field for Channels routing
                and an ``eventType`` field for frontend event handling.
        """
        response = {"type": "broadcast_group", "eventType": event_type, "data": data}
        await self.channel_layer.group_send(group, response)

    async def broadcast_group(self, data):
        """
            Handler for broadcasting messages received via group_send.

            This method is called by the Channels layer when a message is sent to
            a group that this consumer is part of. It forwards the message to the
            WebSocket client.

            Args:
                data (dict): The message data received from the channel layer.

            Note:
                This is an internal handler and should not be called directly.
                The ``type`` field in the message must match this method name
                (with dots replaced by underscores) for Channels routing to work.
        """        

        await self.send(text_data=json.dumps(data))


    # --------------------------------------------- #

    # Helpers for setting up and cleaning up data.

    # for now doesn't support concurrent connections from the same user.
    # --------------------------------------------- #

    async def channel_cleanup(self):
        """
            Clean up expired sessions and stale group memberships.

            This method is called on connection to remove the user's expired
            sessions from all groups they were previously subscribed to. This
            prevents message leakage and ensures clean session management.

            Note:
                This method prevents messages from being sent to disconnected or
                expired sessions, which is critical for security and data integrity.
                
                In the case of multi device connection every connection is treated as
                a session.
        """
        user_id = self.user.id
        groups = await fetch_user_groups(user_id)
        expired_sessions = await EventHandler.get_expired_sessions(user_id)
        # print('expired sessions', expired_sessions)
        for group in groups:
            for channel_name in expired_sessions:
                await self.channel_layer.group_discard(group, channel_name)

    async def channel_setup(self):
        """
            Initialize channel groups and register the user session.

            This method is called on connection to restore the user's group
            memberships and register a new session. The user's personal group
            is automatically added if not already present.

            Note:
                The personal user group (USER_OWN_GROUP) is used for sending
                messages directly to a specific user across all their active
                sessions.
        """
        user_id = self.user.id
        # print('user', self.user)
        groups = await fetch_user_groups(user_id)
        user_own_group = USER_OWN_GROUP.format(user_id=user_id)
        if user_own_group not in groups:
            # add user group to already existing user group.
            groups.append(user_own_group)

            # cache this
            await update_user_groups(user_id, groups)
        for group in groups:
            await self.channel_layer.group_add(group, self.channel_name)
        self.session = await EventHandler.register_session(self.user, self.channel_name)
    
