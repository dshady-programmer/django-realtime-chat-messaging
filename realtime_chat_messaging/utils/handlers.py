from channels.db import database_sync_to_async
from django.shortcuts import get_object_or_404
from realtime_chat_messaging.models import (
    Message, ReadReceipt, 
    ChatNotification, Room, 
    GroupChat, User, 
    Channel, OneToOneChat, Reaction
)
from realtime_chat_messaging.serializers import (
    ChatNotificationSerializer, MessageSerializer, 
    RoomPolymorphicSerializer, RoomListPolymorphicSerializer, 
    ReactionSerializer, MessageMediaAssetSerializer
)
from collections import defaultdict
from .chat_notifications import update_chat_notification, create_chat_notification
from django.db.models import Prefetch, Q
from django.core.paginator import Paginator
from guardian.shortcuts import remove_perm, assign_perm

@database_sync_to_async
def get_and_group_chat_notifications(user):


    chat_notifications = ChatNotification.objects.filter(recipients=user).prefetch_related(
        Prefetch(
            "message__room",
            queryset=Room.objects.all() # using Prefetch is redundant here (prefetch_related() alone works)..
        )

        # using prefetch_related() because it fetches room objects separately and maps it to their respectively subclasses (onetoone, group, channel)
        # using select_related() just returns the direct room object (Room <room_id>) which affects serialization...
    ).distinct().order_by("-message__room__created_at")
    
    serialized_chat_notifications = ChatNotificationSerializer(chat_notifications, many=True).data

    grouped_chat_notifications = defaultdict(list)
    for chat_notification in serialized_chat_notifications:
        
        room_id = chat_notification["message"]["room"]["id"]
        grouped_chat_notifications[room_id].append(chat_notification)


    return grouped_chat_notifications


@database_sync_to_async
def create_message(data, user):
    from django.db import connection
    # Ensures that a database connection is available and open for the current thread (async context). 
    # Needed serializer primarykeyrelatedfield.
    connection.ensure_connection() 
    message_type = 'NEW_MESSAGE'
    media = None
    extra_fields = data.get('extra_fields', {})
    if extra_fields.get('media'):
        media = extra_fields.pop('media')
    new_data = {
        "room_id": data["room_id"],
        "sender_id": user.id,
        "content": data["content"],
        **extra_fields
    }
    if "parent_message" in data:
        new_data["parent_message_id"] = data.get("parent_message")
        message_type = 'REPLY'
    if "is_forwarded" in new_data and "forwarded_from_id" in new_data:
        if not new_data['is_forwarded']:
            new_data.pop('forward_from_id')
            new_data.pop('is_forwarded')
    elif "is_forwarded" not in new_data and "forwarded_from_id" in new_data:
        new_data.pop('forwarded_from_id')
    
    elif "is_forwarded" in new_data and "forwarded_from_id" not in new_data:
        new_data.pop('is_forwarded')

    

    serializer = MessageSerializer(data=new_data)
    serializer.is_valid(raise_exception=True)
    message = serializer.save()
    message.room.last_message = message
    message.room.save()
    if media:
        media_asset = MessageMediaAssetSerializer(data = media)
        media_asset.is_valid(raise_exception=True)
        media_asset.save()
    create_chat_notification(message, message_type, user)
    message_serializer = MessageSerializer(message)
    return message_serializer.data


@database_sync_to_async
def react_to_message(data, user):
    type = data.pop('type')
    response = None
    if type == 'remove':
        message_id = data.pop('message_id')
        reaction = Reaction.objects.filter(message__id=message_id, user=self.user)
        status = None
        if reaction.exists():
            reaction.delete()
            status = "successful"
        else:
            status = "failed"
        message = get_object_or_404(Message, pk=message_id)
        serialized_message = MessageSerializer(message).data
        response = {
            "status": status,
            "message": serialized_message,
            "action": type
        }

    elif type == 'add':
        data["user_id"] = user.id
        message_id = data.pop("message_id")
        data["message"] = message_id
        serializer = ReactionSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        create_chat_notification(instance.message, "REACTION", user)
        message_serializer = MessageSerializer(instance.message)
        response = {"status": "successful", "type": type, "message": message_serializer.data}
    else:
        raise Exception('invalid reaction type')
    return response 

@database_sync_to_async
def message_acknowledged(user, message_id):
    many = False
    if isinstance(message_id, list):
        message_id = list(set(message_id))
        many = True

    update_chat_notification(message_id, user, many)

@database_sync_to_async
def modify_message(user, data):
    action = data.get('action')
    message_ids = data.get('message_id')
    if action == "delete":
        if not isinstance(message_ids, list):
            message_ids = [message_ids]
        Message.objects.filter(pk__in=message_ids).delete()
        return {"status": "successful", "action": "delete", "message_ids": message_ids}
    elif action == "update":
        message_id = None
        if isinstance(message_ids, list):
            if len(message_ids) > 1:
                raise Exception("You can only update one message at a time")
            message_id = message_ids[0]
        else:
            message_id = message_ids
        message = get_object_or_404(Message, pk=message_id)
        content = data.get('extra_fields').get('content')
        if content:
            serializer = MessageSerializer(instance=message, data={"content": content}, partial=True)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            serialized_message = MessageSerializer(instance)
            return {"status": "successful", "action": "update", "message": serialized_message.data}
        else:
            raise Exception("Content should be provided for update action")

    else:
        raise Exception("Invalid action type")
    

@database_sync_to_async
def create_read_receipt(user, message_id):
    if isinstance(message_id, list):
        messages = Message.objects.filter(id__in=message_id).exclude(sender=user).distinct()
        room_ids = set()
        receipts = []
        for message in messages:
            room_ids.add(str(message.room.id))
            receipts.append(ReadReceipt(message=message, reader=user))
        ReadReceipt.objects.bulk_create(receipts)
        serializer = MessageSerializer(messages, many=True)
        rooms = defaultdict(list)

        for m in serializer.data:
            room_id = m["room"]["id"]
            rooms[room_id].append(m)
        return room_ids, rooms

    else:
        message = get_object_or_404(Message, id=message_id)
        if message.sender != user:
            room_id = message.room.id

            ReadReceipt.objects.create(message=message, reader=user)
            serializer = MessageSerializer(message)

            return room_id, serializer.data
        return None, {}


@database_sync_to_async
def create_room(user, data):
    serializer = RoomPolymorphicSerializer(data=data, context={"user": user})
    serializer.is_valid(raise_exception=True)
    instance = serializer.save()
    room_serializer = RoomPolymorphicSerializer(instance)
    return room_serializer.data



@database_sync_to_async
def list_rooms(user):
    rooms = Room.objects.filter(Q(onetoonechat__participants=user) | Q(channel__subscribers=user) | Q(groupchat__participants=user)).select_related('last_message').order_by('-last_message__created_at')
    if rooms.exists():
        serializer = RoomListPolymorphicSerializer(rooms, many=True, context={"user": user})
        return serializer.data

    else:
        return []
    
@database_sync_to_async
def retreive_room(room):
    serializer = RoomPolymorphicSerializer(room)
    return serializer.data

@database_sync_to_async
def add_members_to_room(user_ids, room):
    from django.db import connection
    connection.ensure_connection() 
    existing_room_members = None
    members = None
    user_ids = list(set(user_ids))
    if isinstance(room, GroupChat):
        members = room.participants
        existing_room_members = set(members.all())
    else:
        members = room.subscribers
        existing_room_members = set(members.all())

    new_member_usernames = []
    newly_added_users = []
    for id in user_ids:
        user = get_object_or_404(User, id=id)
        if user not in existing_room_members:
            newly_added_users.append(user)
            new_member_usernames.append(user.username)
    members.add(*newly_added_users)
    serialized_room = RoomPolymorphicSerializer(room).data
    return newly_added_users, serialized_room, new_member_usernames
        
@database_sync_to_async
def remove_members_from_room(user_ids, room, session_user):
    from django.db import connection
    connection.ensure_connection() 
    existing_room_members = None
    members = None
    user_ids = list(set(user_ids))
    if isinstance(room, GroupChat):
        members = room.participants
        existing_room_members = set(members.all())
    else:
        members = room.subscribers
        existing_room_members = set(members.all())

    removed_members_username = []
    newly_removed_users = []
    for id in user_ids:
        user = get_object_or_404(User, id=id)
        if room.creator == user and room.creator != session_user:
            # an admin cannot remove the creator of the group
            # only a group creator can remove themself.
            # you can configure it to raise an error in settings
            continue
        if user in existing_room_members:
            newly_removed_users.append(user)
            removed_members_username.append(user.username)
    members.remove(*newly_removed_users)
    serialized_room = RoomPolymorphicSerializer(room).data
    return newly_removed_users, serialized_room, removed_members_username


@database_sync_to_async
def leave_room(user, room):
    
    if isinstance(room, GroupChat):
        members = room.participants
    elif isinstance(room, Channel):
        members = room.subscribers
    else:
        raise Exception("You can only leave a channel/group chat")

    members.remove(user)

    serialized_room = RoomPolymorphicSerializer(room).data
    return serialized_room



@database_sync_to_async
def join_room(user, room_id):
    room = get_object_or_404(Room, pk=room_id)

    if isinstance(room, GroupChat):
        # User should implement a custom functionality for this or leave the exception
        raise Exception("Ask an admin to add you to the group")
    elif isinstance(room, Channel):
        if room.is_public:
            room.subscribers.add(user)
        else:
            raise Exception("Channel is private, ask a moderator to add you to the channel")
    else:
        raise Exception("You can only join a channel/group chat")
    
    serialized_room = RoomPolymorphicSerializer(room).data
    return serialized_room

@database_sync_to_async
def retreive_messages(room, data):
    messages = Message.objects.filter(room=room).prefetch_related('read_receipts', 'reactions', 'attachments').order_by('-created_at')
    paginate = data.get('paginate')
    response = {}
    if paginate:
        page = paginate.get('page')
        size = paginate.get('size')
        if not page or not size:
            raise Exception('page and size required')
        try:
            page = int(page)
            size = int(size)
        except:
            raise Exception("Invalid types")
        
        paginator = Paginator(messages, size)
        get_page = paginator.get_page(page)
        
        has_next = get_page.has_next()
        has_previous = get_page.has_previous()
        next_page_number = get_page.next_page_number() if has_next else None
        prev_page_number = get_page.previous_page_number() if has_previous else None 

        response.update({
            "has_next": has_next, 
            "has_previous": has_previous, 
            "next_page_number": next_page_number, 
            "prev_page_number": prev_page_number,
            "page": page,
            "size": size    
        })
        messages = get_page.object_list

    serialized_messages = MessageSerializer(messages, many=True)

    response["data"] = {
        "room_id": str(room.id),
        "messages": serialized_messages.data
    }

    return response
    
        

@database_sync_to_async
def modify_room(user, data, room):
    action = data.get('action')
    field_data = data.get('data')

    if not action:
        raise Exception("Action must be provided")
    if not field_data:
        raise Exception("data must be provided")
    if action == "update":
        if type(room) in [GroupChat, Channel]:
            if "name" in field_data:
                room.name = field_data.get("name")
            if "description" in field_data:
                room.description = field_data.get("description")
        if "preference" in field_data:
            room.preference = field_data.get("preference")
        room.save()
    if not isinstance(room, OneToOneChat) and action in [
        "add_permission", "remove_permission",
        "add_moderator", "add_admin", 
        "remove_moderator", "remove_admin"
    ]:
        member_ids = field_data.get('users')

        if not member_ids:
            raise Exception("User ids must be provided")
        if not isinstance(member_ids, list):
            raise Exception("User ids must be a list/array")
        member_ids = list(set(member_ids))
        
        if room.creator.id in member_ids:
            member_ids.remove(room.creator.id)
        members = User.objects.filter(pk__in=member_ids)
        if action in ["add_permission", "remove_permission"]:
            VALID_GROUP_CHAT_PERMS = ["can_add_new_participants", "can_remove_participants"]
            VALID_CHANNEL_PERMS = ["can_add_new_subscribers", "can_remove_subscribers", "can_send_messages"]
            permissions = field_data.get('permission')
            if not permissions:
                raise Exception("Permission to add or remove should be passed")
            if not isinstance(permissions, list):
                raise Exception("Permission must be a list")
            permissions = list(set(permissions))
            
            if isinstance(room, GroupChat):
                for perm in permissions:
                    if perm not in VALID_GROUP_CHAT_PERMS:
                        raise Exception(f"Permission '{perm}' is not a valid group chat permission")
            else:
                for perm in permissions:
                    if perm not in VALID_CHANNEL_PERMS:
                        raise Exception(f"Permission '{perm}' is not a valid channel permission")
            for member in members:
                for perm in permissions:
                    if action == "add_permission":
                        assign_perm(perm, member, room)
                    else:
                        remove_perm(perm, member, room)
        elif action in ["add_admin", "remove_admin"]:
            if not isinstance(room, GroupChat):
                raise Exception("Room should be a group chat to modify the admin")
            if action == "add_admin":
                room.admins.add(*members)
            else:
                room.admins.remove(*members)
        else:
            if not isinstance(room, Channel):
                raise Exception("Room should be a channel to modify the admin")
            if action == "add_moderator":
                room.moderators.add(*members)
            else:
                room.moderators.remove(*members)
    return RoomPolymorphicSerializer(room).data

            
            
        

            
        
    

            

