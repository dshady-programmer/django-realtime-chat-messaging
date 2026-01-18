from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async
from .helper_mixins import MessageHelperMixins, RoomHelperMixins, ChatNotificationHelperMixins, SessionHelperMixins
from realtime_chat_messaging.utils.loader import get_model
from realtime_chat_messaging.conf import realtime_chat_settings 
enable_notification = realtime_chat_settings.ENABLE_NOTIFICATION


class ChatNotificationHandlerMixin(ChatNotificationHelperMixins):


    ChatNotification = get_model("ChatNotification")
    Message = get_model("Message")
    


    @sqlite_safe_db_sync_to_async
    def get_and_group_chat_notifications(self, user):
        return self._get_and_group_chat_notifications(user)
    

    @staticmethod
    def create_chat_notification(message, type, user):
        room = message.room
        recipients = None
        if hasattr(room, "subscribers"):
            recipients = list(room.subscribers.all())
        elif hasattr(room, "participants"):
            recipients = list(room.participants.all())

        if recipients is not None:
            if user in recipients:
                recipients.remove(user)
            notification = ChatNotificationHandlerMixin.ChatNotification.objects.create(message=message, notification_type=type)
            notification.recipients.set(recipients)
        return recipients
    
    @staticmethod
    def update_chat_notification(message_id, user, many=False):
        ids = []
        if many:
            """
                if many == True:
                then message = [id1, id2...]
            """
            ids.extend(message_id)
        else:
            ids.append(message_id)

        ids = set(ids)
        if enable_notification:
            notifications = ChatNotificationHandlerMixin.ChatNotification.objects.filter(message__id__in=ids, recipients=user).distinct()
            if notifications.exists():
                for notification in notifications:
                    notification.recipients.remove(user)

        try:
            messages = ChatNotificationHandlerMixin.Message.objects.prefetch_related('delivered_to').filter(pk__in=ids)
        except AttributeError:
            messages = ChatNotificationHandlerMixin.Message.objects.filter(pk__in=ids)
        for message in messages:
            if hasattr(message, 'delivered_to'):
                message.delivered_to.add(user)

        return messages


class MessageHandlerMixin(MessageHelperMixins):

    @sqlite_safe_db_sync_to_async
    def create_message(self, data, user):
        return self._create_message(data, user)
    

    @sqlite_safe_db_sync_to_async
    def react_to_message(self, data, user):
        return self._react_to_message(data, user)
    
    @sqlite_safe_db_sync_to_async
    def message_acknowledged(self, user, message_id):
        return self._message_acknowledged(user, message_id)
    
    @sqlite_safe_db_sync_to_async
    def modify_message(self, data):
        return self._modify_message(data)
    
    @sqlite_safe_db_sync_to_async
    def create_read_receipt(self, user, message_id):
        return self._create_read_receipt(user, message_id)
    
    @sqlite_safe_db_sync_to_async
    def retreive_messages(self, room, data):
        return self._retreive_messages(room, data)


class RoomHandlerMixin(RoomHelperMixins):
    
    @sqlite_safe_db_sync_to_async
    def create_room(self, user, data):
        return self._create_room(user, data)
    
    @sqlite_safe_db_sync_to_async
    def list_rooms(self, user):
        return self._list_rooms(user)
    
    @sqlite_safe_db_sync_to_async
    def retreive_room(self, room):
        return self._retreive_room(room)
    
    @sqlite_safe_db_sync_to_async
    def add_members_to_room(self, user_ids, room):
        return self._add_members_to_room(user_ids, room)
    
    @sqlite_safe_db_sync_to_async
    def remove_members_from_room(self, user_ids, room, session_user):
        return self._remove_members_from_room(user_ids, room, session_user)
    
    @sqlite_safe_db_sync_to_async
    def leave_room(self, user, room):

        return self._leave_room(user, room)
    
    @sqlite_safe_db_sync_to_async
    def join_room(self, user, room_id):
        return self._join_room(user, room_id)
    
    @sqlite_safe_db_sync_to_async
    def modify_room(self, data, room):
        return self._modify_room(data, room)


class SessionHandlerMixin(SessionHelperMixins):

    @sqlite_safe_db_sync_to_async
    def get_expired_sessions(self, user_id):
        return self._get_expired_sessions(user_id)
    

    @sqlite_safe_db_sync_to_async   
    def register_session(self, user, channel_name):
        return self._register_session(user, channel_name)
    
    @sqlite_safe_db_sync_to_async
    def get_active_sessions(self, user_id):
        return self._get_active_sessions(user_id)
