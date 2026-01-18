
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

event_mapper = realtime_chat_settings.EVENT_MAPPER
event_handler_class = realtime_chat_settings.EVENT_HANDLER_CLASS
exception_handler_class = realtime_chat_settings.EXCEPTION_HANDLER_CLASS
enable_notification = realtime_chat_settings.ENABLE_NOTIFICATION


# 4001: Authentication failed.
# 4002: Permission failed.
# 4003: Validation error.
# 4004: Resource not found.
# 4005: Integrity error.
# 4006: Internal server error.


# Events
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

e_handler = import_and_verify_type_class(event_handler_class, "EVENT_HANDLER_CLASS")

EventHandler = e_handler()

class ChatMessagingConsumer(AsyncWebsocketConsumer):

    
    ExceptionHandler = import_and_verify_type_class(exception_handler_class, "EXCEPTION_HANDLER_CLASS")
    async def connect(self):
        
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
        if hasattr(self, "user"):
            if self.user.id:
                await self.channel_cleanup()


    async def receive(self, text_data = None, bytes_data = None):
        EventMapper = import_and_verify_type_function(event_mapper, "EVENT_MAPPER")
        data = json.loads(text_data)
        """
        data : {
            event_type: string,
            data: {
                ...
            }
        }
        """
        event_type = data.get("event_type")
        map_event_type_to_handlers = EventMapper(self)
        try:
            await map_event_type_to_handlers[event_type](data.get("data"))
        except KeyError:
            error_msg = {"error": "invalid event type"}
            await self.send(text_data=json.dumps(error_msg))

    @ExceptionHandler.exception_handler_decorator
    async def dispatch_chat_notifications(self):

        chat_notifications = await EventHandler.get_and_group_chat_notifications(self.user)
        await self.send_group(
            USER_OWN_GROUP.format(user_id=self.user.id),
            "chat.notifications",
            chat_notifications,
        )

    @ExceptionHandler.exception_handler_decorator
    @can_send_message_to_room
    async def receive_message_send_event(self, data, room):
        """
        receive_message_send_event

        data: {
            room_id: string/int,
            content: text, 
            extra_fields: {
                ... 
                forwarded_from_id: <only if message is forwarded>
                parent_message_id: <only for reply messages>
                media: [
                    {
                        media_url: string
                        media_type: 'audio/image/video/file'
                        file_size: int
                        mime_type: valid_mime_type (check types.py)
                        metadata: {}
                    }, 
                    ...
                ]
                
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
        receive_message_acknowledged_event
        
        this also means message is delivered to the recipient...

        data: {
            message_id: string/int or List<string/int>,
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
        receive_message_read_event
        
        data: {
            message_id: string/int or List<string/int>        
        }

        broadcasts the message/messages with the updated read_receipts
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
        receive_message_reaction_event
        
        data: {
            type: 'add'/'remove'
            message_id: string <id>,
            reaction_content: text
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
        receive_message_typing_event
        
        data: {
            room_id: string
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
        receive_message_modify_event
        
        data: {
            action: "update" / "delete"
            message_id: string/int (update) / [string/int, string/int] (for delete)
            extra_fields: [
                content: text (for update action)
            ]
        }
        Note: No matter what extra fields are passed only content is updated
        """


        response = await EventHandler.modify_message(data)
        if response:
            group_string = GROUP_STRING.format(group_id=room.id)
            await self.send_group(group_string, "messagemodification.dispatch", response)



    @ExceptionHandler.exception_handler_decorator
    @can_access_room
    async def receive_message_list(self, data, room):
        """
        receive_message_list
        
        data: {
            room_id: string 
            paginate: { 
                <pagination is optional>
                page: <page_number>,
                size: <page_size>
            
            }
        }
        """

        response = await EventHandler.retreive_messages(room, data)
    

        user_group = USER_OWN_GROUP.format(user_id=self.user.id)
        await self.send_group(user_group, "roommessages.dispatch", response)
        





    @ExceptionHandler.exception_handler_decorator
    async def receive_room_create_event(self, data):
        """
        receive_room_create_event
        
        data: {
            type: OneToOneChat, GroupChat, Channel,
            participants: [user1, user2 ...] ( for groupchat and onetoone only )
            subscribers: [user1, user2 ...] (for channel only)
            name: string (for groupchat and channel only)
            description: string(optional, for groupchat and channel only)
            extra_fields: {
                ... 
                preferences: {} (if passing preferences, it must be a dict)
            } ( extra fields must match with the model fields)


        }
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
                member_id = member["id"]
                await self.add_channel_to_group(group, member_id)
        
        await self.send_group(group, "roomcreate.dispatch", room)

        

    @ExceptionHandler.exception_handler_decorator
    async def receive_get_rooms(self, _):
        """
        receive_get_rooms
        
        data: empty
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
        receive_get_room_info
        
        data : {
        room_id
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
        receive_add_members_to_room
        
        data: {
        room_id: "",
        members: [userIds]
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
        receive_remove_members_from_room
        data: {
        room_id: "",
        members: [userIds]
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
        receive_leave_room_event
        
        data: {
            room_id: string
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
        receive_join_room_event
        
        data: {
            room_id: string
        }
        """

        serialized_room = await EventHandler.join_room(self.user, data.get('room_id'))

        group = GROUP_STRING.format(group_id=serialized_room["id"])
        await self.add_channel_to_group(group)
        await self.send_group(group, "roomaddmembers.dispatch", {"room": serialized_room, "new_members": [self.user.username], "added_by": "self"}) # same logic used in room leave/remove applies here



    @ExceptionHandler.exception_handler_decorator
    @is_room_admin
    async def receive_modify_room_event(self, data, room):
        """
        receive_modify_room_event
        
        data: {
            room_id: ""
            action: "update" / "delete" / "add_permission" /  "remove_permission" / "add_moderator" / "add_admin" / "remove_moderator" / "remove_admin"
            data: {
                ...
                users: []
                permissions: [] <Must be valid permission based on the type of room you're modifying>
            }
        }
         
         
         
        Note: if you have a different model for Room/GroupChat/Channel other than the default provided 
        or you extended the default room models, update and other actions might not work as intended 
        consider rewriting your _modify_room helper method. See docs to implement this properly
        """

        room_data = await EventHandler.modify_room(data, room)
        

        group = GROUP_STRING.format(group_id=room.id)
        if "room_deleted" in room_data and room_data['room_deleted'] is True and room.pk is None:
            await self.send_group(group, "roomdelete.dispatch", {"room_id": str(room.id)})
            for m in room_data["members"]:
                await self.discard_channel_from_group(group, m.id)
            return None
        await self.send_group(group, "roomupdate.dispatch", room_data)

        















    
    
    
    
    
    # --------------------------------------------- #

    # Utils for adding and discarding channels to groups.

    # --------------------------------------------- #

    async def add_channel_to_group(self, group, user_id=None):
        if user_id is None or user_id == self.user.id:
            user_id = self.user.id
 
        active_sessions = await EventHandler.get_active_sessions(user_id)
        
        for channel_name in active_sessions:
            await self.channel_layer.group_add(group, channel_name)

        # store all user groups so it can be added it to their channel layer on every new connection
        await add_group_to_user_groups(user_id, group)

    async def discard_channel_from_group(self, group, user_id=None):
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
        response = {"type": "broadcast_group", "eventType": event_type, "data": data}
        # print("send_group:", group)
        await self.channel_layer.group_send(group, response)

    async def broadcast_group(self, data):
        # print(self.channel_name)
        # data.pop('type')
        # print('broadcast', data)
        await self.send(text_data=json.dumps(data))


    # --------------------------------------------- #

    # Helpers for setting up and cleaning up data.

    # for now doesn't support concurrent connections from the same user.
    # --------------------------------------------- #

    async def channel_cleanup(self):
        user_id = self.user.id
        groups = await fetch_user_groups(user_id)
        expired_sessions = await EventHandler.get_expired_sessions(user_id)
        for group in groups:
            for channel_name in expired_sessions:
                await self.channel_layer.group_discard(group, channel_name)

    async def channel_setup(self):
        user_id = self.user.id
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
    
