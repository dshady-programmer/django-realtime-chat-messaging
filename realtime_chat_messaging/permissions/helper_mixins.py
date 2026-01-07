from django.shortcuts import get_object_or_404
from realtime_chat_messaging.models import Message, Room, GroupChat, Channel
from django.core.exceptions import ValidationError



class PermissionHelperMixin:
    @staticmethod
    def _have_room_permission(user, room_id):
        if type(room_id) not in [str, int]:
            raise ValidationError("Invalid room_id type")

        room = get_object_or_404(Room, id=room_id)
        is_permitted = False
        if (hasattr(room, "participants")):
            if room.participants.filter(pk=user.pk).exists():
                is_permitted = True
        elif (hasattr(room, "subscribers")):
            if room.subscribers.filter(pk=user.pk).exists():
                is_permitted = True
            
        return is_permitted, room

    @staticmethod
    def _have_message_permission(user, message_id):
            
        if type(message_id) not in [list, str, int]:
            raise ValidationError("Invalid message_id type")
        
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
        
        
        if not isinstance(message_id, list):
            message_id = [message_id]
        else:
            message_id = list(set(message_id))

        for id in message_id:
            message = get_object_or_404(Message.objects.filter(is_deleted=False), pk=id)
            is_permitted = is_member(message)
            if not is_permitted:
                break
        
        return is_permitted
    
    @staticmethod
    def _is_message_sender(user, message_id):

        if type(message_id) not in [list, str, int]:
            raise ValidationError("Invalid message_id type")
        is_permitted = True



        if not isinstance(message_id, list):
            message_id = [message_id]
        else:
            message_id = list(set(message_id))
        # all message ids to be deleted should come from the same room
        # This mimics highlighting multiple messages for deletion
        if len(message_id) < 1:
            raise ValidationError("Atleast one message_id is required for modification")
        message_rooms = set()
        for id in message_id:
            message = get_object_or_404(Message, pk=id)
            message_rooms.add(message.room)
            is_permitted = message.sender == user
            if not is_permitted:
                break
        if len(message_rooms) > 1:
            raise ValidationError("All messages marked for modification must come from the same room")
        return is_permitted, message_rooms.pop()
    
    @staticmethod
    def _have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase):
        if type(room_id) not in [str, int]:
            raise ValidationError("Invalid room_id type")
        is_permitted = False
        room = get_object_or_404(Room, pk = room_id)
        if isinstance(room, GroupChat):
            room = GroupChat.objects.prefetch_related('participants', 'admins').get(pk=room.pk)
            is_permitted = user in room.participants.all() and (user.has_perm(f"can_{perm_phrase}_participants", room) or room.creator == user or user in room.admins.all())
        elif isinstance(room, Channel):
            room = Channel.objects.prefetch_related('subscribers', 'moderators').get(pk=room.pk)
            is_permitted = user in room.subscribers.all() and (user.has_perm(f"can_{perm_phrase}_subscribers", room) or room.creator == user or user in room.moderators.all())
        else:
            raise ValidationError("Invalid room, Can only add or remove members from Groups/Channels")
        return is_permitted, room


    @staticmethod
    def _have_send_message_permission(user, data):
        is_permitted = False 
        room_id = data.get('room_id')
        message_id = data.get('message_id')
        message = None
    
        # if room_id is provided check if the current user can send message to the room

        if room_id:
            if type(room_id) not in [str, int]:
                raise ValidationError("Invalid room_id type")
            room = get_object_or_404(Room, pk=room_id)
        else:
            if type(message_id) not in [str, int]:
                raise ValidationError("Invalid message_id type")
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

    @staticmethod
    def _have_admin_privileges(user, room_id):
        is_permitted = True
        room = get_object_or_404(Room, pk = room_id)
        if isinstance(room, GroupChat):
            room = GroupChat.objects.prefetch_related('participants', 'admins').get(pk=room.pk)
            is_permitted = user in room.participants.all() and (room.creator == user or user in room.admins.all())
        elif isinstance(room, Channel):
            room = Channel.objects.prefetch_related('subscribers', 'moderators').get(pk=room.pk)
            is_permitted = user in room.subscribers.all() and (room.creator == user or user in room.moderators.all())

        return is_permitted, room