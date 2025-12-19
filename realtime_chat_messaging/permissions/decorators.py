from functools import wraps
from channels.db import database_sync_to_async
from realtime_chat_messaging.models import Message,Room


def can_access_message(method):
    @wraps(method)
    async def wrapper(*args, **kwargs):
        self = args.get('self')
        data = args.get('data')

        message_id = data.get('message_id')
        message = database_sync_to_async(Message.objects.get)(id=message_id)
        is_permitted = False
        if (hasattr(message.room, "participants")):
            if self.user in list(message.room.participants.all()):
                is_permitted = True
        elif (hasattr(message.room, "subscribers")):
            if self.user in list(message.room.subscribers.all()):
                is_permitted = True

        if is_permitted:
            return await method(*args, **kwargs)
        else:
            raise Exception("User is not authorized to access this message")
        
    return wrapper


def can_send_message_to_room(method):
    @wraps(method)
    async def wrapper(*args, **kwargs):
        self = args.get('self')
        data = args.get('data')

        room_id = data.get('room_id')
        room = database_sync_to_async(Room.objects.get)(id=room_id)
        is_permitted = False
        if (hasattr(room, "participants")):
            if self.user in list(room.participants.all()):
                is_permitted = True
        elif (hasattr(room, "subscribers")):
            if self.user in list(room.subscribers.all()):
                is_permitted = True

        if is_permitted:
            return await method(*args, **kwargs)
        else:
            raise Exception("User is not authorized to send message in this room")
        
    return wrapper
