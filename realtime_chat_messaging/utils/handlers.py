from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from realtime_chat_messaging.models import Message, ReadReceipt
from realtime_chat_messaging.serializers import ChatNotificationSerializer, MessageSerializer, RoomPolymorphicSerializer
from collections import defaultdict
from .chat_notifications import update_chat_notification, create_chat_notification



@database_sync_to_async
def get_and_group_chat_notifications(user):
    chat_notifications = ChatNotification.objects.filter(recipients=user).select_related("message__room").distinct().order_by("-message__room__created_at")
    
    serialized_chat_notifications = ChatNotificationSerializer(chat_notifications, many=True).data

    grouped_chat_notifications = defaultdict(list)

    for chat_notification in serialized_chat_notifications:
        room_id = chat_notification["message"]["room_id"]
        grouped_chat_notifications[room_id].append(chat_notification)



    return grouped_chat_notifications


@database_sync_to_async
def create_message(data, user):

    new_data = {
        "room_id": data["room_id"],
        "sender_id": user,
        "content": data["content"],
        **data["extra_fields"]
    }
    serializer = MessageSerializer(data=new_data)
    serializer.is_valid(raise_exception=True)
    message = serializer.save()
    create_chat_notification(message, "NEW_MESSAGE")
    return message


@database_sync_to_async
def message_acknowledged(user, message_id):
    many = False
    if isinstance(message_id, list):
        many = True
    
    update_chat_notification(message_id, user, many)
    

@database_sync_to_async
def create_read_receipt(user, message_id):
    if isinstance(message_id, list):
        messages = Message.objects.filter(id__in=message_id)
        room_ids = set()
        receipts = []
        for message in messages:
            room_ids.append(message.room.id)
            receipts.append(ReadReceipt(message=message, reader=user))
        ReadReceipt.objects.bulk_create(receipts)
        serializer = MessageSerializer(messages, many=True)
        rooms = defaultdict(list)

        for m in serializer.data:
            room_id = m["room_id"]
            rooms[room_id].append(m)
        return room_ids, rooms

    else:
        message = get_object_or_404(Message, id=message_id)

        room_id = message.room.id

        ReadReceipt.objects.create(message=message, reader=user)
        serializer = MessageSerializer(message)

        return room_id, serializer.data


@database_sync_to_async
def create_room(user, data):
    serializer = RoomPolymorphicSerializer(data=data, context={"user": user})
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()

    room_serializer = RoomPolymorphicSerializer(instance)
    return room_serializer.data

