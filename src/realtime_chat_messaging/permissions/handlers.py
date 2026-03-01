"""
Permission handler providing async-safe authorization checks.

Wraps synchronous permission logic from PermissionHelperMixin with
sqlite_safe_db_sync_to_async for use in async WebSocket consumers.

All methods delegate to helper mixins where the actual authorization logic
is implemented. Override helper methods to customize permission behavior.
"""



from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async
from .helper_mixins import PermissionHelperMixin

class PermissionHandler(PermissionHelperMixin):


    """
    Async-safe permission handler for WebSocket authorization.

    Wraps synchronous helper methods for safe async execution. Used by
    permission decorators to enforce authorization checks.

    All methods return (is_permitted: bool, room: Room | None) tuples
    except have_message_permission which returns bool only.
    """

    @sqlite_safe_db_sync_to_async
    def have_room_permission(self, user, room_id):
        """Check if user is a room member."""
        return self._have_room_permission(user, room_id)


    @sqlite_safe_db_sync_to_async
    def have_message_permission(self, user, message_id):
        """Check if user has access to message(s)."""
        return self._have_message_permission(user, message_id)


    @sqlite_safe_db_sync_to_async
    def is_message_sender(self, user, message_id):
        """Check if user is the sender of message(s)."""
        return self._is_message_sender(user, message_id)


    @sqlite_safe_db_sync_to_async
    def have_room_permissions_to_add_or_remove_members(self, user, room_id, perm_phrase):
        """Check if user can add or remove members."""
        return self._have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase)


    @sqlite_safe_db_sync_to_async
    def have_send_message_permission(self, user, data):
        """Check if user can send messages to the room."""
        return self._have_send_message_permission(user, data)

    @sqlite_safe_db_sync_to_async
    def have_admin_privileges(self, user, room_id, action):
        """Check if user has admin/moderator privileges."""
        return self._have_admin_privileges(user, room_id, action)

