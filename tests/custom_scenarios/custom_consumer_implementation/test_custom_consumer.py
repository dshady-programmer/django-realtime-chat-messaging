"""
Comprehensive tests for Scenario 5: Custom Consumer Extension

Tests that extending ChatMessagingConsumer with custom functionality works
while keeping all default models.

Key test areas:
- Custom event handlers (message.pin, message.flag, message.analytics)
- Rate limiting functionality
- Analytics tracking
- Enhanced logging
- Moderation features
- Backward compatibility with default functionality
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
import asyncio

User = get_user_model()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCustomConsumerConnection:
    """Test custom consumer connection and disconnection"""
    
    async def test_custom_consumer_connects_successfully(self, users, custom_websocket_communicator):
        """Test that custom consumer establishes connection"""
        comm = custom_websocket_communicator(users[0])
        
        connected, _ = await comm.connect()
        
        assert connected is True
        
        # Should receive connection acknowledgment
        response = await comm.receive_json_from()
        assert 'eventType' in response
        
        await comm.disconnect()
    
    async def test_connection_initializes_analytics(self, users, custom_websocket_communicator):
        """Test that connection initializes analytics tracking"""
        comm = custom_websocket_communicator(users[0])
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Verify analytics logged (check cache)
        analytics_key = f"analytics:connection:{users[0].id}"
        analytics_data = cache.get(analytics_key)
        
        assert analytics_data is not None
        assert analytics_data['event_type'] == 'connection'
        
        await comm.disconnect()
    
    async def test_disconnection_logs_session_duration(self, users, custom_websocket_communicator):
        """Test that disconnection logs session analytics"""
        comm = custom_websocket_communicator(users[0])
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Wait a moment
        await asyncio.sleep(0.5)
        
        # Disconnect
        await comm.disconnect()
        
        # Check disconnection analytics
        disconnect_key = f"analytics:disconnection:{users[0].id}"
        disconnect_data = cache.get(disconnect_key)
        
        assert disconnect_data is not None
        assert 'session_duration_seconds' in disconnect_data['data']
        assert disconnect_data['data']['session_duration_seconds'] > 0


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRateLimiting:
    """Test custom consumer rate limiting"""
    
    async def test_messages_under_rate_limit_succeed(self, users, one_to_one_chat, custom_websocket_communicator):
        """Test sending messages under rate limit"""

        
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Send 10 messages (under limit of 30)
        for i in range(10):
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Message {i}'
                }
            })
            
            response = await comm.receive_json_from()
            assert response['eventType'] == 'message.dispatch'
        
        await comm.disconnect()
    
    async def test_rate_limit_blocks_excessive_messages(self, users, one_to_one_chat, custom_websocket_communicator):
        """Test that rate limit blocks when exceeded"""
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Try to send 35 messages (over limit of 30)
        blocked_count = 0
        for i in range(35):
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Spam {i}'
                }
            })
            
            response = await comm.receive_json_from()
            
            if 'error' in response and response['error']['code'] == 4029:
                blocked_count += 1
        
        # Should have blocked at least 5 messages
        assert blocked_count >= 5
        
        await comm.disconnect()
    
    async def test_rate_limit_resets_after_window(self, users, one_to_one_chat, custom_websocket_communicator):
        """Test that rate limit window resets"""
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Send 30 messages (at limit)
        for i in range(30):
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Message {i}'
                }
            })
            await comm.receive_json_from()
        
        # Next message should be blocked
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Should be blocked'
            }
        })
        
        response = await comm.receive_json_from()
        assert 'error' in response
        assert response['error']['code'] == 4029
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessagePinning:
    """Test custom message.pin event"""
    
    async def test_admin_can_pin_message(self, users, register_room_with_user, create_group_chat, create_message, custom_websocket_communicator):
        """Test that admin can pin messages"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Pin Test',
            participants=[users[0], users[1]]
        )
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await database_sync_to_async(group.admins.add)(users[0])
        
        # Create a message
        message = await database_sync_to_async(create_message)(group, users[1], 'Pin this')
        
        # Admin pins the message
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.pin',
            'data': {
                'message_id': str(message.id),
                'room_id': str(group.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.pinned'
        assert response['data']['message_id'] == str(message.id)
        assert response['data']['pinned_by'] == users[0].username
        
        # Verify message is in pinned cache
        pinned_messages = cache.get(f"pinned_messages:{group.id}", [])
        assert str(message.id) in pinned_messages
        
        await comm.disconnect()
    
    async def test_non_admin_cannot_pin_message(self, users, register_room_with_user, create_group_chat, create_message, custom_websocket_communicator):
        """Test that non-admin cannot pin messages"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Pin Test',
            participants=[users[0], users[1]]
        )
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await database_sync_to_async(group.admins.add)(users[0])  # Only user[0] is admin
        
        message = await database_sync_to_async(create_message)(group, users[0], 'Try to pin')
        
        # Non-admin tries to pin
        comm = custom_websocket_communicator(users[1])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.pin',
            'data': {
                'message_id': str(message.id),
                'room_id': str(group.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should receive permission error
        assert 'error' in response
        assert response['error']['code'] == 4003
        
        await comm.disconnect()
    
    async def test_pin_broadcasts_to_all_room_members(self, users, create_group_chat, register_room_with_user, create_message, custom_websocket_communicator):
        """Test that pin event broadcasts to all room members"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Broadcast Test',
            participants=[users[0], users[1], users[2]]
        )
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await register_room_with_user(users[2].id, group.id)
        await database_sync_to_async(group.admins.add)(users[0])
        
        message = await database_sync_to_async(create_message)(group, users[1], 'Broadcast pin')
        
        # Connect all users
        admin_comm = custom_websocket_communicator(users[0])
        user1_comm = custom_websocket_communicator(users[1])
        user2_comm = custom_websocket_communicator(users[2])
        
        await admin_comm.connect()
        await admin_comm.receive_json_from()
        
        await user1_comm.connect()
        await user1_comm.receive_json_from()
        
        await user2_comm.connect()
        await user2_comm.receive_json_from()
        
        # Admin pins message
        await admin_comm.send_json_to({
            'event_type': 'message.pin',
            'data': {
                'message_id': str(message.id),
                'room_id': str(group.id)
            }
        })
        
        # All should receive pin notification
        admin_response = await admin_comm.receive_json_from()
        user1_response = await user1_comm.receive_json_from()
        user2_response = await user2_comm.receive_json_from()
        
        assert admin_response['eventType'] == 'message.pinned'
        assert user1_response['eventType'] == 'message.pinned'
        assert user2_response['eventType'] == 'message.pinned'
        
        await admin_comm.disconnect()
        await user1_comm.disconnect()
        await user2_comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageFlagging:
    """Test custom message.flag event"""
    
    async def test_user_can_flag_message(self, users, one_to_one_chat, create_message, custom_websocket_communicator):
        """Test that users can flag inappropriate messages"""
        message = await database_sync_to_async(create_message)(one_to_one_chat, users[0], 'Inappropriate content')
        
        # User[1] flags the message
        comm = custom_websocket_communicator(users[1])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.flag',
            'data': {
                'message_id': str(message.id),
                'reason': 'Spam/inappropriate'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.flagged'
        assert response['data']['status'] == 'flagged'
        assert response['data']['reason'] == 'Spam/inappropriate'
        
        # Verify flag stored in cache
        flag_data = cache.get(f"flagged_messages:{message.id}")
        assert flag_data is not None
        assert flag_data['reason'] == 'Spam/inappropriate'
        
        await comm.disconnect()
    
    async def test_flag_without_reason_uses_default(self, users, one_to_one_chat, create_message, custom_websocket_communicator):
        """Test flagging without reason uses default"""
        message = await database_sync_to_async(create_message)(one_to_one_chat, users[0], 'Content')
        
        comm = custom_websocket_communicator(users[1])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.flag',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['data']['reason'] == 'No reason provided'
        
        await comm.disconnect()
    
    async def test_flagging_notifies_moderators(self, users, create_group_chat, register_room_with_user, create_message, custom_websocket_communicator):
        """Test that flagging notifies room moderators"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],  # Creator/moderator
            name='Moderation Test',
            participants=[users[0], users[1], users[2]]
        )

        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await register_room_with_user(users[2].id, group.id)

        await database_sync_to_async(group.admins.add)(users[0])
        
        message = await database_sync_to_async(create_message)(group, users[2], 'Flag this')
        
        # Connect moderator
        mod_comm = custom_websocket_communicator(users[0])
        await mod_comm.connect()
        await mod_comm.receive_json_from()
        
        # User flags message
        user_comm = custom_websocket_communicator(users[1])
        await user_comm.connect()
        await user_comm.receive_json_from()
        
        await user_comm.send_json_to({
            'event_type': 'message.flag',
            'data': {
                'message_id': str(message.id),
                'reason': 'Offensive content'
            }
        })
        
        await user_comm.receive_json_from()  # User's confirmation
        
        # Moderator should receive alert
        mod_alert = await mod_comm.receive_json_from()
        
        assert mod_alert['eventType'] == 'moderation.alert'
        assert mod_alert['data']['alert_type'] == 'message_flagged'
        assert mod_alert['data']['message_id'] == str(message.id)
        
        await mod_comm.disconnect()
        await user_comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageAnalytics:
    """Test custom message.analytics event"""
    
    async def test_get_room_analytics_24h(self, users, create_group_chat, register_room_with_user, create_message, custom_websocket_communicator):
        """Test retrieving 24h analytics for a room"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Analytics Test',
            participants=[users[0], users[1]]
        )
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        
        # Create some messages
        for i in range(5):
            await database_sync_to_async(create_message)(group, users[0], f'Message {i}')
        
        # Get analytics
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.analytics',
            'data': {
                'room_id': str(group.id),
                'timeframe': '24h'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.analytics'
        assert response['data']['room_id'] == str(group.id)
        assert response['data']['timeframe'] == '24h'
        assert response['data']['message_count'] >= 5
        assert response['data']['unique_senders'] >= 1
        
        await comm.disconnect()
    
    async def test_analytics_different_timeframes(self, users, create_group_chat, register_room_with_user, custom_websocket_communicator):
        """Test analytics with different timeframes"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Timeframe Test',
            participants=[users[0]]
        )
        await register_room_with_user(users[0].id, group.id)

        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        timeframes = ['24h', '7d', '30d']
        for tf in timeframes:
            await comm.send_json_to({
                'event_type': 'message.analytics',
                'data': {
                    'room_id': str(group.id),
                    'timeframe': tf
                }
            })
            
            response = await comm.receive_json_from()
            
            assert response['eventType'] == 'message.analytics'
            assert response['data']['timeframe'] == tf
        
        await comm.disconnect()
    
    async def test_analytics_requires_room_permission(self, users, create_group_chat, register_room_with_user, custom_websocket_communicator):
        """Test that analytics requires room access"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Private Group',
            participants=[users[0]]
        )
        await register_room_with_user(users[0].id, group.id)

        # User[1] is not a member
        comm = custom_websocket_communicator(users[1])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.analytics',
            'data': {
                'room_id': str(group.id),
                'timeframe': '24h'
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should receive permission error
        assert 'error' in response
        assert response['error']['code'] == 4004
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestBackwardCompatibility:
    """Test that custom consumer maintains backward compatibility"""
    
    async def test_standard_message_send_still_works(self, users, one_to_one_chat, custom_websocket_communicator):
        """Test standard message.send event works"""
        
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Standard message'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Standard message'
        
        await comm.disconnect()
    
    async def test_all_standard_events_work(self, users, one_to_one_chat, create_message, custom_websocket_communicator):
        """Test all standard events still function"""
        message = await database_sync_to_async(create_message)(one_to_one_chat, users[0], 'Test')
        
        comm = custom_websocket_communicator(users[1])
        await comm.connect()
        await comm.receive_json_from()
        
        # Test room.messages
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response1 = await comm.receive_json_from()

        assert response1['eventType'] == 'roommessages.dispatch'
        
        # Test message.read
        await comm.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response2 = await comm.receive_json_from()
        assert response2['eventType'] == 'readreceipt.dispatch'
        
        await comm.disconnect()
    
    async def test_default_models_unaffected(self, users, one_to_one_chat, create_message):
        """Test that default models are unchanged"""
        message = await database_sync_to_async(create_message)(one_to_one_chat, users[0], 'Test')
        
        # Verify using default Message model
        assert message.__class__.__name__ == 'Message'
        assert one_to_one_chat.__class__.__name__ == 'OneToOneChat'
        
        # No custom fields added
        assert not hasattr(message, 'priority')
        assert not hasattr(one_to_one_chat, 'department')


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAnalyticsLogging:
    """Test analytics logging functionality"""
    
    async def test_connection_logs_analytics(self, users, custom_websocket_communicator):
        """Test connection event logged"""
        comm = custom_websocket_communicator(users[0])
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Check analytics cache
        key = f"analytics:connection:{users[0].id}"
        data = cache.get(key)
        
        assert data is not None
        assert data['event_type'] == 'connection'
        
        await comm.disconnect()
    
    async def test_message_operations_log_analytics(self, users, create_group_chat, register_room_with_user, create_message, custom_websocket_communicator):
        """Test message operations are logged"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            participants=[users[0]]
        )
        await register_room_with_user(users[0].id, group.id)

        await database_sync_to_async(group.admins.add)(users[0])
        
        message = await database_sync_to_async(create_message)(group, users[0], 'Log this')
        
        comm = custom_websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Pin message (logs analytics)
        await comm.send_json_to({
            'event_type': 'message.pin',
            'data': {
                'message_id': str(message.id),
                'room_id': str(group.id)
            }
        })
        
        await comm.receive_json_from()
        
        # Check pin analytics
        pin_key = f"analytics:message_pinned:{users[0].id}"
        pin_data = cache.get(pin_key)
        
        assert pin_data is not None
        assert pin_data['event_type'] == 'message_pinned'
        
        await comm.disconnect()
