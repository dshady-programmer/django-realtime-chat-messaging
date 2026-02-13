"""
Integration tests for Scenario 1: Custom Message Only

Tests that overriding only the Message model works correctly while
all other models remain default.

Key test areas:
- Custom message fields (priority, metadata, is_pinned, expiry_date)
- Custom message works with default Room models
- WebSocket consumer integration
- Serialization with custom fields
- Backward compatibility
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.utils import timezone
import datetime
from custom_message_app.models import CustomMessage
from realtime_chat_messaging.models import OneToOneChat, GroupChat, Channel
from realtime_chat_messaging.consumers import ChatMessagingConsumer

User = get_user_model()


@pytest.mark.django_db
class TestCustomMessageModel:
    """Test CustomMessage model functionality"""
    
    def test_custom_message_has_priority_field(self, users, create_one_to_one_chat, create_custom_message):
        """Test that CustomMessage has priority field"""
        chat = create_one_to_one_chat(users[0], users[1])
        message = create_custom_message(chat, users[0], priority='urgent')
        
        assert message.priority == 'urgent'
        assert hasattr(message, 'priority')
    
    def test_custom_message_has_metadata_field(self, users, create_one_to_one_chat, create_custom_message):
        """Test that CustomMessage has metadata field"""
        chat = create_one_to_one_chat(users[0], users[1])
        metadata = {'category': 'announcement', 'tags': ['important']}
        message = create_custom_message(chat, users[0], metadata=metadata)
        
        assert message.metadata == metadata
        assert message.metadata['category'] == 'announcement'
    
    def test_custom_message_is_pinned_field(self, users, create_one_to_one_chat, create_custom_message):
        """Test that CustomMessage has is_pinned field"""
        chat = create_one_to_one_chat(users[0], users[1])
        message = create_custom_message(chat, users[0], is_pinned=True)
        
        assert message.is_pinned is True
    
    def test_custom_message_expiry_date(self, users, create_one_to_one_chat, create_custom_message):
        """Test that CustomMessage has expiry_date field"""
        chat = create_one_to_one_chat(users[0], users[1])
        expiry = timezone.now() + datetime.timedelta(days=7)
        message = create_custom_message(chat, users[0], expiry_date=expiry)
        
        assert message.expiry_date == expiry
        assert message.is_expired is False
    
    def test_is_high_priority_property(self, users, create_one_to_one_chat, create_custom_message):
        """Test is_high_priority property"""
        chat = create_one_to_one_chat(users[0], users[1])
        
        normal_msg = create_custom_message(chat, users[0], priority='normal')
        high_msg = create_custom_message(chat, users[0], priority='high')
        urgent_msg = create_custom_message(chat, users[0], priority='urgent')
        
        assert normal_msg.is_high_priority is False
        assert high_msg.is_high_priority is True
        assert urgent_msg.is_high_priority is True
    
    def test_is_expired_property(self, users, create_one_to_one_chat, create_custom_message):
        """Test is_expired property"""
        chat = create_one_to_one_chat(users[0], users[1])
        
        # Future expiry
        future = timezone.now() + datetime.timedelta(days=1)
        future_msg = create_custom_message(chat, users[0], expiry_date=future)
        assert future_msg.is_expired is False
        
        # Past expiry
        past = timezone.now() - datetime.timedelta(days=1)
        past_msg = create_custom_message(chat, users[0], expiry_date=past)
        assert past_msg.is_expired is True
        
        # No expiry
        no_expiry_msg = create_custom_message(chat, users[0])
        assert no_expiry_msg.is_expired is False
    
    def test_custom_message_ordering(self, users, create_one_to_one_chat, create_custom_message):
        """Test that messages are ordered by priority then created_at"""
        chat = create_one_to_one_chat(users[0], users[1])
        
        # Create messages in different priority order
        msg1 = create_custom_message(chat, users[0], content='Low priority', priority='low')
        msg2 = create_custom_message(chat, users[0], content='Urgent', priority='urgent')
        msg3 = create_custom_message(chat, users[0], content='Normal', priority='normal')
        
        # Query should return highest priority first
        messages = list(CustomMessage.objects.filter(room=chat))
        
        # Urgent should be first
        assert messages[0].priority == 'urgent'


@pytest.mark.django_db
class TestCustomMessageWithDefaultRooms:
    """Test that CustomMessage works with default Room models"""
    
    def test_custom_message_in_one_to_one_chat(self, users, create_one_to_one_chat, create_custom_message):
        """Test CustomMessage in default OneToOneChat"""
        chat = create_one_to_one_chat(users[0], users[1])
        message = create_custom_message(
            chat, users[0],
            content='Test in OneToOne',
            priority='high',
            metadata={'type': 'test'}
        )
        
        assert message.room == chat
        assert isinstance(message.room, OneToOneChat)
        assert message.priority == 'high'
    
    def test_custom_message_in_group_chat(self, users, create_group_chat, create_custom_message):
        """Test CustomMessage in default GroupChat"""
        group = create_group_chat(users[0], participants=[users[0], users[1], users[2]])
        message = create_custom_message(
            group, users[0],
            content='Test in Group',
            priority='urgent'
        )
        
        assert message.room == group
        assert isinstance(message.room, GroupChat)
        assert message.priority == 'urgent'
    
    def test_custom_message_in_channel(self, users, db):
        """Test CustomMessage in default Channel"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=users[0]
        )
        channel.subscribers.add(users[0])
        
        message = CustomMessage.objects.create(
            room=channel,
            sender=users[0],
            content='Test in Channel',
            priority='critical'
        )
        
        assert message.room == channel
        assert isinstance(message.room, Channel)
        assert message.priority == 'critical'


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketIntegration:
    """Test WebSocket consumer integration with CustomMessage"""
    
    async def test_send_message_with_priority(self, users, one_to_one_chat, websocket_communicator):
        """Test sending message with priority via WebSocket"""
        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Send message with priority
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'High priority message',
                'extra_fields': {
                    'priority': 'high'
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'High priority message'
        
        # Verify in database
        message = await database_sync_to_async(
            CustomMessage.objects.filter(content='High priority message').first
        )()
        
        assert message is not None
        assert message.priority == 'high'
        
        await comm.disconnect()
    
    async def test_send_message_with_metadata(self, users, one_to_one_chat, websocket_communicator):
        """Test sending message with metadata via WebSocket"""
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        metadata = {
            'category': 'announcement',
            'tags': ['urgent', 'action-required'],
            'custom_id': 'ABC123'
        }
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Message with metadata',
                'extra_fields': {
                    'priority': 'urgent',
                    'metadata': metadata
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        
        # Verify in database
        message = await database_sync_to_async(
            CustomMessage.objects.filter(content='Message with metadata').first
        )()
        
        assert message is not None
        assert message.metadata == metadata
        assert message.metadata['category'] == 'announcement'
        
        await comm.disconnect()
    
    async def test_send_pinned_message(self, users, one_to_one_chat, websocket_communicator):
        """Test sending pinned message"""
        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Pinned message',
                'extra_fields': {
                    'is_pinned': True,
                    'priority': 'high'
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        
        # Verify in database
        message = await database_sync_to_async(
            CustomMessage.objects.filter(content='Pinned message').first
        )()
        
        assert message is not None
        assert message.is_pinned is True
        
        await comm.disconnect()
    
    async def test_edit_message_priority(self, users, one_to_one_chat, create_custom_message, websocket_communicator):
        """Test editing message priority"""
        message = await database_sync_to_async(create_custom_message)(
            one_to_one_chat, users[0], content='Original', priority='normal'
        )
        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Edit priority
        await comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': str(message.id),
                'extra_fields': {
                    'priority': 'urgent'
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'messagemodification.dispatch'
        
        # Verify in database
        await database_sync_to_async(message.refresh_from_db)()
        assert message.priority == 'urgent'
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestCustomMessageSerialization:
    """Test serialization of CustomMessage"""
    
    async def test_message_list_includes_custom_fields(self, users, one_to_one_chat, create_custom_message, websocket_communicator):
        """Test that room.messages includes custom fields"""   
        # Create messages with different priorities
        await database_sync_to_async(create_custom_message)(
            one_to_one_chat, users[0], content='Low', priority='low'
        )
        await database_sync_to_async(create_custom_message)(
            one_to_one_chat, users[0], content='High', priority='high'
        )
        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Get messages
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        messages = response['data']['data']['messages']
        
        assert len(messages) == 2
        # Check that priority field is included
        for msg in messages:
            assert 'priority' in msg
        
        await comm.disconnect()
    
    async def test_serialized_message_has_custom_properties(self, users, one_to_one_chat, websocket_communicator):
        """Test that serialized messages include custom properties"""
        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Send high priority message
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Test',
                'extra_fields': {
                    'priority': 'urgent',
                    'metadata': {'test': True}
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        message_data = response['data']
        
        # Should include custom fields
        assert 'priority' in message_data
        assert message_data['priority'] == 'urgent'
        assert 'metadata' in message_data
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestBackwardCompatibility:
    """Test backward compatibility with default models"""
    
    async def test_messages_without_priority_use_default(self, users, one_to_one_chat, websocket_communicator):
        """Test that messages without priority get default value"""
                
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Send message without priority
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'No priority specified'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        
        # Verify default priority
        message = await database_sync_to_async(
            CustomMessage.objects.filter(content='No priority specified').first
        )()
        
        assert message.priority == 'normal'  # Default
        
        await comm.disconnect()
    
    async def test_room_operations_work_normally(self, users, websocket_communicator):
        """Test that room operations work normally with CustomMessage"""
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Create room
        await comm.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Test Group',
                'participants': [users[1].id]
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        
        room_id = response['data']['id']
        
        # Send message
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Test message',
                'extra_fields': {
                    'priority': 'high'
                }
            }
        })
        
        msg_response = await comm.receive_json_from()
        
        assert msg_response['eventType'] == 'message.dispatch'
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.slow
class TestPerformanceWithCustomMessage:
    """Test performance with CustomMessage"""
    
    async def test_bulk_message_creation(self, users, one_to_one_chat, websocket_communicator):
        """Test creating many messages with custom fields"""
        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        # Send 50 messages
        for i in range(50):
            priority = ['low', 'normal', 'high'][i % 3]
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Message {i}',
                    'extra_fields': {
                        'priority': priority,
                        'metadata': {'index': i}
                    }
                }
            })
            
            response = await comm.receive_json_from()
            assert response['eventType'] == 'message.dispatch'
        
        # Verify all created
        count = await database_sync_to_async(
            lambda: CustomMessage.objects.filter(room=one_to_one_chat).count()
        )()
        
        assert count == 50
        
        await comm.disconnect()
    
    async def test_query_by_priority(self, users, one_to_one_chat, message_factory):
        """Test querying messages by priority"""
        
        # Create messages with different priorities
        await database_sync_to_async(message_factory)(
            one_to_one_chat, users[0], count=10, priority='low'
        )
        await database_sync_to_async(message_factory)(
            one_to_one_chat, users[0], count=5, priority='high'
        )
        
        # Query high priority
        high_priority = await database_sync_to_async(
            lambda: list(CustomMessage.objects.filter(room=one_to_one_chat, priority='high'))
        )()
        
        assert len(high_priority) == 5
        assert all(msg.priority == 'high' for msg in high_priority)
