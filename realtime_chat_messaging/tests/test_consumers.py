import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
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
    }


@pytest.fixture
async def communicator(users):
    """Create a WebSocket communicator"""
    communicator = WebsocketCommunicator(
        ChatMessagingConsumer.as_asgi(),
        "/messaging/"
    )
    communicator.scope['user'] = users['user1']
    return communicator


@pytest.fixture
def one_to_one_chat(users, db):
    """Create a one-to-one chat"""
    chat = OneToOneChat.objects.create()
    chat.participants.set([users['user1'], users['user2']])
    return chat


@pytest.fixture
def group_chat(users, db):
    """Create a group chat"""
    return GroupChat.objects.create(
        name="Test Group",
        description="A test group",
        creator=users['user1']
    )


@pytest.fixture
def channel_fixture(users, db):
    """Create a channel"""
    return Channel.objects.create(
        name="Test Channel",
        description="A test channel",
        creator=users['user1']
    )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketConnection:
    """Test WebSocket connection and disconnection"""

    async def test_authenticated_user_can_connect(self, users):
        """Test that authenticated user can connect"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        
        connected, _ = await communicator.connect()
        assert connected
        
        await communicator.disconnect()

    async def test_unauthenticated_user_cannot_connect(self):
        """Test that unauthenticated user cannot connect"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        
        # Mock anonymous user
        class AnonymousUser:
            id = None
            is_authenticated = False
        
        communicator.scope['user'] = AnonymousUser()
        
        connected, close_code = await communicator.connect()
        
        # Should close with custom code 4001
        assert not connected or close_code == 4001

    async def test_disconnect_cleanup(self, users):
        """Test that disconnect properly cleans up"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        
        await communicator.connect()
        await communicator.disconnect()
        
        # Verify cleanup happened (channel removed from groups)
        # This would require access to cache, so we just verify no errors

    async def test_chat_notifications_sent_on_connect(self, users, one_to_one_chat):
        """Test that notifications are dispatched on connection"""
        # Create a notification for the user
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user2'],
            content="Test message"
        )
        
        notification = await database_sync_to_async(ChatNotification.objects.create)(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        await database_sync_to_async(notification.recipients.add)(users['user1'])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        
        await communicator.connect()
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'chat.notifications'
        assert 'data' in response
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRoomCreation:
    """Test room creation events"""

    async def test_create_one_to_one_chat(self, users):
        """Test creating a one-to-one chat via WebSocket"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        # Send room creation event
        await communicator.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'OneToOneChat',
                'participants': [users['user2'].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['type'] == 'OneToOneChat'
        assert len(response['data']['participants']) == 2
        
        await communicator.disconnect()

    async def test_create_group_chat(self, users):
        """Test creating a group chat via WebSocket"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'GroupChat',
                'name': 'New Group',
                'description': 'Test group',
                'participants': [users['user2'].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['type'] == 'GroupChat'
        assert response['data']['name'] == 'New Group'
        
        await communicator.disconnect()

    async def test_create_channel(self, users):
        """Test creating a channel via WebSocket"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'Channel',
                'name': 'New Channel',
                'description': 'Test channel',
                'subscribers': [users['user2'].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['type'] == 'Channel'
        assert response['data']['name'] == 'New Channel'
        
        await communicator.disconnect()

    async def test_create_room_with_preferences(self, users):
        """Test creating room with custom preferences"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'GroupChat',
                'name': 'Pref Group',
                'extra_fields': {
                    'preferences': {'theme': 'dark'}
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['data']['preferences'] == {'theme': 'dark'}
        
        await communicator.disconnect()

    async def test_invalid_room_type_returns_error(self, users):
        """Test that invalid room type returns error"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'InvalidType',
                'name': 'Test'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4003
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageSending:
    """Test message sending events"""

    async def test_send_message_to_one_to_one_chat(self, users, one_to_one_chat):
        """Test sending a message to one-to-one chat"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Hello World'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Hello World'
        assert response['data']['sender']['username'] == 'user1'
        
        await communicator.disconnect()

    async def test_send_message_to_group_chat(self, users, group_chat):
        """Test sending message to group chat"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Group message'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Group message'
        
        await communicator.disconnect()

    async def test_send_message_with_media(self, users, one_to_one_chat):
        """Test sending message with media attachments"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Media message',
                'extra_fields': {
                    'media': [
                        {
                            'media_url': 'https://example.com/image.jpg',
                            'media_type': 'image',
                            'mime_type': 'image/jpeg',
                            'file_size': 1024,
                            'metadata': {}
                        }
                    ]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert len(response['data']['attachments']) == 1
        
        await communicator.disconnect()

    async def test_send_reply_message(self, users, one_to_one_chat):
        """Test sending a reply to a message"""
        # Create parent message
        parent_message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Parent message"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Reply message',
                'parent_message': str(parent_message.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['parent_message']['content'] == 'Parent message'
        
        await communicator.disconnect()

    async def test_send_forwarded_message(self, users, one_to_one_chat, group_chat):
        """Test forwarding a message"""
        # Create original message
        original_message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original message"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Original message',
                'extra_fields': {
                    'is_forwarded': True,
                    'forwarded_from_id': str(original_message.id)
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['is_forwarded'] is True
        
        await communicator.disconnect()

    async def test_unauthorized_user_cannot_send_message(self, users, one_to_one_chat):
        """Test that unauthorized user cannot send message to room"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        # user3 is not a participant
        communicator.scope['user'] = users['user3']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Unauthorized message'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002  # Permission denied
        
        await communicator.disconnect()

    async def test_send_message_to_locked_group_as_non_admin(self, users, group_chat):
        """Test that non-admin cannot send message to locked group"""
        # Lock the group
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        
        # Add user2 as participant but not admin
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_send_event',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Message to locked group'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageOperations:
    """Test message operations (edit, delete, reaction, read receipt)"""

    async def test_mark_message_as_read(self, users, one_to_one_chat):
        """Test marking message as read"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test message"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_read_event',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'readreceipt.dispatch'
        assert len(response['data']['read_receipts']) == 1
        
        await communicator.disconnect()

    async def test_mark_multiple_messages_as_read(self, users, one_to_one_chat):
        """Test marking multiple messages as read"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Message 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Message 2"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_read_event',
            'data': {
                'message_id': [str(message1.id), str(message2.id)]
            }
        })
        
        # Should receive response for each room
        response = await communicator.receive_json_from()
        assert response['eventType'] == 'readreceipt.dispatch'
        
        await communicator.disconnect()

    async def test_message_acknowledged(self, users, one_to_one_chat):
        """Test message acknowledgment (delivery)"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test message"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_acknowledged_event',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await communicator.receive_json_from()
        assert response['status'] == 'successful'
        
        await communicator.disconnect()

    async def test_add_reaction_to_message(self, users, one_to_one_chat):
        """Test adding reaction to message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test message"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_reaction_event',
            'data': {
                'type': 'add',
                'message_id': str(message.id),
                'reaction_content': '👍'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'reaction.dispatch'
        assert response['data']['status'] == 'successful'
        assert any(r['reaction_content'] == '👍' for r in response['data']['message']['reactions'])
        
        await communicator.disconnect()

    async def test_remove_reaction_from_message(self, users, one_to_one_chat):
        """Test removing reaction from message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test message"
        )
        
        # Add reaction first
        await database_sync_to_async(Reaction.objects.create)(
            message=message,
            user=users['user2'],
            reaction_content='👍'
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_reaction_event',
            'data': {
                'type': 'remove',
                'message_id': str(message.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'reaction.dispatch'
        assert response['data']['status'] == 'successful'
        assert response['data']['action'] == 'remove'
        
        await communicator.disconnect()

    async def test_edit_message(self, users, one_to_one_chat):
        """Test editing message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original content"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_modify_event',
            'data': {
                'action': 'update',
                'message_id': str(message.id),
                'extra_fields': {
                    'content': 'Edited content'
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['message']['content'] == 'Edited content'
        
        await communicator.disconnect()

    async def test_delete_message(self, users, one_to_one_chat):
        """Test deleting message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="To be deleted"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_modify_event',
            'data': {
                'action': 'delete',
                'message_id': [str(message.id)]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['action'] == 'delete'
        assert str(message.id) in response['data']['message_ids']
        
        await communicator.disconnect()

    async def test_non_sender_cannot_edit_message(self, users, one_to_one_chat):
        """Test that non-sender cannot edit message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original content"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_modify_event',
            'data': {
                'action': 'update',
                'message_id': str(message.id),
                'extra_fields': {'content': 'Edited'}
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_typing_indicator(self, users, one_to_one_chat):
        """Test typing indicator event"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_typing_event',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'messagetyping.dispatch'
        assert response['data']['username'] == 'user1'
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRoomOperations:
    """Test room operations (join, leave, fetch, etc.)"""

    async def test_fetch_rooms(self, users, one_to_one_chat, group_chat):
        """Test fetching user's rooms"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_get_rooms',
            'data': {}
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomlist.dispatch'
        assert len(response['data']) >= 2
        
        await communicator.disconnect()

    async def test_fetch_room_details(self, users, group_chat):
        """Test fetching specific room details"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_get_room_info',
            'data': {
                'room_id': str(group_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roominfo.dispatch'
        assert response['data']['name'] == 'Test Group'
        
        await communicator.disconnect()

    async def test_fetch_messages(self, users, one_to_one_chat):
        """Test fetching messages from room"""
        # Create some messages
        await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Message 1"
        )
        await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user2'],
            content="Message 2"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_list',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 2
        
        await communicator.disconnect()

    async def test_fetch_messages_with_pagination(self, users, one_to_one_chat):
        """Test fetching messages with pagination"""
        # Create multiple messages
        for i in range(10):
            await database_sync_to_async(Message.objects.create)(
                room=one_to_one_chat,
                sender=users['user1'],
                content=f"Message {i}"
            )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_message_list',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 1,
                    'size': 5
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 5
        assert response['data']['has_next'] is True
        await communicator.disconnect()

    async def test_join_public_channel(self, users, channel_fixture):
        """Test joining a public channel"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_join_room_event',
            'data': {
                'room_id': str(channel_fixture.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user2' in response['data']['new_members']
        
        await communicator.disconnect()

    async def test_cannot_join_private_channel(self, users, channel_fixture):
        """Test that cannot join private channel"""
        # Make channel private
        await database_sync_to_async(setattr)(channel_fixture, 'is_public', False)
        await database_sync_to_async(channel_fixture.save)()
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_join_room_event',
            'data': {
                'room_id': str(channel_fixture.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4003
        
        await communicator.disconnect()

    async def test_leave_room(self, users, group_chat):
        """Test leaving a room"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_leave_room_event',
            'data': {
                'room_id': str(group_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomexit.dispatch'
        assert 'You left' in response['data']['message']
        
        await communicator.disconnect()

    async def test_add_members_to_room(self, users, group_chat):
        """Test adding members to room"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_add_members_to_room',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users['user2'].id, users['user3'].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user2' in response['data']['new_members']
        assert 'user3' in response['data']['new_members']
        
        await communicator.disconnect()

    async def test_remove_members_from_room(self, users, group_chat):
        """Test removing members from room"""
        # Add user2 first
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_remove_members_from_room',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users['user2'].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomremovemembers.dispatch'
        assert 'user2' in response['data']['removed_members']
        
        await communicator.disconnect()

    async def test_non_admin_cannot_add_members(self, users, group_chat):
        """Test that non-admin cannot add members"""
        # Add user2 as participant but not admin
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user2']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_add_members_to_room',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users['user3'].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_modify_room_as_admin(self, users, group_chat):
        """Test modifying room as admin"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_modify_room_event',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'update',
                'data': {
                    'name': 'Updated Group Name'
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        assert response['data']['name'] == 'Updated Group Name'
        
        await communicator.disconnect()

    async def test_add_admin_to_group(self, users, group_chat):
        """Test adding admin to group"""
        # Add user2 as participant
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_modify_room_event',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'add_admin',
                'data': {
                    'users': [users['user2'].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        admin_usernames = [admin['username'] for admin in response['data']['admins']]
        assert 'user2' in admin_usernames
        
        await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestErrorHandling:
    """Test error handling in consumers"""
    async def test_invalid_event_type(self, users):
        """Test invalid event type returns error"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'invalid_event_type',
            'data': {}
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error'] == 'invalid event type'
        
        await communicator.disconnect()

    async def test_malformed_data_returns_error(self, users):
        """Test that malformed data returns appropriate error"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_room_create_event',
            'data': {
                'type': 'GroupChat'
                # Missing required 'name' field
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4003  # Validation error
        
        await communicator.disconnect()

    async def test_resource_not_found_error(self, users):
        """Test resource not found error"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users['user1']
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_get_room_info',
            'data': {
                'room_id': '00000000-0000-0000-0000-000000000000'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4004  # Resource not found
        
        await communicator.disconnect()