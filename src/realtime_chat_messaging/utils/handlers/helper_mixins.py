"""
Helper mixins containing synchronous business logic for chat operations.

These mixins implement the actual database operations and business rules for
messages, rooms, notifications, and sessions. They are wrapped by handler
mixins with sqlite_safe_db_sync_to_async for use in async contexts.

All helpers are designed to be extensible - subclass and override specific
methods to customize behavior without rewriting the entire implementation.

Architecture:
    Consumer (async) → Handler Mixin (async wrapper) → Helper Mixin (sync logic) → Database
"""

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from collections import defaultdict
from django.db.models import Prefetch, Q
from django.core.paginator import Paginator
from guardian.shortcuts import remove_perm, assign_perm
from realtime_chat_messaging.utils.loader import get_serializer, get_model
from realtime_chat_messaging.conf import realtime_chat_settings 
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
import datetime
from django.utils import timezone

User = get_user_model()






class MessageHelperMixins:
    """
        Synchronous business logic for message operations.

        Handles:
        - Message creation (standard, replies, forwards) with media attachments
        - Reactions (add/remove)
        - Message acknowledgment and delivery tracking
        - Message modification (update content, soft/hard delete)
        - Read receipts (single and bulk)
        - Paginated message retrieval

        All methods are synchronous and wrapped by MessageHandlerMixin for async use.
    """

    def __init_subclass__(cls, **kwargs):
        """Load models and serializers when helper is subclassed."""
        super().__init_subclass__(**kwargs)
        MessageHelperMixins._load_variables()

    @classmethod
    def _load_variables(cls):
        """Load required models, serializers, and settings."""
        # models
        cls.Message = get_model("Message")
        cls.ReadReceipt = get_model("ReadReceipt")
        cls.Reaction = get_model("Reaction")
        cls.MessageMediaAsset = get_model("MessageMediaAsset")
        cls.ChatNotification = get_model("ChatNotification")
        # serializers
        cls.MessageSerializer = get_serializer("MessageSerializer")
        cls.ReactionSerializer = get_serializer("ReactionSerializer")
        cls.MessageMediaAssetSerializer = get_serializer("MessageMediaAssetSerializer")
        
        # other variables
        cls.EnableNotification = realtime_chat_settings.ENABLE_NOTIFICATION
        cls.SoftDelete = realtime_chat_settings.MESSAGE_SOFT_DELETE


    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        cls._load_variables()

    
    def _create_message(self, data, user):
        """
            Create a new message with optional media attachments.

            Handles standard messages, replies (parent_message_id), and forwards
            (forwarded_from_id). Media files are validated and created as separate
            MessageMediaAsset instances. Updates room's last_message and creates
            notification if enabled.

            Args:
                data (dict): Message data including room_id, content, and optional
                    extra_fields with media, parent_message_id, forwarded_from_id.
                user: The message sender.

            Returns:
                dict: Serialized message with all relations.

            Raises:
                ValidationError: If media is not a list or validation fails.
        """
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
        if "parent_message_id" in new_data:
            message_type = 'REPLY'

        if "forwarded_from_id" in new_data:
            new_data['is_forwarded'] = True        
        serializer = MessageHelperMixins.MessageSerializer(data=new_data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        if hasattr(message.room, 'last_message'):
            message.room.last_message = message
            message.room.save()

        if media:
            for file in media:
                file.update({"message_id": message.id})   
            media_asset = MessageHelperMixins.MessageMediaAssetSerializer(data = media, many=True)
            media_asset.is_valid(raise_exception=True)
            media = media_asset.save()
        
        if MessageHelperMixins.EnableNotification:
            create_chat_notification(message, message_type, user)
        message_serializer = MessageHelperMixins.MessageSerializer(message)

        return message_serializer.data
    

    def _react_to_message(self, data, user):
        """
            Add or remove a reaction to a message.

            Args:
                data (dict): Must include 'type' ('add' or 'remove'), 'message_id',
                    and 'reaction_content' (for add).
                user: The user reacting.

            Returns:
                dict: Status, action type, and updated message with reactions.

            Raises:
                ValidationError: If type is invalid.

            Note:
                Signals handle replacing old reactions when user reacts again.
        """            
        create_chat_notification = self.create_chat_notification

        type = data.pop('type') if 'type' in data else None
        response = None
        if type == 'remove':
            message_id = data.pop('message_id')
            reaction = MessageHelperMixins.Reaction.objects.filter(message__id=message_id, user=user)
            status = None
            if reaction.exists():
                reaction.delete()
                status = "successful"
            else:
                status = "failed"
            if hasattr(MessageHelperMixins.Message, 'delivered_to'):
                message = get_object_or_404(MessageHelperMixins.Message.objects.prefetch_related('delivered_to'), pk=message_id)
            else:
                message = get_object_or_404(MessageHelperMixins.Message, pk=message_id)
            serialized_message = MessageHelperMixins.MessageSerializer(message).data
            response = {
                "status": status,
                "message": serialized_message,
                "action": type
            }

        elif type == 'add':
            data["user_id"] = user.id
            message_id = data.pop("message_id")
            data["message"] = message_id
 
            serializer = MessageHelperMixins.ReactionSerializer(data=data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            if MessageHelperMixins.EnableNotification:
                create_chat_notification(instance.message, "REACTION", user)
            message_serializer = MessageHelperMixins.MessageSerializer(instance.message)
            response = {"status": "successful", "type": type, "message": message_serializer.data}
        else:
            raise ValidationError('invalid reaction type')
        return response 


    
    def _message_acknowledged(self, user, message_id):
        """
            Mark messages as delivered and update notifications.

            Calls update_chat_notification to remove user from notification
            recipients and add to delivered_to field.

            Args:
                user: User acknowledging delivery.
                message_id: Single ID or list of IDs.

            Returns:
                dict: Messages grouped by sender ID for targeted dispatch.
        """        
        update_chat_notification = self.update_chat_notification
        many = False
        if isinstance(message_id, list):
            message_id = list(set(message_id))
            many = True

        message_senders = defaultdict(list)
        messages = update_chat_notification(message_id, user, many)
        
        serialized_messages = MessageHelperMixins.MessageSerializer(messages, many=True).data

        for serialized_message in serialized_messages:
            message_senders[serialized_message['sender']['id']].append(serialized_message)
        
        return message_senders
        


    @staticmethod
    def _modify_message(data):
        """
            Update or delete message(s).

            For delete: Soft deletes (sets is_deleted=True) or hard deletes based
            on MESSAGE_SOFT_DELETE setting. Accepts single ID or list.

            For update: Only updates content field and sets is_edited=True. Prevents
            modification of immutable fields via serializer.update() method. Single
            message only.

            Args:
                data (dict): Action ('update' or 'delete'), message_id (ID or list),
                    and extra_fields (for update) with content.

            Returns:
                dict: Status, action, and updated message or deleted message IDs.

            Raises:
                ValidationError: If action invalid, multiple updates attempted, or
                    extra_fields missing for update.
        """
        action = data.get('action')
        message_ids = data.get('message_id')
        if action == "delete":
            if not isinstance(message_ids, list):
                message_ids = [message_ids]
            if MessageHelperMixins.SoftDelete:
                MessageHelperMixins.Message.objects.filter(pk__in=message_ids).update(is_deleted=True)
            else:
                MessageHelperMixins.Message.objects.filter(pk__in=message_ids).delete()
            # if message is associated with any notification clear it.
            MessageHelperMixins.ChatNotification.objects.filter(message__pk__in=message_ids).delete()
            return {"status": "successful", "action": "delete", "message_ids": message_ids}
        
        elif action == "update":
            message_id = None
            if isinstance(message_ids, list):
                if len(message_ids) > 1:
                    raise ValidationError("You can only update one message at a time")
                message_id = message_ids[0]
            else:
                message_id = message_ids
            if hasattr(MessageHelperMixins.Message, 'delivered_to'):
                message = get_object_or_404(MessageHelperMixins.Message.objects.prefetch_related('delivered_to'), pk=message_id)
            else:
                message = get_object_or_404(MessageHelperMixins.Message, pk=message_id)
            extra_fields = extra_fields if (extra_fields := data.get('extra_fields')) and type(extra_fields) == dict else None
            if extra_fields:
                serializer = MessageHelperMixins.MessageSerializer(instance=message, data={**extra_fields, "is_edited": True}, partial=True)
                serializer.is_valid(raise_exception=True)
                instance = serializer.save()
                serialized_message = MessageHelperMixins.MessageSerializer(instance)
                return {"status": "successful", "action": "update", "message": serialized_message.data}
            else:
                raise ValidationError("'extra_fields' field should be provided for update action")

        else:
            raise ValidationError("Invalid action type")
    

    @staticmethod
    def _create_read_receipt(user, message_id):
        """
            Create read receipt(s) for message(s).

            Excludes messages where user is the sender. For multiple messages,
            uses bulk_create for efficiency and groups results by room.

            Args:
                user: User marking messages as read.
                message_id: Single ID or list of IDs.

            Returns:
                tuple: (room_id(s), serialized_message(s))
                    - Single: (room_id, message_dict)
                    - Multiple: (set of room_ids, dict of room_id → [messages])
                    - No valid messages: (None, {})
        """
        if isinstance(message_id, list):
            if hasattr(MessageHelperMixins.Message, 'delivered_to'):
                messages = MessageHelperMixins.Message.objects.filter(id__in=message_id).exclude(sender=user).prefetch_related('delivered_to').distinct()
            else:
                 messages = MessageHelperMixins.Message.objects.filter(id__in=message_id).exclude(sender=user).distinct()
            room_ids = set()
            receipts = []
            for message in messages:
                room_ids.add(str(message.room.id))
                receipts.append(MessageHelperMixins.ReadReceipt(message=message, reader=user))
            MessageHelperMixins.ReadReceipt.objects.bulk_create(receipts)
            serializer = MessageHelperMixins.MessageSerializer(messages, many=True)
            rooms = defaultdict(list)

            for m in serializer.data:
                room_id = m["room"]["id"]
                rooms[room_id].append(m)
            return room_ids, rooms

        else:
            if hasattr(MessageHelperMixins.Message, 'delivered_to'):
                message = get_object_or_404(MessageHelperMixins.Message.objects.prefetch_related('delivered_to'), pk=message_id)
            else:
                message = get_object_or_404(MessageHelperMixins.Message, pk=message_id)
            if message.sender != user:
                room_id = message.room.id

                MessageHelperMixins.ReadReceipt.objects.create(message=message, reader=user)
                serializer = MessageHelperMixins.MessageSerializer(message)

                return room_id, serializer.data
        return None, {}

    @staticmethod 
    def _retreive_messages(room, data):
        """
            Retrieve messages from a room with optional pagination.

            Prefetches all related data (read receipts, reactions, attachments,
            delivered_to) for efficient serialization. Orders by newest first.

            Args:
                room: The Room instance.
                data (dict): Optional 'paginate' dict with 'page' and 'size'.

            Returns:
                dict: Contains 'data' with room_id and messages. If paginated,
                    includes pagination metadata (has_next, has_previous,
                    next_page_number, prev_page_number, page, size).

            Raises:
                ValidationError: If pagination params invalid or missing.
        """
        
        read_r = MessageHelperMixins.ReadReceipt._meta.get_field("message").remote_field.get_accessor_name()
        reactions_r = MessageHelperMixins.Reaction._meta.get_field("message").remote_field.get_accessor_name()
        attachm = MessageHelperMixins.MessageMediaAsset._meta.get_field("message").remote_field.get_accessor_name()
        if hasattr(MessageHelperMixins.Message, 'delivered_to'):
            messages = MessageHelperMixins.Message.objects.filter(room=room, is_deleted=False).prefetch_related(read_r, reactions_r, attachm, 'delivered_to').order_by('-created_at')
        else:

            messages = MessageHelperMixins.Message.objects.filter(room=room, is_deleted=False).prefetch_related(read_r, reactions_r, attachm).order_by('-created_at')

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
        serialized_messages = MessageHelperMixins.MessageSerializer(messages, many=True)

        response["data"] = {
            "room_id": str(room.id),
            "messages": serialized_messages.data
        }

        return response




class RoomHelperMixins:
    """
        Synchronous business logic for room operations.

        Handles:
        - Room creation (OneToOneChat, GroupChat, Channel) with properties
        - Listing user's rooms with polymorphic queries
        - Retrieving room details
        - Adding/removing members with validation
        - Joining/leaving rooms
        - Modifying rooms (update, delete, permissions, admins/moderators)

        All methods are synchronous and wrapped by RoomHandlerMixin for async use.
    """

    def __init_subclass__(cls, **kwargs):
        """Load models and serializers when helper is subclassed."""
        super().__init_subclass__(**kwargs)
        RoomHelperMixins._load_variables()

    @classmethod
    def _load_variables(cls):
        """Load required models and serializers."""
        # models
        cls.Room = get_model("Room")
        cls.GroupChat = get_model("GroupChat")
        cls.OneToOneChat = get_model("OneToOneChat")
        cls.Channel = get_model("Channel")

        # serializers
        cls.RoomPolymorphicSerializer = get_serializer("RoomPolymorphicSerializer")
        cls.RoomListPolymorphicSerializer = get_serializer("RoomListPolymorphicSerializer")
        cls.RoomPropertySerializer = get_serializer("RoomPropertySerializer")

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        cls._load_variables()

    @staticmethod
    def _create_room(user, data):
        """Create a new room. Delegates to RoomPolymorphicSerializer."""
        serializer = RoomHelperMixins.RoomPolymorphicSerializer(data=data, context={"user": user})
        serializer.is_valid(raise_exception=True) 
        instance = serializer.save()
        room_serializer = RoomHelperMixins.RoomPolymorphicSerializer(instance)
        return room_serializer.data


    @staticmethod
    def _list_rooms(user):
        """
            List all rooms the user is a member of.

            Uses polymorphic query to fetch OneToOneChats, GroupChats, and
            Channels in a single query. Orders by last_message timestamp.

            Returns:
                list: Serialized rooms, or empty list if user has no rooms.
        """    

        onetoonechat__participants = f"{RoomHelperMixins.OneToOneChat._meta.model_name}__participants"
        groupchat__participants = f"{RoomHelperMixins.GroupChat._meta.model_name}__participants"
        channel__subscribers = f"{RoomHelperMixins.Channel._meta.model_name}__subscribers"

        rooms = RoomHelperMixins.Room.objects.filter(
            Q(**{onetoonechat__participants: user}) | Q(**{channel__subscribers: user}) | Q(**{groupchat__participants: user})
        ).select_related('last_message').order_by('-last_message__created_at')
        if rooms.exists():
            serializer = RoomHelperMixins.RoomListPolymorphicSerializer(rooms, many=True, context={"user": user})
            return serializer.data

        else:
            return []

    @staticmethod
    def _retreive_room(room):
        """Retrieve detailed room information."""
        serializer = RoomHelperMixins.RoomPolymorphicSerializer(room)
        return serializer.data

    
    @staticmethod
    def _add_members_to_room(user_ids, room):
        """
            Add users to a room.

            Filters out users already in the room. Works for both GroupChat
            (participants) and Channel (subscribers).

            Returns:
                tuple: (newly_added_user_objects, serialized_room, new_usernames)
        """
        members = room.participants if isinstance(room, RoomHelperMixins.GroupChat) else room.subscribers
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
        serialized_room = RoomHelperMixins.RoomPolymorphicSerializer(room).data
        return newly_added_users, serialized_room, new_member_usernames
    
    @staticmethod
    def _remove_members_from_room(user_ids, room, session_user):
        """
            Remove users from a room.

            Protects room creator from removal unless they remove themselves.
            Also removes users from admins/moderators when removed from room.

            Args:
                user_ids: List of user IDs to remove.
                room: The room instance.
                session_user: User performing the removal.

            Returns:
                tuple: (removed_user_objects, serialized_room, removed_usernames)

            Note:
                Room creator can only be removed by themselves, not by other admins.
        """
        members = room.participants if isinstance(room, RoomHelperMixins.GroupChat) else room.subscribers
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
        if isinstance(room, RoomHelperMixins.GroupChat):
            if hasattr(room, "admins"):
                room.admins.remove(*newly_removed_users)
        else:
            if hasattr(room, "moderators"):
                room.moderators.remove(*newly_removed_users)
        
        serialized_room = RoomHelperMixins.RoomPolymorphicSerializer(room).data
        return newly_removed_users, serialized_room, removed_members_username
    
    @staticmethod
    def _leave_room(user, room):
        """
            Remove current user from a room.

            Only works for GroupChat and Channel. Automatically removes user from
            admins/moderators. If room becomes empty, it's deleted by signals.

            Returns:
                dict | None: Serialized room, or None if room was deleted.

            Raises:
                ValidationError: If attempting to leave OneToOneChat.
        """        
        if not isinstance(room, (RoomHelperMixins.GroupChat, RoomHelperMixins.Channel)):
            raise ValidationError("You can only leave a channel/group chat")
        
        members = room.participants if isinstance(room, RoomHelperMixins.GroupChat) else room.subscribers
        
        if isinstance(room, RoomHelperMixins.GroupChat):
            if hasattr(room, "admins"):
                room.admins.remove(user)
        else:
            if hasattr(room, "moderators"):
                room.moderators.remove(user)
        members.remove(user) 
        if not room.pk:
            return None # meaning no more participants left and room is deleted
        serialized_room = RoomHelperMixins.RoomPolymorphicSerializer(room).data
        return serialized_room
    

    @staticmethod
    def _join_room(user, room_id):
        """
            Add current user to a room.

            Default implementation:
            - GroupChat: Raises error (admin must add)
            - Channel: Adds user if public, rejects if private
            - OneToOneChat: Raises error

            Raises:
                ValidationError: For GroupChat, private Channel, or OneToOneChat.
        """
        # if you have a different functionality for joining GroupChat or Channels 
        # override this method to replace with your custom functionality

        room = get_object_or_404(RoomHelperMixins.Room, pk=room_id)

        if isinstance(room, RoomHelperMixins.GroupChat):
            # User should implement a custom functionality for this or leave the exception
            raise ValidationError("Ask an admin to add you to the group")
        elif isinstance(room, RoomHelperMixins.Channel):
            if room.is_public:
                room.subscribers.add(user)
            else:
                raise ValidationError("Channel is private, ask a moderator to add you to the channel")
        else:
            raise ValidationError("You can only join a channel/group chat")
        
        serialized_room = RoomHelperMixins.RoomPolymorphicSerializer(room).data
        return serialized_room

    @staticmethod
    def _modify_room(data, room):
        """
            Modify room settings, permissions, or delete room.

            Supported actions:
            - delete: Deletes room and returns member list
            - update: Updates name, description, or property preferences
            - add/remove_permission: Manage object-level permissions
            - add/remove_admin: Manage GroupChat admins
            - add/remove_moderator: Manage Channel moderators

            Args:
                data (dict): Action and data fields with action-specific params.
                room: The room instance.

            Returns:
                dict: Serialized room or deletion confirmation with member list.

            Raises:
                ValidationError: For invalid actions, missing data, or permission
                    violations.

            Note:
                Room creator cannot have permissions removed. Override this method
                for custom room types or different permission logic.
        """

        VALID_ACTIONS = [
            "delete", "update", "add_permission", "remove_permission",
            "add_moderator", "add_admin", 
            "remove_moderator", "remove_admin"
        ]

        action = data.get('action')
        field_data = data.get('data')

        if not action:
            raise ValidationError("Action must be provided")

        if action not in VALID_ACTIONS:
            raise ValidationError("Invalid action type")
        
        if action == "delete":
            members = list(room.subscribers.all() if type(room) == RoomHelperMixins.Channel else room.participants.all())
            room.delete()
            return {"room_deleted": True, "members": members}


        if not field_data:
            raise ValidationError("data must be provided")

        if action == "update":
            if type(room) in [RoomHelperMixins.GroupChat, RoomHelperMixins.Channel]:
                name = field_data.get("name")
                desc = field_data.get("description")
                avatar = field_data.get('avatar')
                if name:
                    room.name = name
                if desc:
                    room.description = desc

                if avatar and hasattr(room, "avatar"):
                    room.avatar = avatar
                
                if type(room) == RoomHelperMixins.GroupChat:
                    if "join_approval_required" in field_data:
                        join_approval_required = field_data.get("join_approval_required")
                        if isinstance(join_approval_required, bool) and\
                            hasattr(room, 'join_approval_required'):
                            room.join_approval_required = join_approval_required
                    if "group_locked" in field_data:
                        group_locked = field_data.get("group_locked")
                        if isinstance(group_locked, bool) and\
                            hasattr(room, 'group_locked'):
                            room.group_locked = group_locked

                else:
                    if "is_public" in field_data:
                        is_public = field_data.get("is_public")
                        if isinstance(is_public, bool) and\
                            hasattr(room, 'is_public'):
                            room.is_public = is_public
            if "property" in field_data:
                room_props = RoomHelperMixins.RoomPropertySerializer(instance=room.property, data=field_data.get("property"), partial=True)
                room_props.is_valid(raise_exception=True)
                room_props.save()
            room.save()
        elif not isinstance(room, RoomHelperMixins.OneToOneChat) and action in [
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
            
            room_members = set(room.participants.all()) if isinstance(room, RoomHelperMixins.GroupChat) else set(room.subscribers.all())
            members = set(User.objects.filter(pk__in=member_ids))
            room_member_difference = members.difference(room_members)
            members = members.difference(room_member_difference)

            if action in ["add_permission", "remove_permission"]:
                VALID_GROUP_CHAT_PERMS = ["can_add_new_participants", "can_remove_participants"]
                VALID_CHANNEL_PERMS = ["can_add_new_subscribers", "can_remove_subscribers", "can_send_messages"]
                permissions = field_data.get('permission')
                if not permissions:
                    raise ValidationError("Permission to add or remove should be passed")
                if not isinstance(permissions, list):
                    raise ValidationError("Permission must be a list")
                permissions = list(set(permissions))
                
                if isinstance(room, RoomHelperMixins.GroupChat):
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
                if not isinstance(room, RoomHelperMixins.GroupChat):
                    raise ValidationError("Room should be a group chat to modify the admins")
                

                if action == "add_admin":
                    room.admins.add(*members)
                else:
                    room.admins.remove(*members)
            else:
                if not isinstance(room, RoomHelperMixins.Channel):
                    raise ValidationError("Room should be a channel to modify the moderators")
                if action == "add_moderator":
                    room.moderators.add(*members)
                else:
                    room.moderators.remove(*members)
        return RoomHelperMixins.RoomPolymorphicSerializer(room).data

            
            
class ChatNotificationHelperMixins:
    """
        Synchronous business logic for notification operations.

        Handles:
        - Retrieving and grouping notifications by room
        - Prefetching related data for efficient serialization

        All methods are synchronous and wrapped by ChatNotificationHandlerMixin
        for async use.
    """

    def __init_subclass__(cls, **kwargs):
        """Load serializer when helper is subclassed."""
        super().__init_subclass__(**kwargs)
        ChatNotificationHelperMixins._load_variables()

    @classmethod
    def _load_variables(cls):
        """Load required serializer."""
        # models
        cls.ChatNotificationSerializer = get_serializer("ChatNotificationSerializer")

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        cls._load_variables()
    
    def _get_and_group_chat_notifications(self, user):
        """
            Retrieve all notifications for a user, grouped by room.

            Uses prefetch_related to fetch polymorphic room objects efficiently,
            ensuring proper subclass resolution for serialization.

            Returns:
                dict: Room ID → list of notifications for that room.

            Note:
                prefetch_related is used instead of select_related because
                polymorphic relationships need separate queries to properly
                resolve subclass types (OneToOneChat, GroupChat, Channel).
        """

        chat_notifications = self.ChatNotification.objects.filter(recipients=user).prefetch_related(
            Prefetch(
                "message__room",
                queryset=self.Room.objects.all() # using Prefetch is redundant here (prefetch_related() alone works)..
            )

            # using prefetch_related() because it fetches room objects separately and maps it 
            # to their respectively subclasses (onetoone, group, channel)
            
            # using select_related() just returns the direct room object (Room <room_id>) 
            # which affects serialization...
        ).distinct().order_by("-message__room__created_at")
        
        serialized_chat_notifications = self.ChatNotificationSerializer(chat_notifications, many=True).data

        grouped_chat_notifications = defaultdict(list)
        for chat_notification in serialized_chat_notifications:
            
            room_id = chat_notification["message"]["room"]["id"]
            grouped_chat_notifications[room_id].append(chat_notification)


        return grouped_chat_notifications
    

class SessionHelperMixins:
    """
        Synchronous business logic for session management.

        Handles:
        - Registering new WebSocket sessions
        - Identifying active sessions (within INACTIVITY_THRESHOLD)
        - Identifying expired sessions for cleanup
        - Updating session heartbeats

        All methods are synchronous and wrapped by SessionHandlerMixin for async use.
    """
    
    def __init_subclass__(cls, **kwargs):
        """Load model and settings when helper is subclassed."""
        super().__init_subclass__(**kwargs)
        SessionHelperMixins._load_variables()

    @classmethod
    def _load_variables(cls):
        """Load required model and settings."""
        # models
        cls.Session = get_model("Session")

        # other variables
        cls.InactivityThreshold = realtime_chat_settings.INACTIVITY_THRESHOLD

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        cls._load_variables()


    @staticmethod
    def _get_expired_sessions(user_id):
        """
            Get channel names of sessions older than INACTIVITY_THRESHOLD.

            Used during connection cleanup to remove stale channel subscriptions.
        """        
        time_allowance = timezone.now() - datetime.timedelta(seconds=SessionHelperMixins.InactivityThreshold)
        expired_sessions = SessionHelperMixins.Session.objects.filter(user__id=user_id, last_seen__lt=time_allowance)
        return [s.channel_name for s in expired_sessions]
    
    @staticmethod
    def _register_session(user, channel_name):
        """Create a new session for the WebSocket connection."""
        session = SessionHelperMixins.Session.objects.create(
            user=user, 
            channel_name=channel_name, 
            last_seen=timezone.now()
        )
        

        return session

    @staticmethod 
    def _get_active_sessions(user_id):
        """
            Get channel names of active sessions (within INACTIVITY_THRESHOLD).

            Used to broadcast messages to all of a user's active devices.
        """

        time_allowance = timezone.now() - datetime.timedelta(seconds=SessionHelperMixins.InactivityThreshold)
        active_sessions = SessionHelperMixins.Session.objects.filter(user__id=user_id, last_seen__gte=time_allowance)
        return [s.channel_name for s in active_sessions]

    @staticmethod
    def _update_session(session):
        """Update session heartbeat timestamp to keep it active."""
        session.last_seen = timezone.now()
        session.save()
        

