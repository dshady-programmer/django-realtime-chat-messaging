"""
Custom Consumer for Scenario 5: Consumer Extension (No Model Override)

This demonstrates extending the ChatMessagingConsumer to add custom functionality
without overriding any models. Use cases:
- Add custom event handlers
- Add logging/analytics
- Add rate limiting
- Add custom validation
- Add webhooks/external API calls
"""
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.permissions.handlers import PermissionHandler
from channels.db import database_sync_to_async
from django.utils import timezone
import logging
import json

logger = logging.getLogger(__name__)

permission_handler = PermissionHandler()

class CustomChatConsumer(ChatMessagingConsumer):
    """
    Extended consumer with custom functionality:
    
    1. Message analytics tracking
    2. Custom event: message.pin
    3. Custom event: message.flag
    4. Rate limiting per user
    5. Webhook notifications
    6. Enhanced logging
    """
    
    # Rate limiting: max messages per minute
    RATE_LIMIT_MESSAGES = 30
    RATE_LIMIT_WINDOW = 60  # seconds
    
    async def connect(self):
        """Override connect to add custom initialization"""
        # Call parent connect
        await super().connect()
        
        # Initialize custom tracking
        self.user_message_timestamps = []
        self.analytics_session_start = timezone.now()
        
        # Log connection with analytics
        await self._log_analytics('connection', {
            'user_id': self.scope['user'].id,
            'timestamp': str(timezone.now())
        })
        
        logger.info(f"Custom consumer connected: User {self.scope['user'].username}")
    
    async def disconnect(self, code):
        """Override disconnect to add cleanup and analytics"""
        # Calculate session duration
        if hasattr(self, 'analytics_session_start'):
            session_duration = (timezone.now() - self.analytics_session_start).total_seconds()
            
            await self._log_analytics('disconnection', {
                'user_id': self.scope['user'].id,
                'session_duration_seconds': session_duration,
                'messages_sent': len(self.user_message_timestamps)
            })
        
        logger.info(f"Custom consumer disconnected: User {self.scope['user'].username}")
        
        # Call parent disconnect
        await super().disconnect(code)
    
    async def receive(self, text_data):
        """Override receive to add rate limiting and validation"""
        data = json.loads(text_data)
        event_type = data.get('event_type', '')
        
        # Rate limiting for message.send events
        if event_type == 'message.send':
            if not await self._check_rate_limit():
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4029,
                        'message': 'Rate limit exceeded',
                        'detail': f'Maximum {self.RATE_LIMIT_MESSAGES} messages per {self.RATE_LIMIT_WINDOW} seconds'
                    }
                }))
                return
        
        # Enhanced logging
        logger.info(f"Event received: {event_type} from user {self.scope['user'].username}")
        
        # Call parent handler
        await super().receive(text_data)
    
    # ==================== CUSTOM EVENT HANDLERS ====================
    
    async def message_pin(self, data):
        """
        Custom event handler: Pin a message in a room
        
        Event: message.pin
        Data: {
            'message_id': str,
            'room_id': str
        }
        """
        try:
            message_id = data.get('message_id')
            room_id = data.get('room_id')
            
            if not message_id or not room_id:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4000,
                        'message': 'Missing required fields',
                        'detail': 'message_id and room_id are required'
                    }
                }))
                return
            
            # Verify permissions
            has_perm, room = await permission_handler.have_room_permission(
                self.scope['user'], room_id
            )
            
            if not has_perm:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4004,
                        'message': 'Permission denied',
                        'detail': 'You do not have access to this room'
                    }
                }))
                return
            
            # Check if user is admin (only admins can pin)
            is_admin, _ = await permission_handler.have_admin_privileges(
                self.scope['user'], str(room.id), 'pin_message'
            )

            if not is_admin:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4003,
                        'message': 'Forbidden',
                        'detail': 'Only admins can pin messages'
                    }
                }))
                return
            
            # Pin the message (store in cache or database)
            await self._pin_message_in_room(room_id, message_id)
            
            # Broadcast to room
            await self.channel_layer.group_send(
                f"group-{room_id}",
                {
                    'type': 'message.pinned',
                    'data': {
                        'message_id': message_id,
                        'room_id': room_id,
                        'pinned_by': self.scope['user'].username,
                        'pinned_at': str(timezone.now())
                    }
                }
            )
            
            # Log analytics
            await self._log_analytics('message_pinned', {
                'message_id': message_id,
                'room_id': room_id,
                'user_id': self.scope['user'].id
            })
            
        except Exception as e:
            logger.error(f"Error in message_pin: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': {
                    'code': 5000,
                    'message': 'Internal error',
                    'detail': 'Failed to pin message'
                }
            }))
    
    async def message_pinned(self, event):
        """Handler for broadcasting pinned message notification"""
        await self.send(text_data=json.dumps({
            'eventType': 'message.pinned',
            'data': event['data']
        }))
    
    async def message_flag(self, data):
        """
        Custom event handler: Flag a message for review
        
        Event: message.flag
        Data: {
            'message_id': str,
            'reason': str
        }
        """
        try:
            message_id = data.get('message_id')
            reason = data.get('reason', 'No reason provided')
            
            if not message_id:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4000,
                        'message': 'Missing message_id'
                    }
                }))
                return
            
            # Get message and verify access
            from realtime_chat_messaging.utils.loader import get_model
            Message = get_model('Message')
            
            message = await database_sync_to_async(
                Message.objects.filter(id=message_id).first
            )()
            
            if not message:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4004,
                        'message': 'Message not found'
                    }
                }))
                return
            
            # Verify user has access to room
            has_perm, room = await permission_handler.have_room_permission(
                self.scope['user'], str(message.room_id)
            )
            
            if not has_perm:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4003,
                        'message': 'Permission denied'
                    }
                }))
                return
            
            # Flag the message (store in database or cache)
            await self._flag_message(message_id, self.scope['user'].id, reason)
            
            # Send confirmation
            await self.send(text_data=json.dumps({
                'eventType': 'message.flagged',
                'data': {
                    'message_id': message_id,
                    'status': 'flagged',
                    'reason': reason
                }
            }))
            
            # Notify moderators (optional)
            await self._notify_moderators_of_flag(message.room_id, message_id, reason)
            
            # Log analytics
            await self._log_analytics('message_flagged', {
                'message_id': message_id,
                'flagger_id': self.scope['user'].id,
                'reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error in message_flag: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': {
                    'code': 5000,
                    'message': 'Failed to flag message'
                }
            }))
    
    async def message_analytics(self, data):
        """
        Custom event handler: Get message analytics for a room
        
        Event: message.analytics
        Data: {
            'room_id': str,
            'timeframe': str  # '24h', '7d', '30d'
        }
        """
        try:
            room_id = data.get('room_id')
            timeframe = data.get('timeframe', '24h')
            
            if not room_id:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4000,
                        'message': 'Missing room_id'
                    }
                }))
                return
            
            # Verify permissions
            has_perm, room = await permission_handler.have_room_permission(
                self.scope['user'], room_id
            )
            
            if not has_perm:
                await self.send(text_data=json.dumps({
                    'error': {
                        'code': 4004,
                        'message': 'Permission denied'
                    }
                }))
                return
            
            # Get analytics data
            analytics_data = await self._get_room_analytics(room_id, timeframe)
            
            await self.send(text_data=json.dumps({
                'eventType': 'message.analytics',
                'data': analytics_data
            }))
            
        except Exception as e:
            logger.error(f"Error in message_analytics: {str(e)}")
            await self.send(text_data=json.dumps({
                'error': {
                    'code': 5000,
                    'message': 'Failed to retrieve analytics'
                }
            }))
    
    # ==================== HELPER METHODS ====================
    
    async def _check_rate_limit(self):
        """Check if user has exceeded rate limit"""
        now = timezone.now()
        
        # Remove timestamps older than window
        cutoff = now.timestamp() - self.RATE_LIMIT_WINDOW
        self.user_message_timestamps = [
            ts for ts in self.user_message_timestamps 
            if ts > cutoff
        ]
        
        # Check if limit exceeded
        if len(self.user_message_timestamps) >= self.RATE_LIMIT_MESSAGES:
            return False
        
        # Add current timestamp
        self.user_message_timestamps.append(now.timestamp())
        return True
    
    async def _log_analytics(self, event_type, data):
        """Log analytics data to database or external service"""
        # In production, this could:
        # 1. Store in analytics database
        # 2. Send to analytics service (e.g., Mixpanel, Amplitude)
        # 3. Send to data warehouse
        
        log_entry = {
            'event_type': event_type,
            'timestamp': str(timezone.now()),
            'data': data
        }
        
        logger.info(f"Analytics: {json.dumps(log_entry)}")
        
        # Example: Store in cache for retrieval
        from django.core.cache import cache
        key = f"analytics:{event_type}:{data.get('user_id', 'unknown')}"
        cache.set(key, log_entry, timeout=3600)
    
    async def _pin_message_in_room(self, room_id, message_id):
        """Pin a message in a room (store in cache)"""
        from django.core.cache import cache
        
        key = f"pinned_messages:{room_id}"
        pinned = cache.get(key, [])
        
        if message_id not in pinned:
            pinned.append(message_id)
            cache.set(key, pinned, timeout=None)
    
    async def _flag_message(self, message_id, flagger_id, reason):
        """Flag a message for review"""
        from django.core.cache import cache
        
        key = f"flagged_messages:{message_id}"
        flag_data = {
            'message_id': message_id,
            'flagger_id': flagger_id,
            'reason': reason,
            'flagged_at': str(timezone.now())
        }
        cache.set(key, flag_data, timeout=86400)  # 24 hours
    
    async def _notify_moderators_of_flag(self, room_id, message_id, reason):
        """Notify moderators that a message was flagged"""
        # Get room moderators/admins
        from realtime_chat_messaging.utils.loader import get_model
        Room = get_model('Room')
        
        room = await database_sync_to_async(
            Room.objects.filter(id=room_id).first
        )()
        
        if not room:
            return
        
        # Get admins based on room type
        if hasattr(room, 'admins'):
            admins = await database_sync_to_async(
                lambda: list(room.admins.all())
            )()
        elif hasattr(room, 'moderators'):
            admins = await database_sync_to_async(
                lambda: list(room.moderators.all())
            )()
        else:
            admins = [room.creator] if hasattr(room, 'creator') else []
        
        # Send notification to each admin
        for admin in admins:
            await self.channel_layer.group_send(
                f"user-{admin.id}",
                {
                    'type': 'moderation.alert',
                    'data': {
                        'alert_type': 'message_flagged',
                        'message_id': message_id,
                        'room_id': str(room_id),
                        'reason': reason
                    }
                }
            )
    
    async def moderation_alert(self, event):
        """Handler for moderation alerts"""
        await self.send(json.dumps({
            'eventType': 'moderation.alert',
            'data': event['data']
        }))
    
    async def _get_room_analytics(self, room_id, timeframe):
        """Get analytics data for a room"""
        from django.utils import timezone
        from datetime import timedelta
        from realtime_chat_messaging.utils.loader import get_model
        
        Message = get_model('Message')
        
        # Calculate time range
        now = timezone.now()
        if timeframe == '24h':
            start_time = now - timedelta(hours=24)
        elif timeframe == '7d':
            start_time = now - timedelta(days=7)
        elif timeframe == '30d':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=24)
        
        # Get message count
        message_count = await database_sync_to_async(
            Message.objects.filter(
                room_id=room_id,
                created_at__gte=start_time
            ).count
        )()
        
        # Get unique senders
        unique_senders = await database_sync_to_async(
            lambda: Message.objects.filter(
                room_id=room_id,
                created_at__gte=start_time
            ).values_list('sender_id', flat=True).distinct().count()
        )()
        
        return {
            'room_id': room_id,
            'timeframe': timeframe,
            'message_count': message_count,
            'unique_senders': unique_senders,
            'start_time': str(start_time),
            'end_time': str(now)
        }
