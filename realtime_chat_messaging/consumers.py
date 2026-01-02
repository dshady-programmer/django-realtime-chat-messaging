
from channels.db import database_sync_to_async
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from guardian.utils import get_anonymous_user
from django.contrib.auth import get_user_model 
import json
from .utils.cache_utils import (
    fetch_user_groups,
    get_previous_channel_name,
    clear_previous_channel_name,
    update_user_groups,
    set_channel_name,
    get_persistent_channel_name,
    add_group_to_user_groups,
    remove_group_from_user_groups
)
from .utils.handlers import  (
    get_and_group_chat_notifications,
    create_message, 
    message_acknowledged,
    create_read_receipt,
    create_room,
    list_rooms,
    retreive_room,
    add_members_to_room,
    react_to_message,
    remove_members_from_room,
    leave_room, 
    join_room, 
    retreive_messages,
    modify_message,
    modify_room
)
from .utils.decorators import (
    event_handler
)
from .permissions.decorators import (
    can_access_message, can_access_room,
    can_add_members_to_room, can_remove_members_from_room,
    can_send_message_to_room, can_modify_message,
    is_room_admin
    

)
User = get_user_model()

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
Connection: 
    connect, 
    disconnect
Room Management (8 events): 
    create_room, 
    join_room, 
    leave_room, 
    fetch_rooms, 
    fetch_room_details, 
    add_participant, 
    remove_participant, 
    update_room
Messages (6 events): 
    send_message, 
    edit_message, 
    delete_message, 
    fetch_messages, 
    forward_message, 
    reply_to_message 
    upload_media, 
    fetch_media
Reactions (3 events): 
    add_reaction, 
    remove_reaction, 
    fetch_reactions
Read Receipts (2 events): 
    mark_as_read, 
    fetch_read_receipts
Notifications (2 events): 
    fetch_notifications, 
    mark_notification_read
Presence (2 events): 
    typing_indicator, 
    update_presence

pending:
  modify_room
    update room,
    update room preferences,
    update room member permissions
    

"""
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
# user_last_seen (heartbeat ping) 

"""


"""
frontend events:

chat.notifications
message.dispatch
messagetyping.dispatch
messagemodification.dispatch
reaction.dispatch
readreceipt.dispatch
roomcreate.dispatch
roomlist.dispatch
roommessages.dispatch
roominfo.dispatch
roomaddmembers.dispatch
roomremovemembers.dispatch
roomexit.dispatch
roomupdate.dispatch


"""
class ChatMessagingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        
        if user.id is None or user == database_sync_to_async(get_anonymous_user)():
            await self.close(code=4001)  # custom close code
            return
        
        self.user = user
        await self.channel_cleanup(user.id)
        await self.channel_setup(user.id)

        await self.accept()
        # dispatch all notifications.
        await self.dispatch_chat_notifications()

    async def disconnect(self, close_code):
        if hasattr(self, "user"):
            user_id = self.user.id
            if user_id:
                await self.channel_cleanup(user_id)


    async def receive(self, text_data = None, bytes_data = None):
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
        map_event_type_to_handlers = {
            "message.send": self.receive_message_send_event,
            "message.acknowledged": self.receive_message_acknowledged_event,
            "message.read": self.receive_message_read_event,
            "message.react": self.receive_message_reaction_event, 
            "message.typing": self.receive_message_typing_event,
            "message.modify": self.receive_message_modify_event,
            "room.create": self.receive_room_create_event,
            "room.list": self.receive_get_rooms,
            "room.info": self.receive_get_room_info,
            "room.add_members": self.receive_add_members_to_room,
            "room.remove_members": self.receive_remove_members_from_room,
            "room.messages": self.receive_message_list,
            "room.join": self.receive_join_room_event,
            "room.leave": self.receive_leave_room_event,
            "room.modify": self.receive_modify_room_event, # add or remove admins/moderators (for the user),  change name/description/preferences,
            # "online_presence": _


        }
        try:
            await map_event_type_to_handlers[event_type](data.get("data"))
        except KeyError:
            error_msg = {"error": "invalid event type"}
            await self.send(text_data=json.dumps(error_msg))

    @event_handler
    async def dispatch_chat_notifications(self):
        chat_notifications = await get_and_group_chat_notifications(self.user)
        await self.send_group(
            USER_OWN_GROUP.format(user_id=self.user.id),
            "chat.notifications",
            chat_notifications,
        )

    @event_handler
    @can_send_message_to_room
    async def receive_message_send_event(self, data, room):
        """
        receive_message_send_event

        data: {
            parent_message: <only for reply messages>
            room_id: string/int,
            content: text, 
            extra_fields: {
                ... 
                is_forwarded: Boolean,
                forwarded_from_id: <only if is_forwarded is true>

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
        message = await create_message(data, self.user)
        group_string = GROUP_STRING.format(group_id=room_id)
        # print(group_string)
        await self.send_group(group_string, "message.dispatch", message)
            

    @event_handler
    @can_access_message
    async def receive_message_acknowledged_event(self, data):
        """
        receive_message_acknowledged_event
        
        data: {
            message_id: string/int or List<string/int>,
        }
        """

        await message_acknowledged(self.user, data["message_id"])

        await self.send(text_data=json.dumps({"status": "successful"}))

    @event_handler
    @can_access_message
    async def receive_message_read_event(self, data):
        """
        receive_message_read_event
        
        data: {
            message_id: string/int or List<string/int>        
        }

        broadcasts the message/messages with the updated read_receipts
        """

        room_id, message = await create_read_receipt(self.user, data["message_id"])
        
        if room_id:
            if isinstance(room_id, set):
                for id in room_id:
                    group = GROUP_STRING.format(group_id=id)
                    await self.send_group(group, "readreceipt.dispatch", message[id])
            else:
                group = GROUP_STRING.format(group_id=room_id)
                await self.send_group(group, "readreceipt.dispatch", message)

    @event_handler
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
        
        response = await react_to_message(data, self.user)
        room_id = response['message']['room']['id']
        group_string = GROUP_STRING.format(group_id=room_id)
        # print(group_string)
        await self.send_group(group_string, "reaction.dispatch", response)





    @event_handler
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


    @event_handler
    @can_modify_message
    @can_access_message
    async def receive_message_modify_event(self, data, room):
        """
        receive_message_modify_event
        
        data: {
            action: "update" / "delete"
            message_id: string/int (update) / [string/int, string/int] (for delete)
            extra_fields: [
                content: text (for update action, provide fields to modify)
            ]
        }
        """

        response = await modify_message(self.user, data)
        if response:
            group_string = GROUP_STRING.format(group_id=room.id)
            await self.send_group(group_string, "messagemodification.dispatch", response)



    @event_handler
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
        
        response = await retreive_messages(room, data)
    

        user_group = USER_OWN_GROUP.format(user_id=self.user.id)
        await self.send_group(user_group, "roommessages.dispatch", response)
        





    @event_handler
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


        room = await create_room(self.user, data)

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

        

    @event_handler
    async def receive_get_rooms(self, _):
        """
        receive_get_rooms
        
        data: empty
        """
        rooms = await list_rooms(self.user)

        await self.send_group(
            USER_OWN_GROUP.format(user_id=self.user.id),
            "roomlist.dispatch", 
            rooms
        )


    @event_handler
    @can_access_room
    async def receive_get_room_info(self, data, room):
        """
        receive_get_room_info
        
        data : {
        room_id
        }
        """
        room = await retreive_room(room)

        
        await self.send_group(
            USER_OWN_GROUP.format(user_id=self.user.id),
            "roominfo.dispatch", 
            room
        )


    @event_handler
    @can_add_members_to_room
    async def receive_add_members_to_room(self, data, room):
        """
        receive_add_members_to_room
        
        data: {
        room_id: "",
        members: [userIds]
        }
        """

        users_added, serialized_room, new_member_usernames = await add_members_to_room(data.get('members'), room)
        group = GROUP_STRING.format(group_id=room.id)
        for user in users_added:
         
            await self.add_channel_to_group(group, user.id)
        await self.send_group(group, "roomaddmembers.dispatch", {"room": serialized_room, "new_members": new_member_usernames})

    @event_handler
    @can_remove_members_from_room
    async def receive_remove_members_from_room(self, data, room):
        """
        receive_remove_members_from_room
        data: {
        room_id: "",
        members: [userIds]
        }
        """

        users_removed, serialized_room, removed_member_usernames = await remove_members_from_room(data.get('members'), room, self.user)
        group = GROUP_STRING.format(group_id=room.id) 
        for user in users_removed:
            await self.discard_channel_from_group(group, user.id)
            user_group = USER_OWN_GROUP.format(user_id=user.id)
            await self.send_group(user_group, "roomexit.dispatch", {"room": serialized_room, "message": f"You have been removed by {self.user.username}"})
        await self.send_group(group, "roomremovemembers.dispatch", {"room": serialized_room, "removed_members": removed_member_usernames, "removed_by": self.user.username})



    @event_handler
    @can_access_room
    async def receive_leave_room_event(self, data, room):
        """
        receive_leave_room_event
        
        data: {
            room_id: string
        }
        """

        serialized_room = await leave_room(self.user, room)

        group = GROUP_STRING.format(group_id=room.id)
        user_group = USER_OWN_GROUP.format(user_id=self.user.id)
        await self.discard_channel_from_group(group) # remove user channel from group

        await self.send_group(user_group, "roomexit.dispatch", {"room": serialized_room, "message": f"You left {room.name}"})

        await self.send_group(group, "roomremovemembers.dispatch", {"room": serialized_room, "removed_members": [self.user.username], "removed_by": "self"})

    
    @event_handler
    async def receive_join_room_event(self, data):
        """
        receive_join_room_event
        
        data: {
            room_id: string
        }
        """

        serialized_room = await join_room(self.user, data.get('room_id'))

        group = GROUP_STRING.format(group_id=serialized_room["id"])
        await self.add_channel_to_group(group)
        await self.send_group(group, "roomaddmembers.dispatch", {"room": serialized_room, "new_members": [self.user.username]})



    @event_handler
    @is_room_admin
    async def receive_modify_room_event(self, data, room):
        """
        receive_modify_room_event
        
        data: {
            room_id: ""
            action: "update" / "add_permission" /  "remove_permission" / "add_moderator" / "add_admin" / "remove_moderator" / "remove_admin"
            data: {
                ...
            }
        }
        """
        room_data = await modify_room(self.user, data, room)
        group = GROUP_STRING.format(group_id=room.id)
        await self.send_group(group, "roomupdate.dispatch", room_data)

        















    
    
    
    
    
    # --------------------------------------------- #

    # Utils for adding and discarding channels to groups.

    # --------------------------------------------- #

    async def add_channel_to_group(self, group, user_id=None):
        if user_id is None or user_id == self.user.id:
            user_id = self.user.id
            # Adds the current user to the group
            await self.channel_layer.group_add(group, self.channel_name)
        else:
            # adds a user to the specified group
            channel_name = await get_persistent_channel_name(user_id)
            if channel_name:
                await self.channel_layer.group_add(group, channel_name)

        # store all user groups so that can add it to their channel layer on every new connection
        await add_group_to_user_groups(user_id, group)

    async def discard_channel_from_group(self, group, user_id=None):
        if user_id is None or user_id == self.user.id:
            user_id = self.user.id
            await self.channel_layer.group_discard(group, self.channel_name)
        else:
            channel_name = await get_persistent_channel_name(user_id)
            if channel_name:
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

    async def channel_cleanup(self, user_id: str):
        groups = await fetch_user_groups(user_id)
        prev_channel_name = await get_previous_channel_name(user_id)
        if not (prev_channel_name):
            # already cleaned up
            return None
        for group in groups:
            await self.channel_layer.group_discard(group, prev_channel_name)
        await clear_previous_channel_name(user_id)

    async def channel_setup(self, user_id: str):
        groups = await fetch_user_groups(user_id)
        user_own_group = USER_OWN_GROUP.format(user_id=user_id)
        if user_own_group not in groups:
            # add user group to already existing user group.
            groups.append(user_own_group)

            # cache this
            await update_user_groups(user_id, groups)
        for group in groups:
            await self.channel_layer.group_add(group, self.channel_name)
        await set_channel_name(user_id, self.channel_name)
