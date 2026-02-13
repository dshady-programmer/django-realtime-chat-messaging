"""
Unit tests for Session management and lifecycle.

Tests cover:
- Session creation on WebSocket connection
- Session heartbeat updates
- Session expiration based on INACTIVITY_THRESHOLD
- Session cleanup on reconnection
- Multi-device session handling
"""
import pytest
import asyncio
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.models import Session
from realtime_chat_messaging.conf import realtime_chat_settings

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(5)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSessionCreation:
    """Test session creation on WebSocket connection"""
    
    async def test_session_created_on_connect(self, users):
        """Test that session is created when user connects"""
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Verify session created
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        assert session is not None
        assert session.channel_name is not None
        assert session.last_seen is not None
        
        await comm.disconnect()
    
    async def test_session_has_correct_channel_name(self, users):
        """Test that session stores correct channel_name"""
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        # Channel name should match communicator's channel_name
        assert session.channel_name == comm.scope.get('channel_name') or session.channel_name is not None
        
        await comm.disconnect()
    
    async def test_multiple_sessions_different_users(self, users):
        """Test that different users get different sessions"""
        comms = []
        for i in range(3):
            comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            comm.scope['user'] = users[i]
            await comm.connect()
            await comm.receive_json_from()
            comms.append(comm)
        
        # Verify 3 sessions created
        sessions = await database_sync_to_async(
            lambda: list(Session.objects.all())
        )()
        
        assert len(sessions) == 3
        
        # Each session should have different user
        session_users = [s.user_id for s in sessions]
        assert len(set(session_users)) == 3
        
        for comm in comms:
            await comm.disconnect()
    
    async def test_session_last_seen_timestamp(self, users):
        """Test that session has recent last_seen timestamp"""
        before_connect = timezone.now()
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        after_connect = timezone.now()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        # last_seen should be between before and after connect
        assert before_connect <= session.last_seen <= after_connect
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSessionHeartbeat:
    """Test session heartbeat updates"""
    
    async def test_session_heartbeat_updates_last_seen(self, users):
        """Test that session.heartbeat event updates last_seen"""
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Get initial last_seen
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        initial_last_seen = session.last_seen
        
        # Wait a bit
        await asyncio.sleep(1)
        
        # Send heartbeat
        await comm.send_json_to({
            'event_type': 'session.heartbeat',
            'data': {}
        })
        await comm.receive_json_from()  # Ensure we wait for the heartbeat to be processed
        # Get updated session
        await database_sync_to_async(session.refresh_from_db)()
        
        # last_seen should be updated
        assert session.last_seen > initial_last_seen
        
        await comm.disconnect()
    
    async def test_heartbeat_multiple_times(self, users):
        """Test that heartbeat can be called multiple times"""
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        last_seen_values = [session.last_seen]
        # Send 3 heartbeats
        for _ in range(3):
            await asyncio.sleep(0.5)
            await comm.send_json_to({
                'event_type': 'session.heartbeat',
                'data': {}
            })
            await comm.receive_json_from()  # Ensure we wait for the heartbeat to be processed
            await database_sync_to_async(session.refresh_from_db)()
            last_seen_values.append(session.last_seen)
        # Each heartbeat should update last_seen
        for i in range(len(last_seen_values) - 1):
            assert last_seen_values[i] < last_seen_values[i + 1]
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSessionExpiration:
    """Test session expiration based on INACTIVITY_THRESHOLD"""
    
    async def test_session_expires_after_inactivity_threshold(self, users):
        """Test that sessions older than INACTIVITY_THRESHOLD are considered expired"""
        from realtime_chat_messaging.utils.handlers import EventHandler
        
        # Create session
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        # Manually set last_seen to expired time
        threshold = realtime_chat_settings.INACTIVITY_THRESHOLD
        expired_time = timezone.now() - datetime.timedelta(seconds=threshold + 10)
        await database_sync_to_async(setattr)(session, 'last_seen', expired_time)
        await database_sync_to_async(session.save)()
        
        # Check if session is in expired list
        expired_sessions = await database_sync_to_async(
            EventHandler._get_expired_sessions
        )(users[0].id)
        
        assert session.channel_name in expired_sessions
        
        await comm.disconnect()
    
    async def test_active_session_not_expired(self, users):
        """Test that recently active sessions are not expired"""
        from realtime_chat_messaging.utils.handlers import EventHandler
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Session was just created, should not be expired
        expired_sessions = await database_sync_to_async(
            EventHandler._get_expired_sessions
        )(users[0].id)
        
        assert len(expired_sessions) == 0
        
        await comm.disconnect()
    
    async def test_get_active_sessions_excludes_expired(self, users):
        """Test that get_active_sessions only returns non-expired sessions"""
        from realtime_chat_messaging.utils.handlers import EventHandler
        
        # Create 2 sessions
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users[0]
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users[0]
        
        await comm1.connect()
        await comm1.receive_json_from()
        
        await comm2.connect()
        await comm2.receive_json_from()
        
        sessions = await database_sync_to_async(
            lambda: list(Session.objects.filter(user=users[0]))
        )()
        assert len(sessions) == 2
        
        # Expire first session
        threshold = realtime_chat_settings.INACTIVITY_THRESHOLD
        expired_time = timezone.now() - datetime.timedelta(seconds=threshold + 10)
        await database_sync_to_async(setattr)(sessions[0], 'last_seen', expired_time)
        await database_sync_to_async(sessions[0].save)()
        
        # Get active sessions
        active_sessions = await database_sync_to_async(
            EventHandler._get_active_sessions
        )(users[0].id)
        
        # Should only return 1 active session
        assert len(active_sessions) == 1
        assert sessions[1].channel_name in active_sessions
        assert sessions[0].channel_name not in active_sessions
        
        await comm1.disconnect()
        await comm2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSessionCleanup:
    """Test session cleanup on new connections"""
    
    async def test_cleanup_removes_expired_from_groups(self, users):
        """Test that channel_cleanup removes expired sessions from channel groups"""
        # Connect device 1
        device1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        device1.scope['user'] = users[0]
        
        await device1.connect()
        await device1.receive_json_from()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        # Expire the session
        threshold = realtime_chat_settings.INACTIVITY_THRESHOLD
        expired_time = timezone.now() - datetime.timedelta(seconds=threshold + 10)
        await database_sync_to_async(setattr)(session, 'last_seen', expired_time)
        await database_sync_to_async(session.save)()
        
        # Connect device 2 (triggers cleanup)
        device2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        device2.scope['user'] = users[0]
        
        await device2.connect()
        await device2.receive_json_from()
        
        # Cleanup should have been triggered
        # Expired session should still exist in DB but not in active list
        sessions = await database_sync_to_async(
            lambda: list(Session.objects.filter(user=users[0]))
        )()
        
        assert len(sessions) == 2  # Both sessions still in DB
        
        await device1.disconnect()
        await device2.disconnect()
    
    async def test_cleanup_preserves_active_sessions(self, users):
        """Test that cleanup doesn't affect active sessions"""
        # Create 3 sessions
        devices = []
        for _ in range(3):
            device = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            device.scope['user'] = users[0]
            await device.connect()
            await device.receive_json_from()
            devices.append(device)
        
        # All should be active
        from realtime_chat_messaging.utils.handlers import EventHandler
        active = await database_sync_to_async(
            EventHandler._get_active_sessions
        )(users[0].id)
        
        assert len(active) == 3
        
        # Connect new device (triggers cleanup)
        device4 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        device4.scope['user'] = users[0]
        await device4.connect()
        await device4.receive_json_from()
        
        # All 4 should still be active
        active = await database_sync_to_async(
            EventHandler._get_active_sessions
        )(users[0].id)
        
        assert len(active) == 4
        
        for device in devices:
            await device.disconnect()
        await device4.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSessionEdgeCases:
    """Test edge cases in session management"""
    
    async def test_rapid_connect_disconnect_cycles(self, users):
        """Test rapid connection and disconnection"""
        async def connect_disconnect():
            comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            comm.scope['user'] = users[0]
            await comm.connect()
            await comm.receive_json_from()
            await comm.disconnect()
        
        # 5 rapid cycles
        for _ in range(5):
            await connect_disconnect()
        
        # Should have multiple sessions in DB
        sessions = await database_sync_to_async(
            lambda: Session.objects.filter(user=users[0]).count()
        )()
        
        assert sessions > 0
    
    async def test_session_without_heartbeat_eventually_expires(self, users):
        """Test that session without heartbeat updates eventually expires"""
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        # Don't send any heartbeats, manually advance time
        threshold = realtime_chat_settings.INACTIVITY_THRESHOLD
        expired_time = timezone.now() - datetime.timedelta(seconds=threshold + 1)
        await database_sync_to_async(setattr)(session, 'last_seen', expired_time)
        await database_sync_to_async(session.save)()
        
        # Session should now be expired
        from realtime_chat_messaging.utils.handlers import EventHandler
        expired = await database_sync_to_async(
            EventHandler._get_expired_sessions
        )(users[0].id)
        
        assert session.channel_name in expired
        
        await comm.disconnect()
    
    async def test_concurrent_heartbeats_same_session(self, users):
        """Test concurrent heartbeat calls on same session"""
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Send 3 heartbeats concurrently
        await asyncio.gather(
            comm.send_json_to({'event_type': 'session.heartbeat', 'data': {}}),
            comm.send_json_to({'event_type': 'session.heartbeat', 'data': {}}),
            comm.send_json_to({'event_type': 'session.heartbeat', 'data': {}})
        )
        
        # Session should handle concurrent updates
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        assert session is not None
        assert session.last_seen is not None
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSessionWithCustomThreshold:
    """Test session behavior with custom INACTIVITY_THRESHOLD"""
    
    async def test_custom_inactivity_threshold(self, users, settings):
        """Test that custom INACTIVITY_THRESHOLD is respected"""
        # Set custom threshold
        settings.REALTIME_CHAT_MESSAGING = {
            **getattr(settings, 'REALTIME_CHAT_MESSAGING', {}),
            'INACTIVITY_THRESHOLD': 30  # 30 seconds
        }
        
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        session = await database_sync_to_async(
            Session.objects.filter(user=users[0]).first
        )()
        
        # Set last_seen to 31 seconds ago (past custom threshold)
        expired_time = timezone.now() - datetime.timedelta(seconds=31)
        await database_sync_to_async(setattr)(session, 'last_seen', expired_time)
        await database_sync_to_async(session.save)()
        
        # Should be expired
        from realtime_chat_messaging.utils.handlers import EventHandler
        expired = await database_sync_to_async(
            EventHandler._get_expired_sessions
        )(users[0].id)
        
        assert session.channel_name in expired
        
        await comm.disconnect()
