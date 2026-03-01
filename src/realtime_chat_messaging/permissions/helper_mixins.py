"""
Synchronous permission checking logic for chat authorization.

This module implements the core authorization rules for rooms, messages, and
admin privileges. All methods are synchronous and wrapped by PermissionHandler
with sqlite_safe_db_sync_to_async for use in async contexts.

The permission logic supports:
- Room membership checks (participants/subscribers)
- Message access and ownership verification
- Admin/moderator privilege validation
- Customizable admin field names for extended models

Override methods in this mixin to customize authorization behavior without
modifying the async wrapper layer.
"""

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from realtime_chat_messaging.utils.loader import get_model


Room = get_model("Room")
Message = get_model("Message")
GroupChat = get_model("GroupChat")
Channel = get_model("Channel")

class PermissionHelperMixin:
    """
        Synchronous helper methods for permission checks.

        All methods return (is_permitted: bool, room: Room | None) tuples except
        _have_message_permission which returns bool only.

        Design Pattern:
            Each method validates input, fetches required objects, checks
            authorization rules, and returns results for decorator consumption.
    """

    @staticmethod
    def _have_room_permission(user, room_id):
        """
            Check if user is a member of the room.

            Args:
                user: The user to check.
                room_id: Room ID (str or int).

            Returns:
                tuple: (is_member: bool, room: Room)

            Raises:
                ValidationError: If room_id type is invalid.
                Http404: If room does not exist.
        """        
        if type(room_id) not in [str, int]:
            raise ValidationError("Invalid room_id type")

        room = get_object_or_404(Room, pk=room_id)
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
        """
            Check if user has access to message(s).

            Verifies user is a member of the room(s) containing the message(s).
            Excludes soft-deleted messages from checks.

            Args:
                user: The user to check.
                message_id: Single ID (str/int) or list of IDs.

            Returns:
                bool: True if user has access to all messages.

            Raises:
                ValidationError: If message_id type is invalid.
                Http404: If any message does not exist or is deleted.

            Note:
                Returns False immediately if user lacks access to any message
                in the list.
        """           
        if type(message_id) not in [list, str, int]:
            raise ValidationError("Invalid message_id type")
        
        is_permitted = True

        def is_member(message):
            """Check if user is a member of the message's room."""
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
        """
            Check if user is the sender of message(s).

            Validates that:
            1. User is the sender of all specified messages
            2. All messages are from the same room (for multi-message operations)

            Args:
                user: The user to check.
                message_id: Single ID (str/int) or list of IDs.

            Returns:
                tuple: (is_sender: bool, room: Room)

            Raises:
                ValidationError: If message_id type invalid, empty list provided,
                    or messages are from different rooms.
                Http404: If any message does not exist or is deleted.

            Note:
                The same-room requirement ensures consistent message.modify
                operations (e.g., bulk delete within one conversation).
        """
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
            message = get_object_or_404(Message.objects.filter(is_deleted=False), pk=id)
            message_rooms.add(message.room)
            is_permitted = message.sender == user
            if not is_permitted:
                break
        if len(message_rooms) > 1:
            raise ValidationError("All messages marked for modification must come from the same room")
        return is_permitted, message_rooms.pop()
    
    @staticmethod
    def _have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase, default_admin_names={"group": "admins", "channel": "moderators"}):
        
        """
            Check if user can add or remove members from the room.

            Permission hierarchy (any grants access):
            1. Room creator (always permitted)
            2. Admin/moderator status
            3. Object-level permission (can_add_new_*/can_remove_*)

            Args:
                user: The user to check.
                room_id: Room ID (str or int).
                perm_phrase: 'add_new' or 'remove'.
                default_admin_names: Dict mapping 'group'/'channel' to admin
                    field names (default: {'group': 'admins', 'channel': 'moderators'}).

            Returns:
                tuple: (has_permission: bool, room: Room)

            Raises:
                ValidationError: If room_id invalid or room is OneToOneChat.
                Http404: If room does not exist.

            Note:
                Override default_admin_names when using custom admin field names
                in extended GroupChat/Channel models.
        """        
        if type(room_id) not in [str, int]:
            raise ValidationError("Invalid room_id type")
        is_permitted = False
        room = get_object_or_404(Room, pk = room_id)
        if isinstance(room, GroupChat):
            room = get_object_or_404(GroupChat.objects.prefetch_related('participants', default_admin_names["group"]), pk=room.pk)
        
            is_permitted = user in room.participants.all() and (user.has_perm(f"can_{perm_phrase}_participants", room) or room.creator == user or user in getattr(room, default_admin_names["group"]).all())
        elif isinstance(room, Channel):
            room = get_object_or_404(Channel.objects.prefetch_related('subscribers', default_admin_names["channel"]), pk=room.pk)
            is_permitted = user in room.subscribers.all() and (user.has_perm(f"can_{perm_phrase}_subscribers", room) or room.creator == user or user in getattr(room, default_admin_names["channel"]).all())
        else:
            raise ValidationError("Invalid room, Can only add or remove members from Groups/Channels")
        return is_permitted, room


    @staticmethod
    def _have_send_message_permission(user, data, default_admin_names={"group": "admins", "channel": "moderators"}):
        """
            Check if user can send messages to the room.

            Permission rules by room type:
            - Channel: User must be a subscriber AND (creator OR moderator OR
            have can_send_messages permission)
            - GroupChat (locked): User must be participant AND (creator OR admin)
            - GroupChat (unlocked): User must be participant
            - OneToOneChat: User must be participant

            Even as a creator of groups/channels you must be a member to be able to send
            messages.
            
            Args:
                user: The user to check.
                data: Event data containing 'room_id' OR 'message_id' (for replies).
                default_admin_names: Dict mapping 'group'/'channel' to admin
                    field names.

            Returns:
                tuple: (can_send: bool, room: Room)

            Raises:
                ValidationError: If room_id/message_id type invalid or missing.
                Http404: If room or message does not exist.

            Note:
                Supports both direct room targeting (room_id) and reply-based
                targeting (message_id). Cross-room replies are allowed to support
                use cases like private replies to group messages. (This functionality would be improved later)
        """

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

        # Commented this out because developer might end up wanting cross room replies e.g in the case of whatsapp you can reply to group messages privately
        # check if parent_message_id is present if present check if the parent_message_id room is same as room
        # if "extra_fields" in data and "parent_message_id" in data["extra_fields"] and (parent_message_id := data["extra_fields"]["parent_message_id"]):
        #     p_message = get_object_or_404(Message, pk=parent_message_id)
        #     if p_message.room != room :
        #         raise ValidationError("You can only reply to message in the same room")



        
        # first check if the room is a channel..
            # only creators and moderators and people with permissions can post on channels
        
        # if group
            # check if group is locked i.e only admins and the creator can send messages
            # else any participants of the group can send messages to the group
        
        if isinstance(room, Channel):
            is_permitted = room.subscribers.filter(pk=user.pk).exists() and (room.creator == user or getattr(room, default_admin_names["channel"]).filter(pk=user.pk).exists() or user.has_perm('can_send_messages', room))
        elif isinstance(room, GroupChat):
            if room.group_locked:
                is_permitted = room.participants.filter(pk=user.pk).exists() and (room.creator == user or getattr(room, default_admin_names["group"]).filter(pk=user.pk).exists())
            else:
                is_permitted = room.participants.filter(pk=user.pk).exists()
        else:
            is_permitted = room.participants.filter(pk=user.pk).exists()

        return is_permitted, room

    @staticmethod
    def _have_admin_privileges(user, room_id, action, default_admin_names={"group": "admins", "channel": "moderators"}):
        """
            Check if user has admin/moderator privileges for room modification.

            Permission rules:
            - delete action: User must be creator (GroupChat/Channel) or
            participant (OneToOneChat)
            - other actions: User must be creator OR admin/moderator, 
            
            AND
            be a member of the room (if this condition is False it invalidates the above condition)

            Args:
                user: The user to check.
                room_id: Room ID.
                action: The modification action (e.g., 'delete', 'update',
                    'add_admin').
                default_admin_names: Dict mapping 'group'/'channel' to admin
                    field names.

            Returns:
                tuple: (has_privileges: bool, room: Room)

            Raises:
                Http404: If room does not exist.

            Note:
                Delete action has stricter requirements (creator-only for
                GroupChat/Channel) to prevent accidental room deletion by admins.
        """        
        is_permitted = True
        room = get_object_or_404(Room, pk = room_id)
        if action == "delete":
            if isinstance(room, (GroupChat, Channel)):
                is_permitted = room.creator == user
            else:
                is_permitted = user in room.participants.all()
        else:
            if isinstance(room, GroupChat):
                room = GroupChat.objects.prefetch_related('participants', default_admin_names["group"]).get(pk=room.pk)
                is_permitted = user in room.participants.all() and (room.creator == user or user in getattr(room, default_admin_names["group"]).all())
            elif isinstance(room, Channel):
                room = Channel.objects.prefetch_related('subscribers', default_admin_names["channel"]).get(pk=room.pk)
                is_permitted = user in room.subscribers.all() and (room.creator == user or user in getattr(room, default_admin_names["channel"]).all())
            else:
                is_permitted = user in room.participants.all()

        return is_permitted, room