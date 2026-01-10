from functools import wraps
from django.core.exceptions import PermissionDenied
from realtime_chat_messaging.conf import realtime_chat_settings 
from realtime_chat_messaging.utils.loader import import_and_verify_type_class
permissions = realtime_chat_settings.PERMISSION_HANDLER_CLASS

PERMISSION_HANDLER_CLASS = import_and_verify_type_class(permissions, "PERMISSION_HANDLER_CLASS")
PERMISSION_HANDLER = PERMISSION_HANDLER_CLASS()



def can_modify_message(method):
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
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):
        message_id = data.get('message_id')
        
        is_permitted = await PERMISSION_HANDLER.have_message_permission(self.user, message_id)
        if is_permitted:
            return await method(*args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to access this message")
        
    return wrapper

def can_send_message_to_room(method):
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):

        is_permitted, room = await PERMISSION_HANDLER.have_send_message_permission(self.user, data)
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not authorized to send message to this room")
    return wrapper


def can_access_room(method):
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
    @wraps(method)
    async def wrapper(self, data, *args, **kwargs):



        room_id = data.get('room_id')
        is_permitted, room = await PERMISSION_HANDLER.have_admin_privileges(self.user, room_id)
        if is_permitted:
            return await method(self, data, room=room, *args, **kwargs)
        else:
            raise PermissionDenied("User is not an admin of this room")
    return wrapper


