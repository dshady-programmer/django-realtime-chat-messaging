from django.shortcuts import get_object_or_404
from realtime_chat_messaging.models import Message,Room, GroupChat, Channel
from channels.db import database_sync_to_async

@database_sync_to_async
def have_room_permission(user, room_id):
    from django.db import connection
    connection.ensure_connection() 

    room = get_object_or_404(Room, id=room_id)
    is_permitted = False
    if (hasattr(room, "participants")):
        if room.participants.filter(pk=user.pk).exists():
            is_permitted = True
    elif (hasattr(room, "subscribers")):
        if room.subscribers.filter(pk=user.pk).exists():
            is_permitted = True
        
    return is_permitted, room


@database_sync_to_async
def have_message_permission(user, message_id):
    from django.db import connection
    connection.ensure_connection() 
    is_permitted = True

    def is_member(message):
        is_mem = False
        if (hasattr(message.room, "participants")):
            if message.room.participants.filter(pk=user.pk).exists():
                is_mem = True
        elif (hasattr(message.room, "subscribers")):
            if message.room.subscribers.filter(pk=user.pk).exists():
                is_mem = True
        return is_mem
    
    
    if isinstance(message_id, list):
        for id in message_id:
            message = get_object_or_404(Message, pk=id)
            is_permitted = is_member(message)
            if not is_permitted:
                break
    else:
        message = get_object_or_404(Message, pk=message_id)
        is_permitted = is_member(message)
    
    return is_permitted


@database_sync_to_async
def have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase):
    from django.db import connection
    connection.ensure_connection() 
    is_permitted = False
    room = get_object_or_404(Room, pk = room_id)
    if isinstance(room, GroupChat):
        room = GroupChat.objects.prefetch_related('participants', 'admins').get(pk=room.pk)
        is_permitted = user in room.participants.all() and (user.has_perm(f"can_{perm_phrase}_participants", room) or room.creator == user or user in room.admins.all())
    elif isinstance(room, Channel):
        room = Channel.objects.prefetch_related('subscribers', 'moderators').get(pk=room.pk)
        is_permitted = user in room.subscribers.all() and (user.has_perm(f"can_{perm_phrase}_subscribers", room) or room.creator == user or user in room.moderators.all())
    else:
        raise Exception("Invalid room, Can only add or remove members from Groups/Channels")
    return is_permitted, room


@database_sync_to_async
def have_send_message_permission(user, data):
    from django.db import connection
    connection.ensure_connection()
    is_permitted = False 
    room_id = data.get('room_id')
    message_id = data.get('message_id')
    message = None

    # if room_id is provided check if the current user can send message to the room

    if room_id:
        room = get_object_or_404(Room, pk=room_id)
    else:
        message = get_object_or_404(Message, pk=message_id)
        room = message.room
    
    # first check if to see if the room is a channel..
        # only creators and moderators and people with permissions can post on channels
    
    # if group
        # check if group is locked i.e only admins and the creator can send messages
        # else any participants of the group can send messages to the group
    
    if isinstance(room, Channel):
        is_permitted = room.subscribers.filter(pk=user.pk).exists() and (room.creator == user or room.moderators.filter(pk=user.pk).exists() or user.has_perm('can_send_messages', room))
    elif isinstance(room, GroupChat):
        if room.group_locked:
            is_permitted = room.participants.filter(pk=user.pk).exists() and (room.creator == user or room.admins.filter(pk=user.pk).exists())
        else:
            is_permitted = room.participants.filter(pk=user.pk).exists()
    else:
        is_permitted = room.participants.filter(pk=user.pk).exists()

    return is_permitted, room
