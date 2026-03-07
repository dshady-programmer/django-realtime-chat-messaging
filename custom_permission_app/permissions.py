"""
Custom Permission Handler for Scenario 3: Permissions-only override testing.

This demonstrates overriding only the permission handler while using
all default models and serializers.
"""
from realtime_chat_messaging.permissions.handlers import PermissionHandler
from channels.db import database_sync_to_async


class CustomPermissionHandler(PermissionHandler):
    """
    Custom Permission Handler with additional business logic:
    
    1. Archived rooms are read-only (no message sending)
    2. VIP users bypass certain restrictions
    3. Time-based permissions (e.g., no messaging after hours)
    4. Quota-based permissions (message limits per user)
    """
    
    async def have_room_permission(self, user, room_id):
        """
        Override to add archived room check.
        Archived rooms can be viewed but not modified.
        """
        has_perm, room = await super().have_room_permission(user, room_id)
        
        if not has_perm:
            return (False, room)
        
        # Check if room is archived (if RoomProperty has archived field)
        if await database_sync_to_async(lambda: hasattr(room, 'property') and room.property)():
            is_archived = await database_sync_to_async(
                lambda: room.property.preferences.get('archived')
            )()
            
            if is_archived:
                # Can view but cannot send messages
                # This will be enforced in have_send_message_permission
                return (has_perm, room)
        
        return (has_perm, room)
    
    async def have_send_message_permission(self, user, data):
        """
        Override to add:
        - Archived room check
        - VIP user bypass
        - Time-based restrictions
        """
        
        is_permitted, room =  await super().have_send_message_permission(user, data)
        
        # Check if room is archived
        if await database_sync_to_async(lambda: hasattr(room, 'property') and room.property)():
            is_archived = await database_sync_to_async(
                lambda: room.property.preferences.get('archived')
            )()
            
            if is_archived:
                # VIP users can send messages even in archived rooms
                is_vip = await self._is_vip_user(user, room)
                if not is_vip:
                    return False, room
        
        # Check VIP bypass first
        is_vip = await self._is_vip_user(user, room)
        if is_vip:
            return True, room  # VIP users can always send messages
        
        # Check time-based restrictions
        if not await self._is_within_allowed_hours():
            return False, room
        
        if not await self.check_message_quota(user, room):
            return False, room
        
        # Delegate to parent implementation
        return is_permitted, room
    
    async def have_admin_privileges(self, user, room_id, action):
        """
        Override to add VIP user privileges.
        VIP users have admin privileges in all rooms.
        """
        is_permitted, room = await super().have_admin_privileges(user, room_id, action)
        # VIP users are always admins
        is_vip = await self._is_vip_user(user, room)
        if is_vip:
            return True, room
    
        # Delegate to parent implementation
        return is_permitted, room
    
    async def have_room_permissions_to_add_or_remove_members(self, user, room_id, perm_phrase):
        """
        Override to add VIP user privileges.
        """

        is_permitted, room = await super().have_room_permissions_to_add_or_remove_members(user, room_id, perm_phrase)
        # VIP users can always add/remove members
        is_vip = await self._is_vip_user(user, room)

        if is_vip:
            return True, room
        
        return is_permitted, room
    
    
    # Helper methods
    
    async def _is_vip_user(self, user, room):
        """
        Check if user is VIP.
        In production, this would check a User.is_vip field or group membership in a particular room
        """
        # Check if user has 'vip' in username (for testing)
        vip = 'vip' in user.username.lower()
        is_member = False
        if (hasattr(room, "participants")):
            if await database_sync_to_async(lambda: room.participants.filter(pk=user.pk).exists())():
                is_member = True
        elif (hasattr(room, "subscribers")):
            if await database_sync_to_async(lambda: room.subscribers.filter(pk=user.pk).exists())():
                is_member = True
        return vip and is_member
    
    async def _is_within_allowed_hours(self):
        """
        Check if current time is within allowed messaging hours.
        For testing, we'll allow 24/7, but this could be:
        - Business hours only (9 AM - 5 PM)
        - Exclude late night (11 PM - 6 AM)
        - Weekend restrictions
        """
        from datetime import datetime
        
        # Example: No messages between 11 PM and 6 AM
        current_hour = datetime.now().hour
        
        # For testing, allow all hours
        return True
        
        # Uncomment for actual restriction:
        # return not (23 <= current_hour or current_hour < 6)
    
    async def check_message_quota(self, user, room):
        """
        Check if user has exceeded message quota for this room.
        Returns True if user can send more messages.
        """
        # Example: Max 100 messages per user per room per day
        from django.utils import timezone
        from datetime import timedelta
        from realtime_chat_messaging.utils.loader import get_model
        
        Message = get_model('Message')
        
        # Count messages from user in this room in last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        
        count = await database_sync_to_async(
            Message.objects.filter(
                room=room,
                sender=user,
                created_at__gte=yesterday
            ).count
        )()
        
        # VIP users have higher quota
        is_vip = await self._is_vip_user(user, room)
        max_quota = 500 if is_vip else 100
        
        return count < max_quota
