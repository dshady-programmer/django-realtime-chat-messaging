
from channels.db import database_sync_to_async
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model 
import json
from .utils.cache_utils import (
    fetch_user_groups,
    get_previous_channel_name,
    clear_previous_channel_name,
    update_user_groups,
    set_channel_name,
    get_persistent_channel_name,
    add_group_to_user_groups
)
from .utils.handlers import  (
    get_and_group_chat_notifications,
    create_message, 
    message_acknowledged,
    create_read_receipt,
    create_room
)
from .utils.decorators import (
    event_handler
)
from .permissions.decorators import (can_access_message, can_send_message_to_room)
User = get_user_model()

# 4001: Authentication failed.
# 4002: Permission failed.


# Events
USER_OWN_GROUP = "user-{user_id}"
GROUP_STRING = "group-{group_id}"


"""
Events on the frontend

user_profile
undelivered_messages
retrieve_peer_conversation
delivered_messages
follow_event
unfollow_event
group_create
group_join
group_leave
incoming_message
message_delivered
message_seen
message_typing

"""

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
Media (2 events): 
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
readreceipt.dispatch
roomcreate.dispatch

"""
class ChatMessagingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
  
        if user.id is None:
            await self.close(code=4001)  # custom close code
            return

      
        self.user = user
        await self.channel_cleanup(user.id)
        await self.channel_setup(user.id)

        await self.accept()
        # dispatch all notifications.
        await self.dispatch_chat_notifications()

    async def disconnect(self, close_code):
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
            # "message.typing": _,
            "room.create": self.receive_room_create_event,
            # "room.list": _,
            # "room.info": _,
            # "room.message": _,
            # "room.join": _,
            # "room.leave": _,
            # "room.modify": _, # add or remove members/subscribers (for the user with permission), add or remove admins/moderators (for the user),  change name/description/preferences,
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
    async def receive_message_send_event(self, data):
        """
        receive_message_send_event

        data: {
            room_id: string/int,
            content: text, 
            extra_fields: {
                ... 
            }
        }
        note: extra field value must contain model fields validated by the provided serializer
        """
        
        room_id = data["room_id"]
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

    async def discard_channel_from_group(self, group):
        await self.channel_layer.group_discard(group, self.channel_name)
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
