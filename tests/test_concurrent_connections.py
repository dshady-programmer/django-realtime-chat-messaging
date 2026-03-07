import pytest
import asyncio
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.models import Message, Session
from realtime_chat_messaging.utils.cache_utils import add_group_to_user_groups
from realtime_chat_messaging.consumers import GROUP_STRING
from asgiref.sync import async_to_sync
import pytest_asyncio

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(5)


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


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestConcurrentConnections:
    """Test concurrent connections from the same user (multiple devices)"""

    async def test_same_user_multiple_connections(self, users):
        """Test that same user can connect from multiple devices"""
        # Create two connections for the same user
        communicator1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator1.scope['user'] = users[0]
        
        communicator2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator2.scope['user'] = users[0]
        
        # Connect both
        connected1, _ = await communicator1.connect()
        await communicator1.receive_json_from()  # consume notifications
        
        connected2, _ = await communicator2.connect()
        await communicator2.receive_json_from()  # consume notifications
        
        assert connected1 is True
        assert connected2 is True
        
        # Verify both sessions are registered
        sessions = await database_sync_to_async(
            lambda: list(Session.objects.filter(user=users[0]))
        )()
        assert len(sessions) == 2
        assert sessions[0].channel_name != sessions[1].channel_name
        
        await communicator1.disconnect()
        await communicator2.disconnect()

    async def test_message_broadcast_to_all_user_sessions(self, users, one_to_one_chat):
        """Test that messages are broadcast to all sessions of the same user"""
        # User 1 connects from two devices
        device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device1.scope['user'] = users[1]
        
        device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device2.scope['user'] = users[1]
        
        # Sender connection
        sender = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        sender.scope['user'] = users[0]
        
        await device1.connect()
        await device1.receive_json_from()
 
        
        await device2.connect()
        await device2.receive_json_from()

        await sender.connect()
        await sender.receive_json_from()
        

        # Send message from user 0
        await sender.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Hello from device 1'
            }
        })
        
        # Sender receives their own message
        sender_response = await sender.receive_json_from()
        assert sender_response['eventType'] == 'message.dispatch'
        
        # Both devices of user 1 should receive the message
        device1_response = await device1.receive_json_from()
        device2_response = await device2.receive_json_from()
        
        assert device1_response['eventType'] == 'message.dispatch'
        assert device2_response['eventType'] == 'message.dispatch'

        assert device1_response['data']['content'] == 'Hello from device 1'
        assert device2_response['data']['content'] == 'Hello from device 1'
        
        await device1.disconnect()
        await device2.disconnect()
        await sender.disconnect()

    async def test_read_receipt_from_one_device_broadcasts_to_all(self, users, one_to_one_chat):
        """Test that marking as read on one device broadcasts to all user's devices"""
        # Create message
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test message"
        )
        
        # User 0 connects from two devices (sender)
        sender_device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        sender_device1.scope['user'] = users[0]
        
        sender_device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        sender_device2.scope['user'] = users[0]
        
        # User 1 connects from one device (reader)
        reader = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        reader.scope['user'] = users[1]
        
        await sender_device1.connect()
        await sender_device1.receive_json_from()
        
        await sender_device2.connect()
        await sender_device2.receive_json_from()
        
        await reader.connect()
        await reader.receive_json_from()
        
        # User 1 marks message as read
        await reader.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        # User 1 receives read receipt confirmation
        reader_response = await reader.receive_json_from()
        assert reader_response['eventType'] == 'readreceipt.dispatch'
        
        # Both sender devices should receive read receipt
        sender1_response = await sender_device1.receive_json_from()
        sender2_response = await sender_device2.receive_json_from()
        
        assert sender1_response['eventType'] == 'readreceipt.dispatch'
        assert sender2_response['eventType'] == 'readreceipt.dispatch'
        
        await sender_device1.disconnect()
        await sender_device2.disconnect()
        await reader.disconnect()

    async def test_typing_indicator_broadcasts_to_all_room_members_devices(self, users, one_to_one_chat):
        """Test that typing indicators broadcast to all devices of all room members"""
        # User 0 with 2 devices
        user0_device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user0_device1.scope['user'] = users[0]
        
        user0_device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user0_device2.scope['user'] = users[0]
        
        # User 1 with 2 devices
        user1_device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user1_device1.scope['user'] = users[1]
        
        user1_device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user1_device2.scope['user'] = users[1]
        
        await user0_device1.connect()
        await user0_device1.receive_json_from()
        
        await user0_device2.connect()
        await user0_device2.receive_json_from()
        
        await user1_device1.connect()
        await user1_device1.receive_json_from()
        
        await user1_device2.connect()
        await user1_device2.receive_json_from()
        
        # User 0 starts typing from device 1
        await user0_device1.send_json_to({
            'event_type': 'message.typing',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        # All devices should receive typing indicator
        responses = []
        for device in [user0_device1, user0_device2, user1_device1, user1_device2]:
            response = await device.receive_json_from()
            responses.append(response)
        
        for response in responses:
            assert response['eventType'] == 'messagetyping.dispatch'
            assert response['data']['username'] == 'user0'
        
        await user0_device1.disconnect()
        await user0_device2.disconnect()
        await user1_device1.disconnect()
        await user1_device2.disconnect()

    async def test_session_cleanup_removes_only_expired_sessions(self, users):
        """Test that cleanup only removes expired sessions, not active ones"""
        # Connect device 1
        device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device1.scope['user'] = users[0]
        
        await device1.connect()
        await device1.receive_json_from()
        
        # Verify session created
        sessions = await database_sync_to_async(
            lambda: list(Session.objects.filter(user=users[0]))
        )()
        assert len(sessions) == 1
        
        # Manually mark session as expired
        session = sessions[0]
        from django.utils import timezone
        import datetime
        expired_time = timezone.now() - datetime.timedelta(seconds=120)
        await database_sync_to_async(setattr)(session, 'last_seen', expired_time)
        await database_sync_to_async(session.save)()
        
        # Connect device 2 (should trigger cleanup)
        device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device2.scope['user'] = users[0]
        
        await device2.connect()
        await device2.receive_json_from()
        
        # Should have 2 sessions (expired one not deleted yet, but cleaned from groups)
        sessions = await database_sync_to_async(
            lambda: list(Session.objects.filter(user=users[0]))
        )()
        # The expired session still exists in DB but shouldn't be in channel groups
        assert len(sessions) == 2
        
        await device1.disconnect()
        await device2.disconnect()

    async def test_concurrent_message_sending_from_multiple_devices(self, users, group_chat):
        """Test handling concurrent message sending from different devices of same user"""
        # Add user to group
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        # User 0 with 2 devices
        device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device1.scope['user'] = users[0]
        
        device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device2.scope['user'] = users[0]
        
        await device1.connect()
        await device1.receive_json_from()
        
        await device2.connect()
        await device2.receive_json_from()
        
        # Send messages simultaneously from both devices
        await asyncio.gather(
            device1.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(group_chat.id),
                    'content': 'Message from device 1'
                }
            }),
            device2.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(group_chat.id),
                    'content': 'Message from device 2'
                }
            })
        )
        
        # Both devices should receive both messages
        device1_responses = []
        device2_responses = []
        
        for _ in range(2):
            device1_responses.append(await device1.receive_json_from())
            device2_responses.append(await device2.receive_json_from())
        
        # Verify both messages were created
        messages = await database_sync_to_async(
            lambda: list(Message.objects.filter(room=group_chat).order_by('created_at'))
        )()
        assert len(messages) == 2
        
        contents = [msg.content for msg in messages]
        assert 'Message from device 1' in contents
        assert 'Message from device 2' in contents
        
        await device1.disconnect()
        await device2.disconnect()

    async def test_room_creation_visible_to_all_user_devices(self, users):
        """Test that room creation is visible to all connected devices"""
        # User 0 with 3 devices
        devices = []
        for i in range(3):
            device = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            device.scope['user'] = users[0]
            await device.connect()
            await device.receive_json_from()
            devices.append(device)
        
        # Create room from device 1
        await devices[0].send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Multi-device Group',
                'participants': [users[1].id, users[2].id]
            }
        })
        
        # All 3 devices should receive room creation event
        responses = []
        for device in devices:
            response = await device.receive_json_from()
            responses.append(response)
        
        for response in responses:
            assert response['eventType'] == 'roomcreate.dispatch'
            assert response['data']['name'] == 'Multi-device Group'
        
        for device in devices:
            await device.disconnect()

    async def test_notification_dispatch_to_all_connected_devices(self, users, one_to_one_chat):
        """Test that notifications are sent to all connected devices on connection"""
        # Create unread message
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Unread message"
        )
        
        # Create notification
        from realtime_chat_messaging.models import ChatNotification
        notification = await database_sync_to_async(ChatNotification.objects.create)(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        await database_sync_to_async(notification.recipients.add)(users[1])
        
        # User 1 connects from 2 devices
        device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device1.scope['user'] = users[1]
        
        device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device2.scope['user'] = users[1]
        
        await device1.connect()
        response1 = await device1.receive_json_from()
        
        await device2.connect()
        response2 = await device2.receive_json_from()
        
        # Both should receive notifications
        assert response1['eventType'] == 'chat.notifications'
        assert response2['eventType'] == 'chat.notifications'
        assert len(response1['data']) > 0
        assert len(response2['data']) > 0
        
        await device1.disconnect()
        await device2.disconnect()

    async def test_disconnect_one_device_keeps_others_active(self, users, one_to_one_chat):
        """Test that disconnecting one device doesn't affect other devices"""
        # Connect 3 devices
        devices = []
        for i in range(3):
            device = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            device.scope['user'] = users[0]
            await device.connect()
            await device.receive_json_from()
            devices.append(device)
        
        # Disconnect first device
        await devices[0].disconnect()
        
        # Create message from another user
        sender = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        sender.scope['user'] = users[1]
        await sender.connect()
        await sender.receive_json_from()
        
        await sender.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Test after disconnect'
            }
        })
        
        await sender.receive_json_from()  # sender receives own message
        
        # Remaining 2 devices should still receive
        response1 = await devices[1].receive_json_from()
        response2 = await devices[2].receive_json_from()
        
        assert response1['eventType'] == 'message.dispatch'
        assert response2['eventType'] == 'message.dispatch'
        
        await devices[1].disconnect()
        await devices[2].disconnect()
        await sender.disconnect()

    async def test_active_sessions_tracking(self, users):
        """Test that active sessions are correctly tracked and retrieved"""
        from realtime_chat_messaging.utils.handlers import EventHandler
        
        # Connect 2 devices
        device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device1.scope['user'] = users[0]
        
        device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device2.scope['user'] = users[0]
        
        await device1.connect()
        await device1.receive_json_from()
        
        await device2.connect()
        await device2.receive_json_from()
        
        # Get active sessions
        active_sessions = await database_sync_to_async(
            EventHandler._get_active_sessions
        )(users[0].id)
        
        assert len(active_sessions) == 2
        
        await device1.disconnect()
        await device2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRoomAdditionBroadcast:
    """Test that being added to rooms broadcasts to all user's devices"""

    async def test_added_to_onetoonechat_all_devices_receive(self, users):
        """Test that when user is added to OneToOneChat, all their devices receive the event"""
        # User 1 connects from 3 devices
        user1_devices = []
        for i in range(3):
            device = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            device.scope['user'] = users[1]
            await device.connect()
            await device.receive_json_from()
            user1_devices.append(device)
        
        # User 0 creates a OneToOneChat with user 1
        creator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        creator.scope['user'] = users[0]
        
        await creator.connect()
        await creator.receive_json_from()
        
        await creator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'OneToOneChat',
                'participants': [users[1].id]
            }
        })
        
        # Creator receives room creation
        creator_response = await creator.receive_json_from()
        assert creator_response['eventType'] == 'roomcreate.dispatch'
        room_id = creator_response['data']['id']
        
        # All 3 devices of user 1 should receive the room creation event
        user1_responses = []
        for device in user1_devices:
            response = await device.receive_json_from()
            user1_responses.append(response)
        
        for response in user1_responses:
            assert response['eventType'] == 'roomcreate.dispatch'
            assert response['data']['id'] == room_id
            assert response['data']['type'] == 'OneToOneChat'
        
        # Verify all devices can now receive messages in this room
        await creator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Test message to all devices'
            }
        })
        
        await creator.receive_json_from()  # creator receives own message
        
        # All 3 devices should receive the message
        for device in user1_devices:
            message_response = await device.receive_json_from()
            assert message_response['eventType'] == 'message.dispatch'
            assert message_response['data']['content'] == 'Test message to all devices'
        
        await creator.disconnect()
        for device in user1_devices:
            await device.disconnect()

    async def test_added_to_groupchat_all_devices_receive(self, users, register_room_with_user):
        """Test that when user is added to GroupChat, all their devices receive the event"""
        # User 2 connects from 4 devices
        user2_devices = []
        for i in range(4):
            device = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            device.scope['user'] = users[2]
            await device.connect()
            await device.receive_json_from()
            user2_devices.append(device)
        
        # User 0 creates a group
        creator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        creator.scope['user'] = users[0]
        
        await creator.connect()
        await creator.receive_json_from()
        
        await creator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Test Group',
                'participants': [users[1].id]
            }
        })
        
        creator_response = await creator.receive_json_from()
        room_id = creator_response['data']['id']
        
        # Now add user 2 to the group
        await creator.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': room_id,
                'members': [users[2].id]
            }
        })
        
        await creator.receive_json_from()  # creator receives add members event
        
        # All 4 devices of user 2 should receive the add members event
        user2_responses = []
        for device in user2_devices:
            response = await device.receive_json_from()
            user2_responses.append(response)
        
        for response in user2_responses:
            assert response['eventType'] == 'roomaddmembers.dispatch'
            assert response['data']['room']['id'] == room_id
            assert 'user2' in response['data']['new_members']
        
        # Verify all devices can now participate in this room
        # Send a message from one device
        await user2_devices[0].send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Hello from device 1'
            }
        })
        
        # All devices should receive it
        for device in user2_devices:
            message_response = await device.receive_json_from()
            assert message_response['eventType'] == 'message.dispatch'
            assert message_response['data']['content'] == 'Hello from device 1'
        
        await creator.disconnect()
        for device in user2_devices:
            await device.disconnect()

    async def test_added_to_channel_all_devices_receive(self, users):
        """Test that when user is added to Channel, all their devices receive the event"""
        # User 3 connects from 2 devices
        user3_device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user3_device1.scope['user'] = users[3]
        
        user3_device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user3_device2.scope['user'] = users[3]
        
        await user3_device1.connect()
        await user3_device1.receive_json_from()
        
        await user3_device2.connect()
        await user3_device2.receive_json_from()
        
        # User 0 creates a channel
        creator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        creator.scope['user'] = users[0]
        
        await creator.connect()
        await creator.receive_json_from()
        
        await creator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'Channel',
                'name': 'Test Channel',
                'subscribers': [users[1].id]
            }
        })
        
        creator_response = await creator.receive_json_from()
        room_id = creator_response['data']['id']
        
        # Now add user 3 to the channel
        await creator.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': room_id,
                'members': [users[3].id]
            }
        })
        
        await creator.receive_json_from()  # creator receives add members event
        
        # Both devices of user 3 should receive the event
        device1_response = await user3_device1.receive_json_from()
        device2_response = await user3_device2.receive_json_from()
        
        assert device1_response['eventType'] == 'roomaddmembers.dispatch'
        assert device2_response['eventType'] == 'roomaddmembers.dispatch'
        assert device1_response['data']['room']['id'] == room_id
        assert device2_response['data']['room']['id'] == room_id
        assert 'user3' in device1_response['data']['new_members']
        assert 'user3' in device2_response['data']['new_members']
        
        # Verify both devices are in the channel layer group
        # Send a message from creator
        await creator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Channel announcement'
            }
        })
        
        await creator.receive_json_from()  # creator receives own message
        
        # Both devices should receive the message
        msg1 = await user3_device1.receive_json_from()
        msg2 = await user3_device2.receive_json_from()
        
        assert msg1['eventType'] == 'message.dispatch'
        assert msg2['eventType'] == 'message.dispatch'
        assert msg1['data']['content'] == 'Channel announcement'
        assert msg2['data']['content'] == 'Channel announcement'
        
        await creator.disconnect()
        await user3_device1.disconnect()
        await user3_device2.disconnect()

    async def test_join_public_channel_all_devices_added(self, users):
        """Test that when user joins public channel, all their devices are added to channel layer"""
        # User 0 creates a public channel
        creator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        creator.scope['user'] = users[0]
        
        await creator.connect()
        await creator.receive_json_from()
        
        await creator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'Channel',
                'name': 'Public Channel',
                'extra_fields': {
                    'is_public': True
                }
            }
        })
        
        creator_response = await creator.receive_json_from()
        room_id = creator_response['data']['id']
        
        # User 1 connects from 3 devices BEFORE joining
        user1_devices = []
        for i in range(3):
            device = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            device.scope['user'] = users[1]
            await device.connect()
            await device.receive_json_from()
            user1_devices.append(device)
        
        # User 1 joins from device 1
        await user1_devices[0].send_json_to({
            'event_type': 'room.join',
            'data': {
                'room_id': room_id
            }
        })
        
        # All 3 devices should receive the join event
        join_responses = []
        for device in user1_devices:
            response = await device.receive_json_from()
            join_responses.append(response)
        
        for response in join_responses:
            assert response['eventType'] == 'roomaddmembers.dispatch'
            assert response['data']['room']['id'] == room_id
            assert 'user1' in response['data']['new_members']
        
        # Verify all devices receive subsequent messages
        await creator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Welcome message'
            }
        })
        
        await creator.receive_json_from()  # creator's own message
        
        # All user 1 devices should receive it
        for device in user1_devices:
            msg = await device.receive_json_from()
            assert msg['eventType'] == 'message.dispatch'
            assert msg['data']['content'] == 'Welcome message'
        
        await creator.disconnect()
        for device in user1_devices:
            await device.disconnect()

    async def test_multiple_users_added_simultaneously_all_devices_updated(self, users):
        """Test that when multiple users are added simultaneously, all their devices receive events"""
        # User 0 creates a group
        creator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        creator.scope['user'] = users[0]
        
        await creator.connect()
        await creator.receive_json_from()
        
        await creator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Multi-User Group'
            }
        })
        
        creator_response = await creator.receive_json_from()
        room_id = creator_response['data']['id']
        
        # Connect multiple devices for users 1, 2, and 3
        user_devices = {
            1: [],
            2: [],
            3: []
        }
        
        for user_idx in [1, 2, 3]:
            for device_idx in range(2):  # 2 devices per user
                device = WebsocketCommunicator(
                    ChatMessagingConsumer.as_asgi(),
                    "/messaging/"
                )
                device.scope['user'] = users[user_idx]
                await device.connect()
                await device.receive_json_from()
                user_devices[user_idx].append(device)
        
        # Add all 3 users at once
        await creator.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': room_id,
                'members': [users[1].id, users[2].id, users[3].id]
            }
        })
        
        await creator.receive_json_from()  # creator receives event
        
        # All devices of all 3 users should receive the event
        for user_idx in [1, 2, 3]:
            for device in user_devices[user_idx]:
                response = await device.receive_json_from()
                assert response['eventType'] == 'roomaddmembers.dispatch'
                assert response['data']['room']['id'] == room_id
                assert f'user{user_idx}' in response['data']['new_members']
        
        # Verify all devices can participate
        # User 1, device 1 sends a message
        await user_devices[1][0].send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Message from user 1'
            }
        })
        
        # All devices of all users should receive it
        for user_idx in [1, 2, 3]:
            for device in user_devices[user_idx]:
                msg = await device.receive_json_from()
                assert msg['eventType'] == 'message.dispatch'
                assert msg['data']['content'] == 'Message from user 1'
        
        await creator.disconnect()
        for user_idx in [1, 2, 3]:
            for device in user_devices[user_idx]:
                await device.disconnect()

    async def test_device_connected_after_room_addition_receives_messages(self, users):
        """Test that device connected AFTER user was added to room still receives messages"""
        # User 0 creates a group and adds user 1
        creator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        creator.scope['user'] = users[0]
        # User 1 connects device 1
        device1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device1.scope['user'] = users[1]
        

        await creator.connect()
        await creator.receive_json_from()

        await device1.connect()
        await device1.receive_json_from()  # receives notifications
        
        
        await creator.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Test Group',
                'participants': [users[1].id]
            }
        })
        
        creator_response = await creator.receive_json_from()
        room_id = creator_response['data']['id']
        

        
        # Device 1 receives the room creation event
        room_create_event = await device1.receive_json_from()
        assert room_create_event['eventType'] == 'roomcreate.dispatch'
        
        # Now user 1 connects device 2 (after already being in the room)
        device2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        device2.scope['user'] = users[1]
        
        await device2.connect()
        await device2.receive_json_from()  # receives notifications
        
        # Send a message
        await creator.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Test message'
            }
        })
        
        await creator.receive_json_from()  # creator receives own message
        
        # BOTH devices should receive the message
        msg1 = await device1.receive_json_from()
        msg2 = await device2.receive_json_from()
        
        assert msg1['eventType'] == 'message.dispatch'
        assert msg2['eventType'] == 'message.dispatch'
        assert msg1['data']['content'] == 'Test message'
        assert msg2['data']['content'] == 'Test message'
        
        await creator.disconnect()
        await device1.disconnect()
        await device2.disconnect()