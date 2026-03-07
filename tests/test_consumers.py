import pytest
import json
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.conf import realtime_chat_settings
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



@pytest.fixture
def communicator(websocket_communicator, users):
    """Create a WebSocket communicator"""
    return websocket_communicator(users[0])
     


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
                    'property': {
                        'preferences': {'theme': 'dark'}
                    }
                }
            }
        })
        
        response = await communicator.receive_json_from()

        assert response['data']['property']['preferences'] == {'theme': 'dark'}
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
        assert await database_sync_to_async(lambda: len(message.realtime_chat_messaging_readreceipt_read_receipts.all()))() == 0

        
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


    async def test_edit_message_with_editable_fields_but_not_allowed_for_update(self, communicator, users, group_chat, one_to_one_chat):
        """Test editing message with editable fields but not allowed for update action should ignore those fields and update only content"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original content"
        )
 
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from() 
        import uuid
        await communicator.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': str(message.id),
                'extra_fields': {
                    'content': 'Edited content',
                    'sender_id': users[1].id,
                    'room_id': str(group_chat.id),
                    'created_at': '2024-01-01T00:00:00Z',
                    'updated_at': '2024-01-01T00:00:00Z',
                    'is_forwarded': True,
                    'forwarded_from_id': str(message.id),
                    'parent_message_id': str(message.id)
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['message']['content'] == 'Edited content'
        assert response['data']['message']['sender']['id'] == users[0].id
        assert response['data']['message']['room']['id'] == str(one_to_one_chat.id)
        assert response['data']['message']['is_forwarded'] is False
        assert response['data']['message']['forwarded_from'] is None
        assert response['data']['message']['parent_message'] is None

        await communicator.disconnect()

    async def test_edit_message_ineditable_fields(self, communicator, users, one_to_one_chat):
        """Test editing message with ineditable fields should not update them"""
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
                    'content': 'Edited content', 
                    'sender': users[1].id, # should ignore
                    'room': str(one_to_one_chat.id), # should ignore
                }
            }
        })
        
        response = await communicator.receive_json_from()
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['message']['content'] == 'Edited content'
        assert response['data']['message']['sender']['id'] == users[0].id
        assert response['data']['message']['room']['id'] == str(one_to_one_chat.id)
        
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
        assert "'extra_fields' field should be provided for update action" in str(response["error"]["detail"])
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

    async def test_fetch_rooms(self, users, communicator, channel, one_to_one_chat, group_chat):
        """Test fetching user's rooms"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.list',
            'data': {}
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomlist.dispatch'
        assert len(response['data']) >= 3
        
        await communicator.disconnect()

    async def test_fetch_room_details(self, users, group_chat):
        """Test fetching specific room details"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        
        await communicator.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': str(group_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()

        assert response['eventType'] == 'roominfo.dispatch'
        assert response['data']['name'] == 'Test Group'
        assert len(response['data']['participants']) == 1

        
        await communicator.disconnect()

    async def test_fetch_room_details_by_non_member(self, communicator, users, group_chat):
        """Test fetching specific room details by non room member"""

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        
        await communicator.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': str(group_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()

        assert "error" in response
        assert response["error"]["code"] == 4002
        
        await communicator.disconnect()

    async def test_fetch_messages(self, users, communicator, one_to_one_chat):
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
        
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.messages',
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
        for i in range(50):
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
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 1,
                    'size': 10
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 10
        assert response['data']['has_next'] is True
        assert response['data']['has_previous'] is False
        assert response['data']['next_page_number'] == 2
        assert response['data']['prev_page_number'] == None
        await communicator.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 5,
                    'size': 10
                }
            }
        })
        
        response = await communicator.receive_json_from()
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 10
        assert response['data']['has_next'] is False
        assert response['data']['has_previous'] is True
        assert response['data']['next_page_number'] == None
        assert response['data']['prev_page_number'] == 4

        await communicator.disconnect()

    async def test_fetch_messages_with_pagination_overflow(self, users, one_to_one_chat):
        """Test fetching messages with pagination overflow doesnt raise error"""
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
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 3,
                    'size': 5
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 5
        assert response['data']['has_next'] is False
        assert response['data']['has_previous'] is True
        assert response['data']['next_page_number'] == None
        assert response['data']['prev_page_number'] == 1


        await communicator.disconnect()

    async def test_fetch_messages_with_pagination_with_improper_data(self, users, one_to_one_chat):
        """Test fetching messages with pagination with improper data raises error"""
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
        await communicator.receive_json_from()

        #without size
        await communicator.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 1,
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert "error" in response
        assert 'page and size required' in response['error']['detail']
        
        #without page
        await communicator.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'size': 1,
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert "error" in response
        assert 'page and size required' in response['error']['detail']

        #without both doesn't paginate returns all
        await communicator.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 10
        await communicator.disconnect()


    

    async def test_join_public_channel(self, communicator, users, channel):
        """Test joining a public channel"""

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()

        
        await communicator.send_json_to({
            'event_type': 'room.join',
            'data': {
                'room_id': str(channel.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user1' in response['data']['new_members']
        
        await communicator.disconnect()

    async def test_cannot_join_private_channel(self, communicator, users, channel):
        """Test that cannot join private channel"""
        # Make channel private
        await database_sync_to_async(setattr)(channel, 'is_public', False)
        await database_sync_to_async(channel.save)()

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.join',
            'data': {
                'room_id': str(channel.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4003
        
        await communicator.disconnect()
        
    async def test_cannot_join_group_chat(self, communicator, users, group_chat):
        """Test that cannot join group_chat"""

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.join',
            'data': {
                'room_id': str(group_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4003
        assert "Ask an admin to add you to the group" in str(response['error']['detail'])
        
        await communicator.disconnect()


    async def test_leave_groupchat(self,communicator, users, group_chat):
        """Test leaving a groupchat"""


        await database_sync_to_async(group_chat.participants.add)(users[1])
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )

        communicator1.scope['user'] = users[0]

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()

        
        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.leave',
            'data': {
                'room_id': str(group_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomexit.dispatch'
        assert 'You left' in response['data']['message']
        assert len(response['data']['room']['participants']) == 1
        # check other members of the group got an event of the exit
        response1 = await communicator1.receive_json_from()
        assert response1['eventType'] == 'roomremovemembers.dispatch'
        assert 'user1' in response1['data']['removed_members']
        assert response1['data']['removed_by'] == 'self'

        await communicator.disconnect()
        await communicator1.disconnect()

    async def test_leave_channel(self,communicator, users, channel):
        """Test leaving a channel"""


        await database_sync_to_async(channel.subscribers.add)(users[1])
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )

        communicator1.scope['user'] = users[0]

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()


        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.leave',
            'data': {
                'room_id': str(channel.id)
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomexit.dispatch'
        assert 'You left' in response['data']['message']
        assert len(response['data']['room']['subscribers']) == 1


        # check other members of the group got an event of the exit
        response1 = await communicator1.receive_json_from()
        assert response1['eventType'] == 'roomremovemembers.dispatch'
        assert 'user1' in response1['data']['removed_members']
        assert response1['data']['removed_by'] == 'self'


        await communicator.disconnect()
        await communicator1.disconnect()

    async def test_leave_onetoonechat(self,communicator, users, one_to_one_chat):
        """Test leaving a one to one chat"""

  
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.leave',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await communicator.receive_json_from()

        assert "error" in response
        assert 'You can only leave a channel/group chat' in response["error"]["detail"]
        await communicator.disconnect()


    async def test_leave_groupchat_as_the_last_participant(self,communicator, users, group_chat):
        """Test leaving a groupchat as the last participant"""
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        # retreive rooms before leaving
        await communicator.send_json_to({
            'event_type': 'room.list'
        })
        response = await communicator.receive_json_from() 
        assert len(response['data']) == 1
        assert response['data'][0]["id"] == str(group_chat.id)

        await communicator.send_json_to({
            'event_type': 'room.leave',
            'data': {
                'room_id': str(group_chat.id)
            }
        }) # room is expected to be deleted after the last person leaves
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomdelete.dispatch'
        assert response['data']['room_id'] == str(group_chat.id) 
        # retreive rooms after leaving
        await communicator.send_json_to({
            'event_type': 'room.list'
        })
        response = await communicator.receive_json_from()
        assert len(response['data']) == 0
        await communicator.disconnect()

        
    async def test_leave_channel_as_the_last_subscriber(self,communicator, users, channel):
        """Test leaving a channel as the last subscriber"""
        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()

        # retreive rooms before leaving
        await communicator.send_json_to({
            'event_type': 'room.list'
        })
        response = await communicator.receive_json_from() 
        assert len(response['data']) == 1
        assert response['data'][0]["id"] == str(channel.id)

        await communicator.send_json_to({
            'event_type': 'room.leave',
            'data': {
                'room_id': str(channel.id)
            }
        }) # room is expected to be deleted after the last person leaves
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomdelete.dispatch'
        assert response['data']['room_id'] == str(channel.id) 
        # retreive rooms after leaving
        await communicator.send_json_to({
            'event_type': 'room.list'
        })
        response = await communicator.receive_json_from()
        assert len(response['data']) == 0
        await communicator.disconnect()

    async def test_add_members_to_group(self,communicator, users, group_chat):
        """Test adding members to group"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[1].id, users[2].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user1' in response['data']['new_members']
        assert 'user2' in response['data']['new_members']
        
        await communicator.disconnect()

    async def test_add_members_to_channel(self,communicator, users, channel):
        """Test adding members to channel"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(channel.id),
                'members': [users[1].id, users[2].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user1' in response['data']['new_members']
        assert 'user2' in response['data']['new_members']
        
        await communicator.disconnect()

    async def test_remove_members_from_groupchat(self, communicator, users, group_chat):
        """Test removing members from groupchat"""
        # Add user2 first
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )

        communicator1.scope['user'] = users[1]

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()


        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.remove_members',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[1].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomremovemembers.dispatch'
        assert 'user1' in response['data']['removed_members']

        response1 = await communicator1.receive_json_from()
        
        assert response1['eventType'] == 'roomexit.dispatch'
        assert response1['data']['message'] == f"You have been removed by {users[0].username}"
        
        await communicator.disconnect()
        await communicator1.disconnect()


    async def test_remove_members_from_channel(self, communicator, users, channel):
        """Test removing members from channel"""
        # Add user2 first
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )

        communicator1.scope['user'] = users[1]

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()


        await communicator1.connect()
        await communicator1.receive_json_from()

        await communicator.send_json_to({
            'event_type': 'room.remove_members',
            'data': {
                'room_id': str(channel.id),
                'members': [users[1].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomremovemembers.dispatch'
        assert 'user1' in response['data']['removed_members']

        response1 = await communicator1.receive_json_from()
        
        assert response1['eventType'] == 'roomexit.dispatch'
        assert response1['data']['message'] == f"You have been removed by {users[0].username}"
        
        await communicator.disconnect()
        await communicator1.disconnect()

    async def test_non_admin_cannot_add_members(self, communicator, users, group_chat):
        """Test that non-admin cannot add members"""
        # Add user 2 as participant but not admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[2].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_non_admin_cannot_remove_members(self, communicator, users, group_chat):
        """Test that non-admin cannot remove members"""
        # Add user 2 as participant but not admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.remove_members',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[2].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await communicator.disconnect()

    async def test_admin_cannot_remove_creator(self, communicator, register_room_with_user, users, group_chat):
        """Test that admin cannot remove the room creator"""
        # Add user 2 as participant and admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        await register_room_with_user(users[1].id, group_chat.id)
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.remove_members',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[0].id]
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert "user0" not in response['data']['removed_members']
        assert len(response['data']['room']['participants']) == 2
        assert response['data']['room']['participants'][0]['id'] == users[0].id
        await communicator.disconnect()

    async def test_modify_groupchat_as_admin(self, communicator, users, group_chat):
        """Test modifying groupchat as admin"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
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

    async def test_modify_channel_as_moderator(self, communicator, users, channel):
        """Test modifying channel as moderator"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(channel.id),
                'action': 'update',
                'data': {
                    'description': 'Updated Channel Description'
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        assert response['data']['description'] == 'Updated Channel Description'
        
        await communicator.disconnect()

    async def test_modify_onetoonechat(self, communicator, users, one_to_one_chat):
        """Test modifying one to one chat"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'action': 'update',
                'data': {
                    'property': {
                        'preferences': {'theme': 'dark'},
                    },
                    'name': 'new name' # ignored
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        assert response['data']['property']['preferences'] == {'theme': 'dark'}
        assert 'name' not in response['data']
        
        await communicator.disconnect()

    async def test_add_admin_to_group(self, communicator, users, group_chat):
        """Test adding admin to group"""
        # Add user1 as participant
        await database_sync_to_async(group_chat.participants.add)(users[1])
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
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
        assert 'user1' in admin_usernames
        
        await communicator.disconnect()

    async def test_add_admin_to_group_by_non_admin_member(self, communicator, users, group_chat):
        """Test adding admin to group"""
        # Add user1 as participant
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.participants.add)(users[2])
        

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'add_admin',
                'data': {
                    'users': [users[1].id, users[2].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        assert response["error"]["code"] == 4002
        
        await communicator.disconnect()

    async def test_add_mod_to_channel(self, communicator, users, channel):
        """Test adding mod to channel"""
        # Add user1 as participant
        await database_sync_to_async(channel.subscribers.add)(users[1])
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(channel.id),
                'action': 'add_moderator',
                'data': {
                    'users': [users[1].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        admin_usernames = [admin['username'] for admin in response['data']['moderators']]
        assert 'user1' in admin_usernames
        
        await communicator.disconnect()

    async def test_add_mod_to_channel_by_non_mod_member(self, communicator, users, channel):
        """Test adding moderators to channel"""
        # Add user1 as participant
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(channel.subscribers.add)(users[2])
        

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(channel.id),
                'action': 'add_moderator',
                'data': {
                    'users': [users[1].id, users[2].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        assert "error" in response
        assert response["error"]["code"] == 4002
        
        await communicator.disconnect()

    async def test_remove_admin_from_group(self, communicator, users, group_chat):
        """Test removing admin from group"""
        # Add user1 as participant and admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'remove_admin',
                'data': {
                    'users': [users[1].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        admin_usernames = [admin['username'] for admin in response['data']['admins']]
        assert 'user1' not in admin_usernames
        
        await communicator.disconnect()

    async def test_remove_mod_from_channel(self, communicator, users, channel):
        """Test removing mod from channel"""
        # Add user1 as participant
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(channel.moderators.add)(users[1])
        

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(channel.id),
                'action': 'remove_moderator',
                'data': {
                    'users': [users[1].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        admin_usernames = [admin['username'] for admin in response['data']['moderators']]
        assert 'user1' not in admin_usernames
        
        await communicator.disconnect()

    async def test_remove_creator_from_admin(self, communicator, register_room_with_user, users, group_chat):
        """Test removing creator from group admin"""
        # Add user1 as participant and admin
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        await register_room_with_user(users[1].id, group_chat.id)

        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'remove_admin',
                'data': {
                    'users': [users[0].id]
                }
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        admin_usernames = [admin['username'] for admin in response['data']['admins']]
        assert 'user0' in admin_usernames
        
        await communicator.disconnect()

    async def test_delete_groupchat(self, communicator, users, group_chat):
        """Test delete chat (only room creators can delete rooms except one to one chat)"""

        communicator.scope['user'] = users[0]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'delete',
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomdelete.dispatch'
        assert response['data']['room_id'] == str(group_chat.id)
        await communicator.disconnect()

    async def test_delete_groupchat_by_non_creator(self, communicator, users, group_chat):
        """Test delete chat by non group chat creator"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        communicator.scope['user'] = users[1]
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group_chat.id),
                'action': 'delete',
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert "error" in response


        assert response['error']['code'] == 4002
        assert response['error']['detail'] == 'User is not the creator of this room'
        
        await communicator.disconnect()

    async def test_delete_onetoonechat(self, communicator, users, one_to_one_chat):
        """Test delete one to one chat"""

        communicator.scope['user'] = users[1] 
        await communicator.connect()
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'action': 'delete',
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert response['eventType'] == 'roomdelete.dispatch'
        assert response['data']['room_id'] == str(one_to_one_chat.id)
        await communicator.disconnect()
        

# =================== DELETED MESSAGE RETRIEVAL ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestDeletedMessageRetrieval:
    """Test retrieving messages after deletion"""
    
    async def test_retrieve_messages_after_soft_delete(self, users, one_to_one_chat):
        """Test that soft-deleted messages are excluded from retrieval"""

        
        # Create some messages
        messages = []
        for i in range(5):
            msg = await database_sync_to_async(Message.objects.create)(
                room=one_to_one_chat,
                sender=users[0],
                content=f'Message {i}'
            )
            messages.append(msg)
        
        # Soft delete messages 1 and 3 (if soft delete enabled)
        if realtime_chat_settings.MESSAGE_SOFT_DELETE:
            messages[1].is_deleted = True
            messages[3].is_deleted = True
            await database_sync_to_async(messages[1].save)()
            await database_sync_to_async(messages[3].save)()
        else:
            # Hard delete
            await database_sync_to_async(messages[1].delete)()
            await database_sync_to_async(messages[3].delete)()
        
        # Retrieve messages
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        retrieved_messages = response['data']['data']['messages']
        
        # Should only get 3 messages (0, 2, 4)
        assert len(retrieved_messages) == 3
        
        contents = [m['content'] for m in retrieved_messages]
        assert 'Message 0' in contents
        assert 'Message 2' in contents
        assert 'Message 4' in contents
        assert 'Message 1' not in contents  # Deleted
        assert 'Message 3' not in contents  # Deleted
        
        await comm.disconnect()
    
    async def test_retrieve_messages_after_hard_delete(self, users, one_to_one_chat):
        """Test retrieving messages after hard deletion"""
        
        # Create messages
        msg1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat, sender=users[0], content='Keep this'
        )
        msg2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat, sender=users[0], content='Delete this'
        )
        msg3 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat, sender=users[0], content='Keep this too'
        )
        
        # Hard delete msg2
        await database_sync_to_async(msg2.delete)()
        
        # Retrieve
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        retrieved = response['data']['data']['messages']
        assert len(retrieved) == 2
        
        contents = [m['content'] for m in retrieved]
        assert 'Keep this' in contents
        assert 'Keep this too' in contents
        assert 'Delete this' not in contents
        
        await comm.disconnect()
    
    async def test_delete_multiple_messages_then_retrieve(self, users, one_to_one_chat):
        """Test bulk deletion then retrieval"""

        # Create 10 messages
        message_ids = []
        for i in range(10):
            msg = await database_sync_to_async(Message.objects.create)(
                room=one_to_one_chat, sender=users[0], content=f'Message {i}'
            )
            message_ids.append(str(msg.id))
        
        # Delete messages 2, 4, 6, 8
        delete_ids = [message_ids[i] for i in [2, 4, 6, 8]]
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        await comm.connect()
        await comm.receive_json_from()
        
        # Delete via WebSocket
        await comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': delete_ids
            }
        })
        
        delete_response = await comm.receive_json_from()
        assert delete_response['eventType'] == 'messagemodification.dispatch'
        
        # Retrieve
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await comm.receive_json_from()
        retrieved = response['data']['data']['messages']
        
        # Should have 6 messages (0, 1, 3, 5, 7, 9)
        assert len(retrieved) == 6
        
        await comm.disconnect()
    
    async def test_retrieve_room_info_shows_correct_message_count(self, users, one_to_one_chat):
        """Test that room info shows correct count after deletions"""

        
        # Create 5 messages
        message_ids = []
        for i in range(5):
            msg = await database_sync_to_async(Message.objects.create)(
                room=one_to_one_chat, sender=users[0], content=f'Msg {i}'
            )
            message_ids.append(str(msg.id))
        
        # Delete 2 messages
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': [message_ids[0], message_ids[2]]
            }
        })
        
        await comm.receive_json_from()
        
        # Get room info
        await comm.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        info_response = await comm.receive_json_from()
        
        # Should reflect actual message count
        # Note: Depends on implementation - may need to verify logic
        assert info_response['eventType'] == 'roominfo.dispatch'
        
        await comm.disconnect()


# ==================NOTIFICATION AUTO-DELETION ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestNotificationAutoDeletion:
    """
    Test notification auto-deletion when sender deletes undelivered messages.
    
    Scenario: User A sends messages to User B. User B receives notifications but
    doesn't mark them as delivered. User A deletes the messages. The notifications
    should be automatically removed.
    """
    
    async def test_notification_deleted_when_sender_deletes_undelivered_message(self, users, one_to_one_chat):
        """Test notification auto-deletion on message deletion"""
        if not realtime_chat_settings.ENABLE_NOTIFICATION:
            pytest.skip("Notifications disabled")
        
        # User 0 (sender) sends messages to User 1 (receiver)
        sender_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        sender_comm.scope['user'] = users[0]
        await sender_comm.connect()
        await sender_comm.receive_json_from()
        
        # Send 3 messages
        message_ids = []
        for i in range(3):
            await sender_comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Undelivered message {i}'
                }
            })
            response = await sender_comm.receive_json_from()
            message_ids.append(response['data']['id'])
        
        # Check notifications created for receiver (User 1)
        notifications = await database_sync_to_async(
            lambda: list(ChatNotification.objects.filter(
                recipients=users[1],
            ))
        )()
        
        initial_notification_count = len(notifications)
        assert initial_notification_count >= 3  # Should have notifications
        
        # Sender deletes the messages WITHOUT receiver marking as delivered
        await sender_comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': message_ids
            }
        })
        
        delete_response = await sender_comm.receive_json_from()
        assert delete_response['eventType'] == 'messagemodification.dispatch'
        
        # Check notifications - should be auto-deleted or cleaned up
        remaining_notifications = await database_sync_to_async(
            lambda: list(ChatNotification.objects.filter(
                recipients=users[1],
            ))
        )()
        
        # Verify notifications are cleaned up
        # If notifications are per-message, they should be gone
        # If notification is per-room, the message refs should be removed
        assert len(remaining_notifications) < initial_notification_count and len(remaining_notifications) == 0
        
        await sender_comm.disconnect()
    

    async def test_message_deletion_lead_to_notification_deletion(self, users, one_to_one_chat):
        """Test deletion of messages deletes notification for users who haven't acknowledged notification"""
        if not realtime_chat_settings.ENABLE_NOTIFICATION:
            pytest.skip("Notifications disabled")
        

        # Sender sends 5 messages
        sender_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        sender_comm.scope['user'] = users[0]
        await sender_comm.connect()
        await sender_comm.receive_json_from()
        message_ids = []
        for i in range(5):
            await sender_comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Message {i}'
                }
            })
            response = await sender_comm.receive_json_from()
            message_ids.append(response['data']['id'])
        
        # Receiver connects but does not acknowledge
        receiver_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        receiver_comm.scope['user'] = users[1]
        await receiver_comm.connect()

        # Receives notification
        notifications = await receiver_comm.receive_json_from()
        assert notifications['eventType'] == 'chat.notifications'
        assert len(notifications['data'][str(one_to_one_chat.id)]) == 5


        # Disconnect receiver
        await receiver_comm.disconnect()
        
        # Sender deletes all messages
        await sender_comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': message_ids
            }
        })
        

        # connect again
        receiver_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        receiver_comm.scope['user'] = users[1]
        await receiver_comm.connect()

        updated_notifications = await receiver_comm.receive_json_from()
        
        # Check notification state
        assert updated_notifications['eventType'] == 'chat.notifications'
        assert updated_notifications['data'] == {}
        
        await sender_comm.disconnect()
        await receiver_comm.disconnect()
    
    async def test_notification_cleanup_on_multiple_recipients(self, users, register_room_with_user, create_group_chat):
        """Test notification cleanup when message sent to multiple users"""
        if not realtime_chat_settings.ENABLE_NOTIFICATION:
            pytest.skip("Notifications disabled")
        
        # Create group with 3 users
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Test Group',
            participants=[users[0], users[1], users[2]]
        )
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await register_room_with_user(users[2].id, group.id)
        
        # User 0 sends message
        sender_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        sender_comm.scope['user'] = users[0]
        await sender_comm.connect()
        await sender_comm.receive_json_from()
        
        await sender_comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group.id),
                'content': 'Group message'
            }
        })
        
        response = await sender_comm.receive_json_from()
        message_id = response['data']['id']
        
        # Check notifications for users 1 and 2
        notifications_user1 = await database_sync_to_async(
            lambda: ChatNotification.objects.filter(recipients=users[1], message__room=group).count()
        )()
        notifications_user2 = await database_sync_to_async(
            lambda: ChatNotification.objects.filter(recipients=users[2], message__room=group).count()
        )()
        
        assert notifications_user1 > 0
        assert notifications_user2 > 0
        
        # Delete message
        await sender_comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': [message_id]
            }
        })
        
        await sender_comm.receive_json_from()
        
        # Both users' notifications should be cleaned
        remaining_user1 = await database_sync_to_async(
            lambda: ChatNotification.objects.filter(recipients=users[1], message__room=group).count()
        )()
        remaining_user2 = await database_sync_to_async(
            lambda: ChatNotification.objects.filter(recipients=users[2], message__room=group).count()
        )()
        
        # Notifications should be reduced or cleared
        assert remaining_user1 == 0
        assert remaining_user2 == 0
        
        await sender_comm.disconnect()


# =================== ROOM SETTINGS PERMISSIONS ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRoomSettingsPermissions:
    """
    Test that only admins/creators can update critical room settings:
    - group_locked (GroupChat)
    - join_approval_required (GroupChat)
    - is_public (Channel)
    """
    
    async def test_admin_can_update_group_locked(self, register_room_with_user, users, create_group_chat):
        """Test admin can update group_locked setting"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],  # Creator
            name='Lockable Group',
            participants=[users[0], users[1], users[2]]
        )
        
        # Add user[1] as admin
        await database_sync_to_async(group.admins.add)(users[0], users[1])
        
        # Register users to channel group for receiving updates
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await register_room_with_user(users[2].id, group.id)

        # Admin updates group_locked
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[1]  # Admin
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group.id),
                'action': 'update',
                'data': {
                    'group_locked': True
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        
        # Verify update
        await database_sync_to_async(group.refresh_from_db)()
        assert group.group_locked is True
        
        await comm.disconnect()
    
    async def test_regular_member_cannot_update_group_locked(self, register_room_with_user, users, create_group_chat):
        """Test regular member cannot update group_locked"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],  # Creator
            name='Locked Test',
            participants=[users[0], users[1], users[2]]
        )

        
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await register_room_with_user(users[2].id, group.id)

        # Regular member (user[2]) tries to update
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[2]  # Regular member
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group.id),
                'action': 'update',
                'data': {
                    'group_locked': True
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should receive permission error
        assert 'error' in response
        assert response['error']['code'] == 4002  # Permission denied
        
        await comm.disconnect()
    
    async def test_creator_can_update_join_approval_required(self, register_room_with_user, users, create_group_chat):
        """Test creator can update join_approval_required"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Approval Group',
            participants=[users[0], users[1]]
        )
        
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)

        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]  # Creator
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group.id),
                'action': 'update',
                'data': {
                    'join_approval_required': True
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        
        # Verify
        await database_sync_to_async(group.refresh_from_db)()
        assert group.join_approval_required is True
        
        await comm.disconnect()
    
    async def test_non_admin_cannot_update_join_approval_required(self, register_room_with_user, users, create_group_chat):
        """Test non-admin cannot update join_approval_required"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Approval Test',
            participants=[users[0], users[1], users[2]]
        )

        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        await register_room_with_user(users[2].id, group.id)
        
        await database_sync_to_async(group.admins.add)(users[0])
        
        # Non-admin tries to update
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[2]
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group.id),
                'action': 'update',
                'data': {
                    'join_approval_required': True
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await comm.disconnect()
    
    async def test_moderator_can_update_channel_is_public(self, users, register_room_with_user):
        """Test channel moderator can update is_public setting"""
        # Create channel
        channel = await database_sync_to_async(Channel.objects.create)(
            name='Public Channel',
            creator=users[0],
            is_public=True
        )
        await database_sync_to_async(channel.moderators.add)(users[0], users[1])
        await database_sync_to_async(channel.subscribers.add)(users[0], users[1])
        
        await register_room_with_user(users[0].id, channel.id)
        await register_room_with_user(users[1].id, channel.id)

        # Moderator updates is_public
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[1]  # Moderator
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(channel.id),
                'action': 'update',
                'data': {
                    'is_public': False
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        
        # Verify
        await database_sync_to_async(channel.refresh_from_db)()
        assert channel.is_public is False
        
        await comm.disconnect()
    
    async def test_subscriber_cannot_update_channel_is_public(self, users, register_room_with_user):
        """Test regular subscriber cannot update is_public"""
        channel = await database_sync_to_async(Channel.objects.create)(
            name='Test Channel',
            creator=users[0],
            is_public=True
        )
        await database_sync_to_async(channel.subscribers.add)(users[0], users[1], users[2])
        await register_room_with_user(users[0].id, channel.id)
        await register_room_with_user(users[1].id, channel.id)
        await register_room_with_user(users[2].id, channel.id)

        # Regular subscriber tries to update
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[2]  # Regular subscriber
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(channel.id),
                'action': 'update',
                'data': {
                    'is_public': False
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002
        
        await comm.disconnect()
    
    async def test_update_multiple_settings_at_once(self, users, register_room_with_user, create_group_chat):
        """Test updating multiple room settings simultaneously"""
        group = await database_sync_to_async(create_group_chat)(
            users[0],
            name='Multi Update',
            participants=[users[0], users[1]]
        )

        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.modify',
            'data': {
                'room_id': str(group.id),
                'action': 'update',
                'data': {
                    'group_locked': True,
                    'join_approval_required': True,
                    'name': 'Updated Name'
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        
        # Verify all updates
        await database_sync_to_async(group.refresh_from_db)()
        assert group.group_locked is True
        assert group.join_approval_required is True
        assert group.name == 'Updated Name'
        
        await comm.disconnect()


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
        await communicator.receive_json_from()
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
        await communicator.receive_json_from()
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
        await communicator.receive_json_from()
        await communicator.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': '00000000-0000-0000-0000-000000000000'
            }
        })
        
        response = await communicator.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4004  # Resource not found
        
        await communicator.disconnect()