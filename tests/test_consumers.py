import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.utils.cache_utils import add_group_to_user_groups
from realtime_chat_messaging.consumers import GROUP_STRING, USER_OWN_GROUP
from realtime_chat_messaging.models import (
    OneToOneChat, GroupChat, Channel, Message,
    ReadReceipt, Reaction, ChatNotification
)
from asgiref.sync import async_to_sync
import pytest_asyncio

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create 10 test users"""
    users =  create_users(10)
    return users



@pytest_asyncio.fixture
async def communicator(websocket_communicator, users):
    """Create a WebSocket communicator"""
    return await websocket_communicator(users[0])
     


@pytest.fixture
def register_room_with_user():
    async def _register_room(user_id, room_id):
        group = GROUP_STRING.format(group_id=room_id)
        await add_group_to_user_groups(user_id, group)
    return _register_room
    

@pytest.fixture
def one_to_one_chat(users, register_room_with_user, create_one_to_one_chat):
    """Create a one-to-one chat"""
    room = create_one_to_one_chat(users[0], users[1])
    async_to_sync(register_room_with_user)(users[0].id, room.id)
    async_to_sync(register_room_with_user)(users[1].id, room.id)
    return room



@pytest.fixture
def group_chat(users, register_room_with_user, create_group_chat):
    """Create a group chat"""

    room = create_group_chat(users[0], "Test Group", description="A test group")
    async_to_sync(register_room_with_user)(users[0].id, room.id)
    return room
    

@pytest.fixture
def channel(users, register_room_with_user, create_channel):
    """Create a channel"""
    room = create_channel(users[0], "Test Channel", description="A test channel", is_public=True)

    async_to_sync(register_room_with_user)(users[0].id, room.id)
    return room


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketConnection:
    """Test WebSocket connection and disconnection"""

    async def test_authenticated_user_can_connect(self, communicator):
        """Test that authenticated user can connect"""
        connected, _ = await communicator.connect()
        assert connected
        
        await communicator.disconnect()

    async def test_unauthenticated_user_cannot_connect(self, communicator):
        """Test that unauthenticated user cannot connect"""

        
        # Mock anonymous user
        class AnonymousUser:
            id = None
            is_authenticated = False
        
        communicator.scope['user'] = AnonymousUser()
        
        connected, close_code = await communicator.connect()
        
        # Should close with custom code 4001
        assert not connected and close_code == 4001

    async def test_disconnect_cleanup(self, communicator):
        """Test that disconnect properly cleans up"""
        await communicator.connect()
        await communicator.disconnect()
        
        # Verify cleanup happened (channel removed from groups)
        # This would require access to cache, so we just verify no errors

    async def test_chat_notifications_sent_on_connect(self, users, one_to_one_chat):
        """Test that notifications are dispatched on connection"""
        # Create a notification for the user
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[1],
            content="Test message"
        )
        
        notification = await database_sync_to_async(ChatNotification.objects.create)(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        await database_sync_to_async(notification.recipients.add)(users[0])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        
        await communicator.connect()
        
        response = await communicator.receive_json_from()
        # print(response)
        assert response['eventType'] == 'chat.notifications'
        assert 'data' in response
        
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRoomCreation:
    """Test room creation events"""

    async def test_create_one_to_one_chat(self, communicator, users):
        """Test creating a one-to-one chat via WebSocket"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        # Send room creation event
        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'OneToOneChat',
                'participants': [users[1].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['type'] == 'OneToOneChat'
        assert len(response['data']['participants']) == 2
        
        await communicator.disconnect()

    async def test_create_one_to_one_chat_with_more_than_2_participants(self, communicator, users):
        """Test creating a one-to-one chat via WebSocket with more than 2 participants"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        # Send room creation event
        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'OneToOneChat',
                'participants': [users[1].id, users[2].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'eventType' not in response
        assert 'error' in response
        assert 'A one to one chat can only have 2 participants' in str(response['error']['detail'])
        
        await communicator.disconnect()

    async def test_create_group_chat(self, communicator,  users):
        """Test creating a group chat via WebSocket"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'New Group',
                'description': 'Test group',
                'participants': [u.id for u in users[1:8]]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['type'] == 'GroupChat'
        assert response['data']['name'] == 'New Group'
        assert len(response['data']['participants']) == 8
        
        await communicator.disconnect()

    async def test_create_group_chat_with_extra_fields(self, communicator, users):
        "Test creating a groupchat with extra args via WebSocket"
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'New Group',
                'description': 'Test group',
                'participants': [u.id for u in users[1:8]],
                'extra_fields': {
                    'max_participants': 10,
                    'join_approval_required': True,
                    'group_locked': True
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['max_participants'] == 10
        assert response['data']['join_approval_required'] == True
        assert response['data']['group_locked'] == True
        await communicator.disconnect()

    async def test_create_groupchat_with_max_participants_enforcement(self, communicator, users):
        "Test creating a groupchat will enforce max_participants if provided"
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'New GroupChat',
                'description': 'Test groupchat',
                'participants': [u.id for u in users[1:8]],
                'extra_fields': {

                    'max_participants': 5
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert 'Maximum number of group participants exceeded' in str(response['error']['detail'])
        await communicator.disconnect()


    async def test_create_channel(self, communicator, users):
        """Test creating a channel via WebSocket"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'Channel',
                'name': 'New Channel',
                'description': 'Test channel',
                'subscribers': [u.id for u in users[1:8]]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['type'] == 'Channel'
        assert response['data']['name'] == 'New Channel'
        assert len(response['data']['subscribers']) == 8
        
        await communicator.disconnect()
    
    async def test_create_channel_with_extra_fields(self, communicator, users):
        "Test creating a channel with extra args via WebSocket"
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'Channel',
                'name': 'New Channel',
                'description': 'Test channel',
                'participants': [u.id for u in users[1:8]],
                'extra_fields': {
                    'is_public': True,
                    'max_subscribers': 10
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['is_public'] == True
        assert response['data']['max_subscribers'] == 10
        await communicator.disconnect()

    async def test_create_channel_with_max_sub_enforcement(self, communicator, users):
        "Test creating a channel will enforce max_subscribers if provided"
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'Channel',
                'name': 'New Channel',
                'description': 'Test channel',
                'subscribers': [u.id for u in users[1:8]],
                'extra_fields': {

                    'max_subscribers': 5
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert 'Maximum number of channel subscribers exceeded' in str(response['error']['detail'])
        await communicator.disconnect()


    async def test_create_room_with_preferences(self, communicator, users):
        """Test creating room with custom preferences"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
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
        assert len(response['data']['participants']) == 1

        
        await communicator.disconnect()

    async def test_invalid_room_type_returns_error(self, communicator, users):
        """Test that invalid room type returns error"""
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'InvalidType',
                'name': 'Test'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4003
        
        await communicator.disconnect()

    async def test_create_room_dispatches_event_to_members(self, communicator, users):
        """
        test room create event propagates to all members of the group.
        """
        communicator1= WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator1.scope['user'] = users[3]


        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'New Group',
                'description': 'Test group',
                'participants': [u.id for u in users[1:8]]
            }
        })
        response1 = await communicator.receive_json_from()
        response2 = await communicator1.receive_json_from()

        assert response1['eventType'] == 'roomcreate.dispatch'
        assert response2['eventType'] == 'roomcreate.dispatch'
        assert response1['data']['type'] == response2['data']['type'] 
        await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageSending:
    """Test message sending events"""

    async def test_send_message_to_one_to_one_chat(self, communicator, users, one_to_one_chat):
        """Test sending a message to one-to-one chat"""
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Hello World'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Hello World'
        assert response['data']['sender']['username'] == 'user0'
        
        await communicator.disconnect()

    async def test_send_message_to_group_chat(self, communicator, users, group_chat):
        """Test sending message to group chat"""
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()       
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Group message'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Group message'
        
        await communicator.disconnect()

    async def test_send_message_with_media(self, communicator, users, one_to_one_chat):
        """Test sending message with media attachments"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
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

    async def test_send_reply_message(self, communicator, users, one_to_one_chat):
        """Test sending a reply to a message"""
        # Create parent message
        parent_message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Parent message"
        )
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Reply message',
                'extra_fields': {
                    'parent_message_id': str(parent_message.id)
                }
            }
        })
        
        response = await communicator.receive_json_from()

        assert response['eventType'] == 'message.dispatch'
        assert response['data']['parent_message']['content'] == 'Parent message'
        
        await communicator.disconnect()

    async def test_send_forwarded_message(self, users, communicator, one_to_one_chat, group_chat):
        """Test forwarding a message"""
        # Create original message
        original_message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original message"
        )
        
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Original message',
                'extra_fields': {
                    'forwarded_from_id': str(original_message.id)
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['is_forwarded'] is True
        assert response['data']['content'] == original_message.content
        
        await communicator.disconnect()

    async def test_unauthorized_user_cannot_send_message(self, communicator, users, one_to_one_chat):
        """Test that unauthorized user cannot send message to room"""
        # user3 is not a participant
        communicator.scope['user'] = users[2]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Unauthorized message'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002  # Permission denied
        
        await communicator.disconnect()

    async def test_send_message_to_locked_group_as_non_admin(self, communicator, users, group_chat):
        """Test that non-admin cannot send message to locked group"""
        # Lock the group
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        
        # Add user2 as participant but not admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Message to locked group'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_send_message_to_locked_group_as_admin(self, communicator, register_room_with_user, users, group_chat):
        """Test that admin can send message to locked group"""
        # Lock the group
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        # Add user2 as participant 
        await database_sync_to_async(group_chat.participants.add)(users[1])
        # add to admins
        await database_sync_to_async(group_chat.admins.add)(users[1])
        await register_room_with_user(users[1].id, group_chat.id)

        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Message to locked group'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Message to locked group'
        
        await communicator.disconnect()

    async def test_send_message_to_channel_not_a_subscriber(self, communicator, users, channel):
        """Test that non-subscribers cannot send message to channel"""

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(channel.id),
                'content': 'Message to channel but i\'m not a sub'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_send_message_to_channel_a_subscriber_no_perm(self, communicator, users, channel):
        """Test that subscribers with no permisson to send message to channel"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(channel.id),
                'content': 'Message to channel but i\'m a sub but no perm to send message'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_send_message_to_channel_a_subscriber_not_mod_but_has_perm(self, register_room_with_user,  communicator, users, channel):
        """Test that subscribers that are not mods but with permisson can send message to channel"""
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(assign_perm)("can_send_messages", users[1], channel)
        await register_room_with_user(users[1].id, channel.id)
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()        
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(channel.id),
                'content': 'Message to channel i\'m a sub not a mod but has perm to send message'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Message to channel i\'m a sub not a mod but has perm to send message'
        
        await communicator.disconnect()


    async def test_send_message_with_invalid_room_id(self, communicator, users, group_chat):
        """ Test message sending to a room that doesn't exist """
        communicator.scope['user'] = users[0]
        import uuid
        await communicator.connect()
        await communicator.receive_json_from()  
        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(uuid.uuid4()),
                'content': 'Message to locked group'
            }
        })

        response = await communicator.receive_json_from()
        assert 'error' in response
        assert response['error']['code'] == 4004
        assert response['error']['detail'] == "Resource not found."

        await communicator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group_chat.id),
                'content': 'Original message',
                'extra_fields': {
                    'forwarded_from_id': str(uuid.uuid4())
                }
            }
        })
        response = await communicator.receive_json_from()
        assert 'error' in response
        assert response['error']['code'] == 4003
        await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageOperations:
    """Test message operations (edit, delete, reaction, read receipt)"""

    async def test_mark_message_as_read(self, users,communicator,  one_to_one_chat):
        """Test marking message as read"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'readreceipt.dispatch'
        assert len(response['data']['read_receipts']) == 1
        
        await communicator.disconnect()

    async def test_mark_multiple_messages_as_read_for_same_room(self, users, communicator, one_to_one_chat):
        """Test marking multiple messages as read for same room"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Message 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Message 2"
        )
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        message_ids = [str(message1.id), str(message2.id)]
        await communicator.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': [str(message1.id), str(message2.id)]
            }
        })
        
        # Should receive response for each room
        response = await communicator.receive_json_from()
        # print(response)
        assert response['eventType'] == 'readreceipt.dispatch'
        assert len(response['data']) == 2 # 2 messages
        assert response['data'][0]['id'] in message_ids # can't guarantee the order
        message_ids.remove(response['data'][0]['id'])
        assert response['data'][1]['id'] in message_ids # can't guarantee the order

        assert response['data'][0]['room']['id'] == response['data'][1]['room']['id'] # same room here
        
        await communicator.disconnect()

    async def test_mark_multiple_messages_as_read_for_different_room(self, register_room_with_user, users, channel, communicator, one_to_one_chat):
        """Test marking multiple messages as read for different rooms"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        message1 = await database_sync_to_async(Message.objects.create)(
            room=channel,
            sender=users[0],
            content="Message 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Message 2"
        )
        await register_room_with_user(users[1].id, channel.id)
        communicator.scope['user'] = users[1]
        message_ids = [str(message1.id), str(message2.id)]
        room_ids = [str(channel.id),str(one_to_one_chat.id) ]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': [str(message1.id), str(message2.id)]
            }
        })
        
        # Should receive response for each room
        response = await communicator.receive_json_from()
        assert response['eventType'] == 'readreceipt.dispatch'
        assert len(response['data']) == 1
        assert response['data'][0]['id'] in message_ids
        message_ids.remove(response['data'][0]['id'])
        assert response['data'][0]['room']['id'] in room_ids
        room_ids.remove(response['data'][0]['room']['id']) 

        response = await communicator.receive_json_from()
        assert response['eventType'] == 'readreceipt.dispatch'
        assert len(response['data']) == 1
        assert response['data'][0]['id'] in message_ids
        assert response['data'][0]['room']['id'] in room_ids
        room_ids.remove(response['data'][0]['room']['id'])
        
        await communicator.disconnect()


    async def test_mark_multiple_messages_as_read_but_one_non_permitted_room(self, users, communicator, one_to_one_chat, group_chat):
        """Test marking multiple messages as read but one of the message is from a room user isn't permitted"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Message 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users[0],
            content="Message 2"
        )
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': [str(message1.id), str(message2.id)]
            }
        })
        
        # Should receive response for each room
        response = await communicator.receive_json_from()
        assert 'error' in response
        assert response['error']['code'] == 4002
        await communicator.disconnect()

    async def test_message_acknowledged(self, users, communicator, one_to_one_chat):
        """Test message acknowledgment (delivery)"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
    

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()

        communicator1.scope['user'] = users[0]
        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'message.acknowledged',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await communicator1.receive_json_from()
        assert response['eventType'] == 'messagedelivered.dispatch'
        assert len(response['data']) == 1
        assert response['data'][0]['id'] == str(message.id)
        assert len(response['data'][0]['delivered_to']) == 1
        assert response['data'][0]['delivered_to'][0] == users[1].username

        
        await communicator.disconnect()
        await communicator1.disconnect()

    async def test_message_acknowledged_on_message_user_dont_have_access_to(self, users, communicator, channel):
        """Test message acknowledgment on message the user don't have access to(delivery)"""
        message = await database_sync_to_async(Message.objects.create)(
            room=channel,
            sender=users[0],
            content="Test message"
        )
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
    

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()

        communicator1.scope['user'] = users[0]
        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'message.acknowledged',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        assert response["error"]["code"] == 4002
        assert await database_sync_to_async(lambda: len(message.read_receipts.all()))() == 0

        
        await communicator.disconnect()
        await communicator1.disconnect()

    async def test_add_reaction_to_message(self, communicator, users, one_to_one_chat):
        """Test adding reaction to message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.react',
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

    async def test_add_double_reaction_of_the_same_content_to_message(self, communicator, users, one_to_one_chat):
        """Test adding double reaction of the same contnt to message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.react',
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
        
        await communicator.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'add',
                'message_id': str(message.id),
                'reaction_content': '👍'
            }
        })
        response = await communicator.receive_json_from()


        assert 'error' in response
        assert response['error']['code'] == 4005 # integrity error
        await communicator.disconnect()

    async def test_add_double_reaction_of_different_content_to_message(self, communicator, users, one_to_one_chat):
    
        """Test adding double reaction of different content to message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )
        

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.react',
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
        
        await communicator.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'add',
                'message_id': str(message.id),
                'reaction_content': '😂'
            }
        })
        response = await communicator.receive_json_from()


        assert response['eventType'] == 'reaction.dispatch'
        assert response['data']['status'] == 'successful'
        assert any(r['reaction_content'] == '😂' for r in response['data']['message']['reactions'])
        
     

    async def test_remove_reaction_from_message(self, communicator, users, one_to_one_chat):
        """Test removing reaction from message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )
        
        # Add reaction first
        await database_sync_to_async(Reaction.objects.create)(
            message=message,
            user=users[1],
            reaction_content='👍'
        )
        

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.react',
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


    async def test_remove_reaction_twice_from_message(self, communicator, users, one_to_one_chat):
        """Test removing reaction twice from message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )
        
        # Add reaction first
        await database_sync_to_async(Reaction.objects.create)(
            message=message,
            user=users[1],
            reaction_content='👍'
        )
        

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'remove',
                'message_id': str(message.id)
            }
        })
        
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'remove',
                'message_id': str(message.id)
            }
        })
        response = await communicator.receive_json_from()
        assert response['data']['action'] == 'remove'
        assert response['data']['status'] == 'failed'
        
        await communicator.disconnect()

    async def test_edit_message(self, communicator, users, one_to_one_chat):
        """Test editing message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original content"
        )
        
 
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from() 
        await communicator.send_json_to({
            'event_type': 'message.modify',
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


    async def test_edit_multiple_message_by_the_same_user_should_fail(self, communicator, users, one_to_one_chat):
        """Test editing multiple message by the same user at the same time should fail"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original content"
        )
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original content 2"
        )
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from() 
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': [str(message.id), str(message1.id)],
                'extra_fields': {
                    'content': 'Edited content'
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert "error" in response
        assert response["error"]["code"] == 4003
        await communicator.disconnect()

    async def test_non_message_sender_cant_edit_message(self, communicator, users, channel):
        """Test editing message by non message sender should fail"""
        message = await database_sync_to_async(Message.objects.create)(
            room=channel,
            sender=users[0],
            content="Original content"
        )

        
    
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from() 
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': str(message.id),
                'extra_fields': {
                    'content': 'Edited content'
                }
            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        assert response["error"]["code"] == 4002 
        await communicator.disconnect()
  
    async def test_edit_message_with_no_content(self, communicator, users, channel):
        """Test editing message with no content provided"""
        message = await database_sync_to_async(Message.objects.create)(
            room=channel,
            sender=users[0],
            content="Original content"
        )

 
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from() 
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': str(message.id),

            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        assert response["error"]["code"] == 4003 
        assert "Content should be provided for update action" in str(response["error"]["detail"])
        await communicator.disconnect()
  
  
    async def test_modify_message_across_multiple_rooms_at_the_same_time(self, communicator, users, one_to_one_chat, channel):
        """Test modify multiple message across different rooms isnt allowed"""
        message = await database_sync_to_async(Message.objects.create)(
            room=channel,
            sender=users[0],
            content="Channel content"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="One to one chat content"
        )
    
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from() 
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete', # delete is used here because editing is not allowed for multiple messages 
                'message_id': [str(message.id), str(message2.id)],

            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        assert response["error"]["code"] == 4003
        assert "All messages marked for modification must come from the same room" in str(response["error"]["detail"])
        await communicator.disconnect()



    async def test_delete_message(self, communicator, users, one_to_one_chat):
        """Test deleting message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="To be deleted"
        )
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.modify',
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



    async def test_deleting_multiple_messages(self, communicator, users, one_to_one_chat):
        """Test deleting multiple messages"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="To be deleted"
        )
        
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="To be deleted 1"
        )

        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="To be deleted 2"
        )
        

        message_ids = [str(message.id), str(message1.id), str(message2.id)]
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': message_ids
            }
        })
        
        response = await communicator.receive_json_from()
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['action'] == 'delete'
        for m_id in message_ids:
            assert str(m_id) in response['data']['message_ids']
        
        await communicator.disconnect()


    async def test_delete_message_by_non_sender(self, communicator, users, one_to_one_chat):
        """Test deleting message by non sender"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="To be deleted"
        )
        

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': [str(message.id)]
            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        
        await communicator.disconnect()

    async def test_typing_indicator(self, users, communicator, one_to_one_chat):
        """Test typing indicator event"""
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        communicator1.scope['user'] = users[1]
        await communicator1.connect()
        await communicator1.receive_json_from()


        await communicator.send_json_to({
            'event_type': 'message.typing',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await communicator1.receive_json_from()
        
        assert response['eventType'] == 'messagetyping.dispatch'
        assert response['data']['username'] == 'user0'
        
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
        communicator.scope['user'] = users[0]
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
        communicator.scope['user'] = users[0]
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
            sender=users[0],
            content="Message 1"
        )
        await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[1],
            content="Message 2"
        )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
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
                sender=users[0],
                content=f"Message {i}"
            )
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
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
        communicator.scope['user'] = users[1]
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
        communicator.scope['user'] = users[1]
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
        communicator.scope['user'] = users[0]
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
        communicator.scope['user'] = users[0]
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_add_members_to_room',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[1].id, users['user3'].id]
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
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_remove_members_from_room',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[1].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomremovemembers.dispatch'
        assert 'user2' in response['data']['removed_members']
        
        await communicator.disconnect()

    async def test_non_admin_cannot_add_members(self, users, group_chat):
        """Test that non-admin cannot add members"""
        # Add user2 as participant but not admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[1]
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
        communicator.scope['user'] = users[0]
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
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'receive_modify_room_event',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'add_admin',
                'data': {
                    'users': [users[1].id]
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
        communicator.scope['user'] = users[0]
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
        communicator.scope['user'] = users[0]
        await communicator.connect()
        
        await communicator.send_json_to({
            'event_type': 'room.create',
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
        communicator.scope['user'] = users[0]
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