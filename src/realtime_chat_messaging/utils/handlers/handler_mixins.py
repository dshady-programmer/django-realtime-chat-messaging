"""
Handler mixins providing async-safe wrappers for chat operations.

These mixins wrap synchronous helper methods with sqlite_safe_db_sync_to_async
to enable safe database access from async WebSocket consumers. Each mixin
handles a specific domain of chat functionality.

The mixins delegate actual business logic to helper mixins (which contain
the synchronous implementation), while providing the async interface required
by Django Channels consumers.

Architecture:
    Handler Mixin (async) → Helper Mixin (sync) → Database operations
"""



from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async
from .helper_mixins import MessageHelperMixins, RoomHelperMixins, ChatNotificationHelperMixins, SessionHelperMixins
from realtime_chat_messaging.utils.loader import get_model
from realtime_chat_messaging.conf import realtime_chat_settings 
enable_notification = realtime_chat_settings.ENABLE_NOTIFICATION


class ChatNotificationHandlerMixin(ChatNotificationHelperMixins):
    """
        Async handler for chat notification operations.

        Provides async-safe methods for:
        - Retrieving and grouping notifications
        - Creating notifications on message send
        - Updating notifications on message delivery

        All methods wrap synchronous helper implementations with
        sqlite_safe_db_sync_to_async for safe async execution.
    """

    def __init_subclass__(cls, **kwargs):
        """Load models when handler is subclassed."""
        super().__init_subclass__(**kwargs)
        ChatNotificationHandlerMixin._load_variables()

    @classmethod
    def _load_variables(cls):
        """Load required models from configuration."""
        # models
        cls.ChatNotification = get_model("ChatNotification")
        cls.Message = get_model("Message")

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        ChatNotificationHelperMixins._reload_variables()
        cls._load_variables()
    


    @sqlite_safe_db_sync_to_async
    def get_and_group_chat_notifications(self, user):
        """
            Retrieve and group all pending notifications for a user.

            Called on WebSocket connection to send undelivered message
            notifications to the client.

            Args:
                user: The user to retrieve notifications for.

            Returns:
                dict: Grouped notifications by room/type.
        """        
        return self._get_and_group_chat_notifications(user)
    

    @staticmethod
    def create_chat_notification(message, type, user):
        """
            Create notification for a message sent to a room.

            Adds all room participants (except sender) as notification recipients.
            Recipients are removed as they acknowledge delivery.

            Args:
                message: The Message instance.
                type: Notification type from NOTIFICATION_TYPE choices.
                user: The message sender (excluded from recipients).

            Returns:
                list: Users who were added as recipients, or None if room
                    has no participants/subscribers.

            Note:
                Auto-deleted by signals when all recipients acknowledge delivery.
        """
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
        """
            Remove user from notification recipients and mark messages as delivered.

            Called when user acknowledges message delivery. Updates both the
            ChatNotification (if enabled) and Message.delivered_to field.

            Args:
                message_id: Single message ID or list of message IDs.
                user: The user acknowledging delivery.
                many (bool): If True, message_id is a list. If False, it's a
                    single ID.

            Returns:
                QuerySet: Updated Message instances.

            Note:
                Notifications are auto-deleted by signals when recipients list
                becomes empty.
        """        
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
    """
        Async handler for message operations.

        Provides async-safe methods for:
        - Creating messages (send, reply, forward)
        - Modifying messages (update, delete)
        - Reactions (add, remove)
        - Read receipts
        - Message acknowledgment (delivery tracking)
        - Retrieving paginated message lists

        All methods wrap synchronous helper implementations.
    """

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        MessageHelperMixins._reload_variables()

        
    @sqlite_safe_db_sync_to_async
    def create_message(self, data, user):
        """Create a new message in a room."""
        return self._create_message(data, user)
    

    @sqlite_safe_db_sync_to_async
    def react_to_message(self, data, user):
        """Add or remove a reaction to a message."""
        return self._react_to_message(data, user)
    
    @sqlite_safe_db_sync_to_async
    def message_acknowledged(self, user, message_id):
        """Mark message(s) as delivered to the sender."""
        return self._message_acknowledged(user, message_id)
    
    @sqlite_safe_db_sync_to_async
    def modify_message(self, data):
        """Update or delete message(s)."""
        return self._modify_message(data)
    
    @sqlite_safe_db_sync_to_async
    def create_read_receipt(self, user, message_id):
        """Mark message(s) as read by user."""
        return self._create_read_receipt(user, message_id)
    
    @sqlite_safe_db_sync_to_async
    def retreive_messages(self, room, data):
        """Retrieve paginated messages from a room."""
        return self._retreive_messages(room, data)


class RoomHandlerMixin(RoomHelperMixins):
    """
        Async handler for room operations.

        Provides async-safe methods for:
        - Creating rooms (OneToOneChat, GroupChat, Channel)
        - Listing user's rooms
        - Retrieving room details
        - Adding/removing members
        - Joining/leaving rooms
        - Modifying room settings and permissions

        All methods wrap synchronous helper implementations.
    """

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        RoomHelperMixins._reload_variables()
    
    @sqlite_safe_db_sync_to_async
    def create_room(self, user, data):
        """Create a new room (OneToOneChat, GroupChat, or Channel)."""
        return self._create_room(user, data)
    
    @sqlite_safe_db_sync_to_async
    def list_rooms(self, user):
        """List all rooms the user has access to."""
        return self._list_rooms(user)
    
    @sqlite_safe_db_sync_to_async
    def retreive_room(self, room):
        """Retrieve detailed information about a room."""
        return self._retreive_room(room)
    
    @sqlite_safe_db_sync_to_async
    def add_members_to_room(self, user_ids, room):
        """Add users to a room (participants or subscribers)."""
        return self._add_members_to_room(user_ids, room)
    
    @sqlite_safe_db_sync_to_async
    def remove_members_from_room(self, user_ids, room, session_user):
        """Remove users from a room."""
        return self._remove_members_from_room(user_ids, room, session_user)
    
    @sqlite_safe_db_sync_to_async
    def leave_room(self, user, room):
        """Remove current user from a room."""
        return self._leave_room(user, room)
    
    @sqlite_safe_db_sync_to_async
    def join_room(self, user, room_id):
        """Add current user to a room (typically channels)."""
        return self._join_room(user, room_id)
    
    @sqlite_safe_db_sync_to_async
    def modify_room(self, data, room):
        """Update room settings, permissions, or delete room."""
        return self._modify_room(data, room)


class SessionHandlerMixin(SessionHelperMixins):
    """
        Async handler for session management.

        Provides async-safe methods for:
        - Registering new WebSocket sessions
        - Tracking active sessions (multi-device support)
        - Identifying expired sessions for cleanup
        - Updating session heartbeats

        Sessions enable multi-device support by tracking all active WebSocket
        connections for each user.

        All methods wrap synchronous helper implementations.
    """

    @classmethod
    def _reload_variables(cls):
        """Reload variables when settings change (for tests)."""
        SessionHelperMixins._reload_variables()

    @sqlite_safe_db_sync_to_async
    def get_expired_sessions(self, user_id):
        """Get sessions older than INACTIVITY_THRESHOLD."""
        return self._get_expired_sessions(user_id)
    

    @sqlite_safe_db_sync_to_async   
    def register_session(self, user, channel_name):
        """Register a new WebSocket session."""
        return self._register_session(user, channel_name)
    
    @sqlite_safe_db_sync_to_async
    def get_active_sessions(self, user_id):
        """Get all active channel names for a user."""
        return self._get_active_sessions(user_id)
    
    @sqlite_safe_db_sync_to_async
    def update_session(self, session):
        """Update session heartbeat timestamp."""
        return self._update_session(session)
    

