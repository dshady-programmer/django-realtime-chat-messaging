from realtime_chat_messaging.permissions.handlers import PermissionHandler

# ==================== CUSTOM PERMISSION HANDLER ====================

class CustomPermissionHandler(PermissionHandler):
    """Custom permission handler with additional checks"""
    
    async def have_room_permission(self, user, room_id):
        """Override to add custom permission logic"""
        has_perm, room = await super().have_room_permission(user, room_id)
        
        # Add custom check: archived rooms are read-only
        if has_perm and hasattr(room, 'archived'):
            if room.archived:
                # User can view but not send messages
                return (has_perm, room)
        
        return (has_perm, room)