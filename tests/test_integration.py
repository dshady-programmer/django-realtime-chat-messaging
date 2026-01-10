import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.models import (
    OneToOneChat, GroupChat, Channel, Message,
    ReadReceipt, Reaction, ChatNotification
)

User = get_user_model()


@pytest.fixture
def users(db):
    """Create test users"""
    return {
        'user1': User.objects.create_user(username='user1', email='user1@test.com', password='pass123'),
        'user2': User.objects.create_user(username='user2', email='user2@test.com', password='pass123'),
        'user3': User.objects.create_user(username='user3', email='user3@test.com', password='pass123'),
        'user4': User.objects.create_user(username='user4', email='user4@test.com', password='pass123'),
    }


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEndToEndMessageFlow:
    """Test complete message flow from creation to delivery"""

    async def test_complete_message_lifecycle(self, users):
        """Test complete lifecycle: send, deliver, read, react"""
        # Create room
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users['user1'], users['user2']])
        
        # Connect user1
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        # Connect user2
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        # User1 sends message
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(chat.id),
                'content': 'Hello from user1'
            }
        })
        
        # Both users receive message
        msg1 = await comm1.receive_json_from()
        msg2 = await comm2.receive_json_from()
        
        assert msg1['eventType'] == 'message.dispatch'
        assert msg2['eventType'] == 'message.dispatch'
        
        message_id = msg1['data']['id']
        
        # User2 acknowledges message (delivered)
        await comm2.send_json_to({
            'event_type': 'receive_message_acknowledged_event',
            'data': {'message_id': message_id}
        })
        
        ack_response = await comm2.receive_json_from()
        assert ack_response['status'] == 'successful'
        
        # User2 reads message
        await comm2.send_json_to({
            'event_type': 'receive_message_read_event',
            'data': {'message_id': message_id}
        })
        
        # Both receive read receipt
        read1 = await comm1.receive_json_from()
        read2 = await comm2.receive_json_from()
        
        assert read1['eventType'] == 'readreceipt.dispatch'
        assert read2['eventType'] == 'readreceipt.dispatch'
        
        # User2 reacts to message
        await comm2.send_json_to({
            'event_type': 'receive_message_reaction_event',
            'data': {
                'type': 'add',
                'message_id': message_id,
                'reaction_content': '👍'
            }
        })
        
        # Both receive reaction
        react1 = await comm1.receive_json_from()
        react2 = await comm2.receive_json_from()
        
        assert react1['eventType'] == 'reaction.dispatch'
        assert react2['eventType'] == 'reaction.dispatch'
        
        await comm1.disconnect()
        await comm2.disconnect()

    async def test_group_chat_complete_flow(self, users):
        """Test complete group chat flow with multiple users"""
        # User1 creates group
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        await comm1.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'GroupChat',
                'name': 'Integration Test Group',
                'description': 'Test group',
                'participants': [users['user2'].id, users['user3'].id]
            }
        })
        
        room_response = await comm1.receive_json_from()
        room_id = room_response['data']['id']
        
        # Connect other users
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        comm3 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm3.scope['user'] = users['user3']
        await comm3.connect()
        
        # User2 and User3 also receive room creation event
        await comm2.receive_json_from()
        await comm3.receive_json_from()
        
        # User1 sends message
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': room_id,
                'content': 'Hello group!'
            }
        })
        
        # All three receive message
        msg1 = await comm1.receive_json_from()
        msg2 = await comm2.receive_json_from()
        msg3 = await comm3.receive_json_from()
        
        assert all(m['eventType'] == 'message.dispatch' for m in [msg1, msg2, msg3])
        assert all(m['data']['content'] == 'Hello group!' for m in [msg1, msg2, msg3])
        
        # User1 adds user4 to group
        await comm1.send_json_to({
            'event_type': 'receive_add_members_to_room',
            'data': {
                'room_id': room_id,
                'members': [users['user4'].id]
            }
        })
        
        # All receive add member event
        for comm in [comm1, comm2, comm3]:
            response = await comm.receive_json_from()
            assert response['eventType'] == 'roomaddmembers.dispatch'
            assert 'user4' in response['data']['new_members']
        
        await comm1.disconnect()
        await comm2.disconnect()
        await comm3.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestNotificationFlow:
    """Test notification creation and management flow"""

    async def test_notification_created_on_message_send(self, users):
        """Test that notification is created when message is sent"""
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users['user1'], users['user2']])
        
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(chat.id),
                'content': 'Test notification'
            }
        })
        
        response = await comm1.receive_json_from()
        
        # Check notification was created
        notification_exists = await database_sync_to_async(
            lambda: ChatNotification.objects.filter(
                message__id=response['data']['id']
            ).exists()
        )()
        
        assert notification_exists
        
        await comm1.disconnect()

    async def test_notification_dispatched_on_connect(self, users):
        """Test that notifications are dispatched when user connects"""
        # Create message and notification before connecting
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users['user1'], users['user2']])
        
        message = await database_sync_to_async(Message.objects.create)(
            room=chat,
            sender=users['user1'],
            content="Notification test"
        )
        
        notification = await database_sync_to_async(ChatNotification.objects.create)(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        await database_sync_to_async(notification.recipients.add)(users['user2'])
        
        # Connect user2
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        # Should receive notifications immediately
        response = await comm2.receive_json_from()
        
        assert response['eventType'] == 'chat.notifications'
        assert str(chat.id) in response['data']
        
        await comm2.disconnect()

    async def test_notification_removed_on_read(self, users):
        """Test that notification recipient is removed when message is read"""
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users['user1'], users['user2']])
        
        message = await database_sync_to_async(Message.objects.create)(
            room=chat,
            sender=users['user1'],
            content="Test"
        )
        
        notification = await database_sync_to_async(ChatNotification.objects.create)(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        await database_sync_to_async(notification.recipients.add)(users['user2'])
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        # Skip initial notification dispatch
        await comm2.receive_json_from()
        
        # Mark as read
        await comm2.send_json_to({
            'event_type': 'receive_message_read_event',
            'data': {'message_id': str(message.id)}
        })
        
        await comm2.receive_json_from()
        
        # Check notification was deleted (no more recipients)
        notification_exists = await database_sync_to_async(
            lambda: ChatNotification.objects.filter(id=notification.id).exists()
        )()
        
        assert not notification_exists
        
        await comm2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChannelPermissions:
    """Test channel permission enforcement in real scenarios"""

    async def test_non_moderator_cannot_send_to_channel(self, users):
        """Test that non-moderator cannot send message to channel"""
        channel = await database_sync_to_async(Channel.objects.create)(
            name="Test Channel",
            creator=users['user1']
        )
        
        # Add user2 as subscriber but not moderator
        await database_sync_to_async(channel.subscribers.add)(users['user2'])
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        await comm2.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(channel.id),
                'content': 'Unauthorized message'
            }
        })
        
        response = await comm2.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await comm2.disconnect()

    async def test_moderator_can_send_to_channel(self, users):
        """Test that moderator can send message to channel"""
        channel = await database_sync_to_async(Channel.objects.create)(
            name="Test Channel",
            creator=users['user1']
        )
        
        # Add user2 as subscriber and moderator
        await database_sync_to_async(channel.subscribers.add)(users['user2'])
        await database_sync_to_async(channel.moderators.add)(users['user2'])
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        await comm2.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(channel.id),
                'content': 'Moderator message'
            }
        })
        
        response = await comm2.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Moderator message'
        
        await comm2.disconnect()

    async def test_permission_changes_take_effect_immediately(self, users):
        """Test that permission changes are reflected immediately"""
        channel = await database_sync_to_async(Channel.objects.create)(
            name="Test Channel",
            creator=users['user1']
        )
        
        await database_sync_to_async(channel.subscribers.add)(users['user2'])
        await database_sync_to_async(channel.moderators.add)(users['user2'])
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        # Can send message as moderator
        await comm2.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(channel.id),
                'content': 'Message 1'
            }
        })
        
        response1 = await comm2.receive_json_from()
        assert response1['eventType'] == 'message.dispatch'
        
        # Remove moderator status
        await database_sync_to_async(channel.moderators.remove)(users['user2'])
        
        # Try to send message (should fail)
        await comm2.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(channel.id),
                'content': 'Message 2'
            }
        })
        
        response2 = await comm2.receive_json_from()
        assert 'error' in response2
        
        await comm2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestGroupChatPermissions:
    """Test group chat permission enforcement"""

    async def test_locked_group_admin_can_send(self, users):
        """Test that admin can send to locked group"""
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Locked Group",
            creator=users['user1'],
            group_locked=True
        )
        
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(group.id),
                'content': 'Admin message'
            }
        })
        
        response = await comm1.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        
        await comm1.disconnect()

    async def test_locked_group_regular_user_cannot_send(self, users):
        """Test that regular user cannot send to locked group"""
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Locked Group",
            creator=users['user1'],
            group_locked=True
        )
        
        await database_sync_to_async(group.participants.add)(users['user2'])
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        await comm2.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(group.id),
                'content': 'Regular user message'
            }
        })
        
        response = await comm2.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await comm2.disconnect()

    async def test_admin_can_add_members(self, users):
        """Test that admin can add members to group"""
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Test Group",
            creator=users['user1']
        )
        
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        await comm1.send_json_to({
            'event_type': 'receive_add_members_to_room',
            'data': {
                'room_id': str(group.id),
                'members': [users['user2'].id]
            }
        })
        
        response = await comm1.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        
        await comm1.disconnect()

    async def test_non_admin_cannot_add_members(self, users):
        """Test that non-admin cannot add members"""
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Test Group",
            creator=users['user1']
        )
        
        await database_sync_to_async(group.participants.add)(users['user2'])
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        await comm2.send_json_to({
            'event_type': 'receive_add_members_to_room',
            'data': {
                'room_id': str(group.id),
                'members': [users['user3'].id]
            }
        })
        
        response = await comm2.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await comm2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageForwardingAndReplies:
    """Test message forwarding and reply functionality"""

    async def test_forward_message_between_rooms(self, users):
        """Test forwarding message from one room to another"""
        # Create two chats
        chat1 = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat1.participants.set)([users['user1'], users['user2']])
        
        chat2 = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat2.participants.set)([users['user1'], users['user3']])
        
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        # Send original message in chat1
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(chat1.id),
                'content': 'Original message'
            }
        })
        
        original_response = await comm1.receive_json_from()
        original_message_id = original_response['data']['id']
        
        # Forward to chat2
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(chat2.id),
                'content': 'Original message',
                'extra_fields': {
                    'is_forwarded': True,
                    'forwarded_from_id': original_message_id
                }
            }
        })
        
        forward_response = await comm1.receive_json_from()
        
        assert forward_response['eventType'] == 'message.dispatch'
        assert forward_response['data']['is_forwarded'] is True
        
        await comm1.disconnect()

    async def test_reply_to_message(self, users):
        """Test replying to a message"""
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users['user1'], users['user2']])
        
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        # User1 sends original message
        await comm1.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(chat.id),
                'content': 'Original message'
            }
        })
        
        original = await comm1.receive_json_from()
        await comm2.receive_json_from()  # user2 also receives
        
        # User2 replies
        await comm2.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(chat.id),
                'content': 'Reply message',
                'parent_message': original['data']['id']
            }
        })
        
        reply1 = await comm1.receive_json_from()
        reply2 = await comm2.receive_json_from()
        
        assert reply1['data']['parent_message']['content'] == 'Original message'
        assert reply2['data']['parent_message']['content'] == 'Original message'
        
        await comm1.disconnect()
        await comm2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestConcurrencyAndRaceConditions:
    """Test concurrent operations and race conditions"""

    async def test_concurrent_message_sends(self, users):
        """Test multiple users sending messages concurrently"""
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Concurrent Test",
            creator=users['user1']
        )
        
        await database_sync_to_async(group.participants.add)(users['user2'], users['user3'])
        
        comms = []
        for user in [users['user1'], users['user2'], users['user3']]:
            comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            comm.scope['user'] = user
            await comm.connect()
            comms.append(comm)
        
        # All users send messages simultaneously
        for i, comm in enumerate(comms):
            await comm.send_json_to({
                'event_type': 'receive_message_send_event',
                'data': {
                    'room_id': str(group.id),
                    'content': f'Message from user{i+1}'
                }
            })
        
        # Each user should receive all 3 messages
        for comm in comms:
            messages = []
            for _ in range(3):
                response = await comm.receive_json_from()
                messages.append(response['data']['content'])
            
            assert len(messages) == 3
            assert 'Message from user1' in messages
            assert 'Message from user2' in messages
            assert 'Message from user3' in messages
        
        for comm in comms:
            await comm.disconnect()

    async def test_concurrent_reaction_updates(self, users):
        """Test multiple users reacting to same message"""
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users['user1'], users['user2']])
        
        # Create message
        message = await database_sync_to_async(Message.objects.create)(
            room=chat,
            sender=users['user1'],
            content="React to this"
        )
        
        comm1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm1.scope['user'] = users['user1']
        await comm1.connect()
        
        comm2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm2.scope['user'] = users['user2']
        await comm2.connect()
        
        # Both users react simultaneously
        await comm1.send_json_to({
            'event_type': 'receive_message_reaction_event',
            'data': {
                'type': 'add',
                'message_id': str(message.id),
                'reaction_content': '👍'
            }
        })
        
        await comm2.send_json_to({
            'event_type': 'receive_message_reaction_event',
            'data': {
                'type': 'add',
                'message_id': str(message.id),
                'reaction_content': '❤️'
            }
        })
        
        # Collect all responses
        responses = []
        for _ in range(4):  # Each user gets 2 reactions
            try:
                responses.append(await comm1.receive_json_from())
                responses.append(await comm2.receive_json_from())
            except:
                break
        
        # Verify both reactions exist
        reaction_count = await database_sync_to_async(
            lambda: Reaction.objects.filter(message=message).count()
        )()
        
        assert reaction_count == 2
        
        await comm1.disconnect()
        await comm2.disconnect()