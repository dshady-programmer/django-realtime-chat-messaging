
from realtime_chat_messaging.utils.decorators import sqlite_safe_db_sync_to_async
from .helper_mixins import PermissionHelperMixin

class PermissionHandler(PermissionHelperMixin):
    @sqlite_safe_db_sync_to_async
    def have_room_permission(self, user, room_id):
        return self._have_room_permission(user, room_id)


    @sqlite_safe_db_sync_to_async
    def have_message_permission(self, user, message_id):
        return self._have_message_permission(user, message_id)


    @sqlite_safe_db_sync_to_async
    def is_message_sender(self, user, message_id):
        return self._is_message_sender(user, message_id)


    @sqlite_safe_db_sync_to_async
    def have_room_permissions_to_add_or_remove_members(self, user, room_id, perm_phrase):
        return self._have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase)


    @sqlite_safe_db_sync_to_async
    def have_send_message_permission(self, user, data):
        return self._have_send_message_permission(user, data)

    @sqlite_safe_db_sync_to_async
    def have_admin_privileges(self, user, room_id):
        return self._have_admin_privileges(user, room_id)

