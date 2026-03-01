
"""
Permission decorators for WebSocket consumer event handlers.

These decorators enforce authorization checks before executing consumer methods.
They use the configurable PERMISSION_HANDLER_CLASS to check permissions and
inject resolved room instances into the handler methods.

The permission handler is swappable via settings, allowing custom authorization
logic without modifying decorator code.
"""




from functools import wraps
from django.core.exceptions import PermissionDenied
from realtime_chat_messaging.conf import realtime_chat_settings 
from realtime_chat_messaging.utils.loader import import_and_verify_type_class
permissions = realtime_chat_settings.PERMISSION_HANDLER_CLASS

PERMISSION_HANDLER_CLASS = import_and_verify_type_class(permissions, "PERMISSION_HANDLER_CLASS")
PERMISSION_HANDLER = PERMISSION_HANDLER_CLASS()



def can_modify_message(method):
    """
        Verify user is the message sender before allowing modification.

        Checks that the user sending the event is the original sender of the
        message(s) being modified. Injects the room instance for group dispatch.

        Args:
            method: Consumer method handling message.modify event.

        Returns:
            Wrapped method that receives room parameter.

        Raises:
            PermissionDenied: If user is not the message sender.

        Example:
            @can_modify_message
            async def receive_message_modify_event(self, data, room):
                # room is injected by decorator
                ...
    """    
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        message_id = data.get('message_id')
        is_permitted, room = await PERMISSION_HANDLER.is_message_sender(self.user, message_id)
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to modify this message")
    return wrapper


def can_access_message(method):
    """
        Verify user has access to message(s) before allowing operations.

        Checks that the user is a member of the room containing the message(s).
        Used for read, react, and acknowledge operations.

        Args:
            method: Consumer method handling message operations.

        Raises:
            PermissionDenied: If user is not a room member.

        Example:
            @can_access_message
            async def receive_message_read_event(self, data):
                ...
    """    
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):
        message_id = data.get('message_id')
        
        is_permitted = await PERMISSION_HANDLER.have_message_permission(self.user, message_id)
        if is_permitted:
            return await method(self, data, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to access this message")
        
    return wrapper

def can_send_message_to_room(method):
    """
        Verify user can send messages to the room.

        For GroupChat: Checks room membership (and group_locked status).
        For Channel: Checks can_send_messages permission or moderator status.
        For OneToOneChat: Checks room membership.

        Injects the room instance for message creation.

        Args:
            method: Consumer method handling message.send event.

        Returns:
            Wrapped method that receives room parameter.

        Raises:
            PermissionDenied: If user cannot send messages to the room.

        Example:
            @can_send_message_to_room
            async def receive_message_send_event(self, data, room):
                # room is injected by decorator
                ...
    """

    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        is_permitted, room = await PERMISSION_HANDLER.have_send_message_permission(self.user, data)
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to send message to this room")
    return wrapper


def can_access_room(method):
    """
        Verify user is a member of the room.

        Checks room membership for participants (GroupChat/OneToOneChat) or
        subscribers (Channel). Injects the room instance.

        Args:
            method: Consumer method handling room operations.

        Returns:
            Wrapped method that receives room parameter.

        Raises:
            PermissionDenied: If user is not a room member.

        Example:
            @can_access_room
            async def receive_get_room_info(self, data, room):
                # room is injected by decorator
                ...
    """    
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        room_id = data.get('room_id')
        is_permitted, room = await PERMISSION_HANDLER.have_room_permission(self.user, room_id)
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized access this room")
        
    return wrapper


def can_add_members_to_room(method):
    """
        Verify user has permission to add members to the room.

        For GroupChat: Checks can_add_new_participants permission.
        For Channel: Checks can_add_new_subscribers permission.

        Injects the room instance.

        Args:
            method: Consumer method handling room.add_members event.

        Returns:
            Wrapped method that receives room parameter.

        Raises:
            PermissionDenied: If user lacks add member permission.

        Example:
            @can_add_members_to_room
            async def receive_add_members_to_room(self, data, room):
                # room is injected by decorator
                ...
    """

    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        room_id = data.get('room_id')
        is_permitted, room = await PERMISSION_HANDLER.have_room_permissions_to_add_or_remove_members(self.user, room_id, "add_new") 
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to add new members to this room")
    return wrapper



def can_remove_members_from_room(method):
    """
        Verify user has permission to remove members from the room.

        For GroupChat: Checks can_remove_participants permission.
        For Channel: Checks can_remove_subscribers permission.

        Injects the room instance.

        Args:
            method: Consumer method handling room.remove_members event.

        Returns:
            Wrapped method that receives room parameter.

        Raises:
            PermissionDenied: If user lacks remove member permission.

        Example:
            @can_remove_members_from_room
            async def receive_remove_members_from_room(self, data, room):
                # room is injected by decorator
                ...
    """    
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        room_id = data.get('room_id')
        is_permitted, room = await PERMISSION_HANDLER.have_room_permissions_to_add_or_remove_members(self.user, room_id, "remove") 
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to remove members from this room")
    return wrapper



def is_room_admin(method):
    """
        Verify user has admin/moderator privileges for room modification.

        For delete action: Requires user to be the room creator.
        For other actions: Requires admin (GroupChat) or moderator (Channel) status.

        Injects the room instance.

        Args:
            method: Consumer method handling room.modify event.

        Returns:
            Wrapped method that receives room parameter.

        Raises:
            PermissionDenied: If user is not creator (for delete) or not admin/
                moderator (for other actions).

        Example:
            @is_room_admin
            async def receive_modify_room_event(self, data, room):
                # room is injected by decorator
                ...
    """    
    
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        room_id = data.get('room_id')
        action = data.get('action')

        is_permitted, room = await PERMISSION_HANDLER.have_admin_privileges(self.user, room_id, action)
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            if action == "delete":
                msg = "User is not the creator of this room"

            else:
                msg = "User is not an admin of this room"

            raise PermissionDenied(msg)
    return wrapper


