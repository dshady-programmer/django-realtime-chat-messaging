from django.shortcuts import get_object_or_404
from operator import itemgetter
from django.core.exceptions import ValidationError
from collections import defaultdict
from django.db.models import Prefetch, Q
from django.core.paginator import Paginator
from guardian.shortcuts import remove_perm, assign_perm
from realtime_chat_messaging.utils.loader import import_and_verify_type_class, import_and_verify_type_function
from realtime_chat_messaging.conf import realtime_chat_settings 
from django.contrib.auth import get_user_model

User = get_user_model()
serializers = realtime_chat_settings.SERIALIZERS
models = realtime_chat_settings.MODELS 
soft_delete = realtime_chat_settings.MESSAGE_SOFT_DELETE
enable_notification = realtime_chat_settings.ENABLE_NOTIFICATION

(

    _RoomListPolymorphicSerializer,
    _RoomPolymorphicSerializer,
    _ReactionSerializer,
    _MessageMediaAssetSerializer,
    _MessageSerializer,
    _ChatNotificationSerializer
) = itemgetter(

        "RoomListPolymorphicSerializer",
        "RoomPolymorphicSerializer",
        "ReactionSerializer",
        "MessageMediaAssetSerializer",
        "MessageSerializer",
        "ChatNotificationSerializer"
    )(serializers)

(        
    _Room,
    _OneToOneChat,
    _GroupChat,
    _Channel,
    _Message,
    _ReadReceipt,
    _ChatNotification,
    _Reaction,
) = itemgetter(
        "Room",
        "OneToOneChat",
        "GroupChat",
        "Channel",
        "Message",
        "ReadReceipt",
        "ChatNotification",
        "Reaction",
    )(models)

class MessageHelperMixins:
    """
    Message handler helper mixins
    Functionality can be extended
    """
 
    def _create_message(self, data, user):
        MessageSerializer = import_and_verify_type_class(
            _MessageSerializer,
            "MessageSerializer",
        )
        MessageMediaAssetSerializer = import_and_verify_type_class(
            _MessageMediaAssetSerializer,
            "MessageMediaAssetSerializer"
        )

        create_chat_notification = self.create_chat_notification

        message_type = 'NEW_MESSAGE'
        media = None
        extra_fields = data.get('extra_fields', {})
 
        media = extra_fields.pop('media', None)
        if media is not None and not isinstance(media, list):
            raise ValidationError("Media must be a list of media files")
        
        new_data = {
            "room_id": data["room_id"],
            "sender_id": user.id,
            "content": "Media Files" if media else data["content"],
            **extra_fields
        }
        if "parent_message_id" in data:
            message_type = 'REPLY'

        if "forwarded_from_id" in new_data:
            new_data['is_forwarded'] = True        

        serializer = MessageSerializer(data=new_data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        if hasattr(message.room, 'last_message'):
            message.room.last_message = message
            message.room.save()

        if media:
            for file in media:
                file.update({"message_id": message.id})   
            media_asset = MessageMediaAssetSerializer(data = media, many=True)
            media_asset.is_valid(raise_exception=True)
            media = media_asset.save()
        
        if enable_notification:
            create_chat_notification(message, message_type, user)
        message_serializer = MessageSerializer(message)
        return message_serializer.data
    

    def _react_to_message(self, data, user):
        Reaction = import_and_verify_type_class(_Reaction, "Reaction")
        Message = import_and_verify_type_class(_Message, "Message")
        MessageSerializer = import_and_verify_type_class(_MessageSerializer, "MessageSerializer")
        ReactionSerializer = import_and_verify_type_class(_ReactionSerializer, "ReactionSerializer")
        create_chat_notification = create_chat_notification = self.create_chat_notification

        type = data.pop('type') if 'type' in data else None
        response = None
        if type == 'remove':
            message_id = data.pop('message_id')
            reaction = Reaction.objects.filter(message__id=message_id, user=user)
            status = None
            if reaction.exists():
                reaction.delete()
                status = "successful"
            else:
                status = "failed"
            try:
                message = get_object_or_404(Message.objects.prefetch_related('delivered_to'), pk=message_id)
            except AttributeError:
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
            if enable_notification:
                create_chat_notification(instance.message, "REACTION", user)
            message_serializer = MessageSerializer(instance.message)
            response = {"status": "successful", "type": type, "message": message_serializer.data}
        else:
            raise ValidationError('invalid reaction type')
        return response 


    
    def _message_acknowledged(self, user, message_id):
        update_chat_notification = self.update_chat_notification
        many = False
        if isinstance(message_id, list):
            message_id = list(set(message_id))
            many = True

        if enable_notification:
            update_chat_notification(message_id, user, many)


    @staticmethod
    def _modify_message(data):

        Message = import_and_verify_type_class(_Message, "Message")
        MessageSerializer = import_and_verify_type_class(_MessageSerializer, "MessageSerializer")

        action = data.get('action')
        message_ids = data.get('message_id')
        if action == "delete":
            if not isinstance(message_ids, list):
                message_ids = [message_ids]
            if soft_delete:
                Message.objects.filter(pk__in=message_ids).update(is_deleted=True)
            else:
                Message.objects.filter(pk__in=message_ids).delete() 
            return {"status": "successful", "action": "delete", "message_ids": message_ids}
        elif action == "update":
            message_id = None
            if isinstance(message_ids, list):
                if len(message_ids) > 1:
                    raise ValidationError("You can only update one message at a time")
                message_id = message_ids[0]
            else:
                message_id = message_ids
            message = get_object_or_404(Message.objects.prefetch_related('delivered_to'), pk=message_id)
            content = data.get('extra_fields').get('content')
            if content:
                serializer = MessageSerializer(instance=message, data={"content": content, "is_edited": True}, partial=True)
                serializer.is_valid(raise_exception=True)
                instance = serializer.save()
                serialized_message = MessageSerializer(instance)
                return {"status": "successful", "action": "update", "message": serialized_message.data}
            else:
                raise ValidationError("Content should be provided for update action")

        else:
            raise ValidationError("Invalid action type")
    

    @staticmethod
    def _create_read_receipt(user, message_id):

        Message = import_and_verify_type_class(_Message, "Message")
        ReadReceipt = import_and_verify_type_class(_ReadReceipt, "ReadReceipt")
        MessageSerializer = import_and_verify_type_class(_MessageSerializer, "MessageSerializer")

        if isinstance(message_id, list):
            try:
                messages = Message.objects.filter(id__in=message_id).exclude(sender=user).prefetch_related('delivered_to').distinct()
            except AttributeError:
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
            try:
                message = get_object_or_404(Message.objects.prefetch_related('delivered_to'), id=message_id)
            except AttributeError:
                message = get_object_or_404(Message, id=message_id)
            if message.sender != user:
                room_id = message.room.id

                ReadReceipt.objects.create(message=message, reader=user)
                serializer = MessageSerializer(message)

                return room_id, serializer.data
            return None, {}

    @staticmethod 
    def _retreive_messages(room, data):

        Message = import_and_verify_type_class(_Message, "Message")
        MessageSerializer = import_and_verify_type_class(_MessageSerializer, "MessageSerializer")


        try:
            messages = Message.objects.filter(room=room).prefetch_related('read_receipts', 'reactions', 'attachments', 'delivered_to').order_by('-created_at')
        except AttributeError:
            messages = Message.objects.filter(room=room).prefetch_related('read_receipts', 'reactions', 'attachments').order_by('-created_at')
        paginate = data.get('paginate')
        response = {}
        if paginate and isinstance(paginate, dict):
            page = paginate.get('page')
            size = paginate.get('size')
            if not page or not size:
                raise ValidationError('page and size required')
            try:
                page = int(page)
                size = int(size)
            except:
                raise ValidationError("Invalid types")
            
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




class RoomHelperMixins:
    """
    Room handler helper mixins
    Functionality can be extended
    """
    @staticmethod
    def _create_room(user, data):
    
        RoomPolymorphicSerializer = import_and_verify_type_class(
            _RoomPolymorphicSerializer,
            "RoomPolymorphicSerializer"
        )

        serializer = RoomPolymorphicSerializer(data=data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        room_serializer = RoomPolymorphicSerializer(instance)
        return room_serializer.data


    @staticmethod
    def _list_rooms(user):
        Room = import_and_verify_type_class(_Room, "Room")

        RoomListPolymorphicSerializer = import_and_verify_type_class(_RoomListPolymorphicSerializer, "RoomListPolymorphicSerializer")
        rooms = Room.objects.filter(Q(onetoonechat__participants=user) | Q(channel__subscribers=user) | Q(groupchat__participants=user)).select_related('last_message').order_by('-last_message__created_at')
        if rooms.exists():
            serializer = RoomListPolymorphicSerializer(rooms, many=True, context={"user": user})
            return serializer.data

        else:
            return []

    @staticmethod
    def _retreive_room(room):
        RoomPolymorphicSerializer = import_and_verify_type_class(_RoomPolymorphicSerializer, "RoomPolymorphicSerializer")

        serializer = RoomPolymorphicSerializer(room)
        return serializer.data

    
    @staticmethod
    def _add_members_to_room(user_ids, room):
        GroupChat = import_and_verify_type_class(_GroupChat, "GroupChat")
        RoomPolymorphicSerializer = import_and_verify_type_class(_RoomPolymorphicSerializer, "RoomPolymorphicSerializer")
        members = room.participants if isinstance(room, GroupChat) else room.subscribers
        user_ids = list(set(user_ids))
        existing_room_members = set(members.all())

        new_member_usernames = []
        newly_added_users = []
        for id in user_ids:
            user = get_object_or_404(User, pk=id)
            if user not in existing_room_members:
                newly_added_users.append(user)
                new_member_usernames.append(user.username)
        members.add(*newly_added_users)
        serialized_room = RoomPolymorphicSerializer(room).data
        return newly_added_users, serialized_room, new_member_usernames
    
    @staticmethod
    def _remove_members_from_room(user_ids, room, session_user):

        GroupChat = import_and_verify_type_class(_GroupChat, "GroupChat")
        RoomPolymorphicSerializer = import_and_verify_type_class(_RoomPolymorphicSerializer, "RoomPolymorphicSerializer")
        members = room.participants if isinstance(room, GroupChat) else room.subscribers
        user_ids = list(set(user_ids))
        existing_room_members = set(members.all())

        removed_members_username = []
        newly_removed_users = []
        for id in user_ids:
            user = get_object_or_404(User, pk=id)
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
    
    @staticmethod
    def _leave_room(user, room):
        GroupChat = import_and_verify_type_class(_GroupChat, "GroupChat")
        Channel = import_and_verify_type_class(_Channel, "Channel")
        RoomPolymorphicSerializer = import_and_verify_type_class(_RoomPolymorphicSerializer, "RoomPolymorphicSerializer")
        if not isinstance(room, (GroupChat, Channel)):
            raise ValidationError("You can only leave a channel/group chat")
        members = room.participants if isinstance(room, GroupChat) else room.subscribers
        members.remove(user)

        serialized_room = RoomPolymorphicSerializer(room).data
        return serialized_room
    

    @staticmethod
    def _join_room(user, room_id):

        # if you have a different functionality for joining GroupChat or Channels override this method to replace with your custom functionality


        GroupChat = import_and_verify_type_class(_GroupChat, "GroupChat")
        Channel = import_and_verify_type_class(_Channel, "Channel")
        Room = import_and_verify_type_class(_Room, "Room")
        RoomPolymorphicSerializer = import_and_verify_type_class(_RoomPolymorphicSerializer, "RoomPolymorphicSerializer")

        room = get_object_or_404(Room, pk=room_id)

        if isinstance(room, GroupChat):
            # User should implement a custom functionality for this or leave the exception
            raise ValidationError("Ask an admin to add you to the group")
        elif isinstance(room, Channel):
            if room.is_public:
                room.subscribers.add(user)
            else:
                raise ValidationError("Channel is private, ask a moderator to add you to the channel")
        else:
            raise ValidationError("You can only join a channel/group chat")
        
        serialized_room = RoomPolymorphicSerializer(room).data
        return serialized_room

    def _modify_room(user, data, room):

        VALID_ACTIONS = [
            "update", "add_permission", "remove_permission",
            "add_moderator", "add_admin", 
            "remove_moderator", "remove_admin"
        ]
        GroupChat = import_and_verify_type_class(_GroupChat, "GroupChat")
        Channel = import_and_verify_type_class(_Channel, "Channel")
        OneToOneChat = import_and_verify_type_class(_OneToOneChat, "OneToOneChat")
        RoomPolymorphicSerializer = import_and_verify_type_class(_RoomPolymorphicSerializer, "RoomPolymorphicSerializer")

        action = data.get('action')
        field_data = data.get('data')

        if not action:
            raise ValidationError("Action must be provided")

        if action not in VALID_ACTIONS:
            raise ValidationError("Invalid action type")
        if not field_data:
            raise ValidationError("data must be provided")
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
                raise ValidationError("User ids must be provided")
            if not isinstance(member_ids, list):
                raise ValidationError("User ids must be a list/array")
            member_ids = list(set(member_ids)) # remove duplicates
            
            if room.creator.id in member_ids:
                member_ids.remove(room.creator.id) # prevent removal of room creator permissions
            members = User.objects.filter(pk__in=member_ids)
            if action in ["add_permission", "remove_permission"]:
                VALID_GROUP_CHAT_PERMS = ["can_add_new_participants", "can_remove_participants"]
                VALID_CHANNEL_PERMS = ["can_add_new_subscribers", "can_remove_subscribers", "can_send_messages"]
                permissions = field_data.get('permission')
                if not permissions:
                    raise ValidationError("Permission to add or remove should be passed")
                if not isinstance(permissions, list):
                    raise ValidationError("Permission must be a list")
                permissions = list(set(permissions))
                
                if isinstance(room, GroupChat):
                    for perm in permissions:
                        if perm not in VALID_GROUP_CHAT_PERMS:
                            raise ValidationError(f"Permission '{perm}' is not a valid group chat permission")
                else:
                    for perm in permissions:
                        if perm not in VALID_CHANNEL_PERMS:
                            raise ValidationError(f"Permission '{perm}' is not a valid channel permission")
                for member in members:
                    for perm in permissions:
                        if action == "add_permission":
                            assign_perm(perm, member, room)
                        else:
                            remove_perm(perm, member, room)
            elif action in ["add_admin", "remove_admin"]:
                if not isinstance(room, GroupChat):
                    raise ValidationError("Room should be a group chat to modify the admins")
                if action == "add_admin":
                    room.admins.add(*members)
                else:
                    room.admins.remove(*members)
            else:
                if not isinstance(room, Channel):
                    raise ValidationError("Room should be a channel to modify the moderators")
                if action == "add_moderator":
                    room.moderators.add(*members)
                else:
                    room.moderators.remove(*members)
        return RoomPolymorphicSerializer(room).data

            
            
class ChatNotificationHelperMixins:
    """
    Notification handler helper mixins
    Functionality can be extended
    """
    @staticmethod
    def _get_and_group_chat_notifications(user):
    
        ChatNotification = import_and_verify_type_class(_ChatNotification, "ChatNotification")
        Room = import_and_verify_type_class(_Room, "Room")

        ChatNotificationSerializer = import_and_verify_type_class(
            _ChatNotificationSerializer,
            "ChatNotificationSerializer"
        )


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

