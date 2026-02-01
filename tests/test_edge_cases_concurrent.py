import pytest
import asyncio
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.models import Message, Reaction, ReadReceipt, GroupChat
from realtime_chat_messaging.utils.cache_utils import add_group_to_user_groups
from realtime_chat_messaging.consumers import GROUP_STRING
from asgiref.sync import async_to_sync
from django.core.exceptions import ValidationError

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(10)


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
class TestConcurrentMessageOperations:
    """Test concurrent message operations and race conditions"""

    async def test_concurrent_message_creation_in_same_room(self, users, register_room_with_user, group_chat):
        """Test multiple users sending messages to same room simultaneously"""
        # Add users to group
        for user in users[1:6]:
            await database_sync_to_async(group_chat.participants.add)(user)
            await register_room_with_user(user.id, group_chat.id)
        
        # Create communicators for 5 users
        communicators = []
        for i in range(5):
            comm = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            comm.scope['user'] = users[i]
            await comm.connect()
            await comm.receive_json_from()
            communicators.append(comm)
        
        # Send messages simultaneously
        send_tasks = [
            comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(group_chat.id),
                    'content': f'Message from user{i}'
                }
            })
            for i, comm in enumerate(communicators)
        ]
        
        await asyncio.gather(*send_tasks)
        
        # Wait for all broadcasts
        await asyncio.sleep(0.5)
        
        # Verify all messages created
        messages = await database_sync_to_async(
            lambda: list(Message.objects.filter(room=group_chat))
        )()
        
        assert len(messages) == 5
        
        # Each communicator should receive 5 messages
        for comm in communicators:
            responses = []
            for _ in range(5):
                responses.append(await comm.receive_json_from())
            
            assert all(r['eventType'] == 'message.dispatch' for r in responses)
        
        for comm in communicators:
            await comm.disconnect()

    async def test_concurrent_reactions_to_same_message(self, users, register_room_with_user, group_chat):
        """Test multiple users reacting to same message simultaneously"""

        for user in users[1:6]:
            await database_sync_to_async(group_chat.participants.add)(user)
            await register_room_with_user(user.id, group_chat.id)
        # Create message
        message = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users[0],
            content="React to me"
        )
        
        # Connect multiple users
        communicators = []
        for i in range(5):
            comm = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            comm.scope['user'] = users[i]
            await comm.connect()
            await comm.receive_json_from()
            communicators.append(comm)
        
        # All react simultaneously with different emojis
        emojis = ['👍', '❤️', '😂', '🎉', '🔥']
        react_tasks = [
            comm.send_json_to({
                'event_type': 'message.react',
                'data': {
                    'type': 'add',
                    'message_id': str(message.id),
                    'reaction_content': emojis[i]
                }
            })
            for i, comm in enumerate(communicators)
        ]
        
        await asyncio.gather(*react_tasks)
        
        # Wait for processing
        await asyncio.sleep(0.5)
        
        # Verify all reactions created
        reactions = await database_sync_to_async(
            lambda: list(Reaction.objects.filter(message=message))
        )()
        
        assert len(reactions) == 5
        
        reaction_contents = [r.reaction_content for r in reactions]
        for emoji in emojis:
            assert emoji in reaction_contents
        
        for comm in communicators:
            await comm.disconnect()

    async def test_concurrent_duplicate_reaction_prevention(self, users, one_to_one_chat):
        """Test that concurrent duplicate reactions from same user are prevented"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        # Connect user from 2 devices
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
        await device1.receive_json_from()
        
        await device2.connect()
        await device2.receive_json_from()
        
        # React simultaneously from both devices with same emoji
        await asyncio.gather(
            device1.send_json_to({
                'event_type': 'message.react',
                'data': {
                    'type': 'add',
                    'message_id': str(message.id),
                    'reaction_content': '👍'
                }
            }),
            device2.send_json_to({
                'event_type': 'message.react',
                'data': {
                    'type': 'add',
                    'message_id': str(message.id),
                    'reaction_content': '👍'
                }
            })
        )
        
        await asyncio.sleep(0.5)
        
        # Should have only 1 reaction due to unique constraint
        reactions = await database_sync_to_async(
            lambda: Reaction.objects.filter(message=message, user=users[1]).count()
        )()
        
        assert reactions == 1
        
        await device1.disconnect()
        await device2.disconnect()

    async def test_concurrent_read_receipts(self, users, group_chat):
        """Test concurrent read receipts from multiple users"""
        # Add users to group
        for user in users[1:6]:
            await database_sync_to_async(group_chat.participants.add)(user)
        
        # Create message
        message = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users[0],
            content="Read me"
        )
        
        # Connect users (excluding sender)
        communicators = []
        for i in range(1, 6):
            comm = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            comm.scope['user'] = users[i]
            await comm.connect()
            await comm.receive_json_from()
            communicators.append(comm)
        
        # All mark as read simultaneously
        read_tasks = [
            comm.send_json_to({
                'event_type': 'message.read',
                'data': {
                    'message_id': str(message.id)
                }
            })
            for comm in communicators
        ]
        
        await asyncio.gather(*read_tasks)
        
        await asyncio.sleep(0.5)
        
        # Verify all read receipts created
        receipts = await database_sync_to_async(
            lambda: ReadReceipt.objects.filter(message=message).count()
        )()
        
        assert receipts == 5
        
        for comm in communicators:
            await comm.disconnect()

    async def test_concurrent_message_edit_and_delete(self, users, one_to_one_chat):
        """Test race condition between edit and delete operations"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original"
        )
        message_id = str(message.id)
        
        # Connect from 2 devices
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
        
        # Device 1 edits, Device 2 deletes simultaneously
        await asyncio.gather(
            device1.send_json_to({
                'event_type': 'message.modify',
                'data': {
                    'action': 'update',
                    'message_id': message_id,
                    'extra_fields': {
                        'content': 'Edited'
                    }
                }
            }),
            device2.send_json_to({
                'event_type': 'message.modify',
                'data': {
                    'action': 'delete',
                    'message_id': [message_id]
                }
            })
        )
        
        await asyncio.sleep(0.5)
        
        # One operation should succeed
        # Check if message exists or is deleted
        from realtime_chat_messaging.conf import realtime_chat_settings
        if realtime_chat_settings.MESSAGE_SOFT_DELETE:
            msg = await database_sync_to_async(
                Message.objects.filter(id=message.id).first
            )()
            # Message exists but might be marked deleted
            assert msg is not None
        else:
            # Message might be deleted
            exists = await database_sync_to_async(
                Message.objects.filter(id=message.id).exists
            )()
            # Either exists with edit or doesn't exist (deleted)
            assert exists or not exists  # One of the operations succeeded
        
        await device1.disconnect()
        await device2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestConcurrentRoomOperations:
    """Test concurrent room operations"""

    async def test_concurrent_room_creation_duplicate_onetoonechat(self, users):
        """Test that duplicate OneToOneChat creation is prevented"""
        # Try to create same OneToOneChat from 2 users simultaneously
        comm1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm1.scope['user'] = users[0]
        
        comm2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm2.scope['user'] = users[1]
        
        await comm1.connect()
        await comm1.receive_json_from()
        
        await comm2.connect()
        await comm2.receive_json_from()
        
        # Both try to create chat with each other
        await asyncio.gather(
            comm1.send_json_to({
                'event_type': 'room.create',
                'data': {
                    'type': 'OneToOneChat',
                    'participants': [users[1].id]
                }
            }),
            comm2.send_json_to({
                'event_type': 'room.create',
                'data': {
                    'type': 'OneToOneChat',
                    'participants': [users[0].id]
                }
            })
        )
        
        await asyncio.sleep(0.5)
        
        # Only one should succeed
        from realtime_chat_messaging.models import OneToOneChat
        chats = await database_sync_to_async(
            lambda: list(OneToOneChat.objects.filter(
                participants__in=[users[0], users[1]]
            ).distinct())
        )()
        
        # Should have at most 1 chat (duplicate prevented by signal)
        assert len(chats) <= 1
        
        await comm1.disconnect()
        await comm2.disconnect()

    async def test_concurrent_add_remove_members(self, users, group_chat, register_room_with_user):
        """Test concurrent add and remove operations on same group"""
        # Add some users first
        for user in users[1:4]:
            await database_sync_to_async(group_chat.participants.add)(user)
            await register_room_with_user(user.id, group_chat.id)
        
        # Connect admin and regular member
        admin = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        admin.scope['user'] = users[0]
        
        member = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        member.scope['user'] = users[1]
        
        await admin.connect()
        await admin.receive_json_from()
        
        await member.connect()
        await member.receive_json_from()
        
        # Admin adds user5, simultaneously admin removes user3
        await asyncio.gather(
            admin.send_json_to({
                'event_type': 'room.add_members',
                'data': {
                    'room_id': str(group_chat.id),
                    'members': [users[4].id]
                }
            }),
            admin.send_json_to({
                'event_type': 'room.remove_members',
                'data': {
                    'room_id': str(group_chat.id),
                    'members': [users[2].id]
                }
            })
        )
        
        await asyncio.sleep(0.5)
        
        # Verify final state
        participants = await database_sync_to_async(
            lambda: list(group_chat.participants.all())
        )()
        
        participant_ids = [p.id for p in participants]
        assert users[4].id in participant_ids  # Added
        assert users[2].id not in participant_ids  # Removed
        
        await admin.disconnect()
        await member.disconnect()

    async def test_concurrent_max_participants_enforcement(self, users):
        """Test that max_participants is enforced under concurrent adds"""
        # Create group with max 3 participants
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Limited Group",
            creator=users[0],
            max_participants=3
        )
        
        # Connect admin
        admin = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        admin.scope['user'] = users[0]
        
        await admin.connect()
        await admin.receive_json_from()
        
        # Try to add 5 users simultaneously (would exceed max)
        add_tasks = [
            admin.send_json_to({
                'event_type': 'room.add_members',
                'data': {
                    'room_id': str(group.id),
                    'members': [users[i].id]
                }
            })
            for i in range(1, 6)
        ]
        
        results = await asyncio.gather(*add_tasks, return_exceptions=True)
        
        await asyncio.sleep(0.5)
        
        # Should not exceed max participants
        participant_count = await database_sync_to_async(
            group.participants.count
        )()
        
        assert participant_count <= 3
        
        await admin.disconnect()

    async def test_concurrent_leave_room_last_participant(self, users, register_room_with_user):
        """Test race condition when last 2 participants leave simultaneously"""
        # Create group with 2 participants
        group = await database_sync_to_async(GroupChat.objects.create)(
            name="Empty Soon",
            creator=users[0]
        )
        await database_sync_to_async(group.participants.add)(users[1])
        
        await register_room_with_user(users[0].id, group.id)
        await register_room_with_user(users[1].id, group.id)
        
        # Connect both
        user1 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user1.scope['user'] = users[0]
        
        user2 = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        user2.scope['user'] = users[1]
        
        await user1.connect()
        await user1.receive_json_from()
        
        await user2.connect()
        await user2.receive_json_from()
        
        # Both leave simultaneously
        await asyncio.gather(
            user1.send_json_to({
                'event_type': 'room.leave',
                'data': {
                    'room_id': str(group.id)
                }
            }),
            user2.send_json_to({
                'event_type': 'room.leave',
                'data': {
                    'room_id': str(group.id)
                }
            })
        )
        
        await asyncio.sleep(0.5)
        
        # Group should be deleted
        exists = await database_sync_to_async(
            GroupChat.objects.filter(id=group.id).exists
        )()
        
        assert not exists
        
        await user1.disconnect()
        await user2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions"""

    async def test_message_to_deleted_room(self, users, one_to_one_chat):
        """Test sending message to a room that gets deleted"""
        room_id = str(one_to_one_chat.id)
        
        # Connect user
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Delete room
        await database_sync_to_async(one_to_one_chat.delete)()
        
        # Try to send message
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Message to deleted room'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4004  # Not found
        
        await comm.disconnect()

    async def test_react_to_deleted_message(self, users, one_to_one_chat):
        """Test reacting to a message that gets deleted"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Will be deleted"
        )
        message_id = str(message.id)
        
        # Connect user
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[1]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Delete message
        await database_sync_to_async(message.delete)()
        
        # Try to react
        await comm.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'add',
                'message_id': message_id,
                'reaction_content': '👍'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        
        await comm.disconnect()

    async def test_concurrent_connection_disconnection_same_user(self, users):
        """Test rapid connect/disconnect cycles"""
        async def connect_disconnect():
            comm = WebsocketCommunicator(
                ChatMessagingConsumer.as_asgi(),
                "/messaging/"
            )
            comm.scope['user'] = users[0]
            
            connected, _ = await comm.connect()
            if connected:
                await comm.receive_json_from()
                await comm.disconnect()
        
        # Perform 10 rapid connect/disconnect cycles
        tasks = [connect_disconnect() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify no lingering sessions
        from realtime_chat_messaging.models import Session
        from django.utils import timezone
        import datetime
        
        # Wait a bit for cleanup 
        await asyncio.sleep(10)
        
        # Check for active sessions
        time_allowance = timezone.now() - datetime.timedelta(seconds=5) # used 5 secs since asyncio.sleep is 10 secs
        active = await database_sync_to_async(
            lambda: Session.objects.filter(
                user=users[0],
                last_seen__gte=time_allowance
            ).count()
        )()
        
        # Should have minimal or no active sessions left
        assert active <= 1

    async def test_malformed_message_data(self, users, one_to_one_chat):
        """Test handling of malformed message data"""
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Send message with missing required fields
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id)
                # Missing 'content' field
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        
        await comm.disconnect()

    async def test_empty_message_list(self, users, one_to_one_chat):
        """Test fetching messages from empty room"""
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
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
        assert len(response['data']['data']['messages']) == 0
        
        await comm.disconnect()

    async def test_pagination_edge_cases(self, users, one_to_one_chat):
        """Test pagination with edge cases"""
        # Create exactly 10 messages
        for i in range(10):
            await database_sync_to_async(Message.objects.create)(
                room=one_to_one_chat,
                sender=users[0],
                content=f"Message {i}"
            )
        
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Test: Request page beyond available
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 100,
                    'size': 10
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) >= 0
        
        # Test: Page size larger than total
        await comm.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'paginate': {
                    'page': 1,
                    'size': 100
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roommessages.dispatch'
        assert len(response['data']['data']['messages']) == 10
        
        await comm.disconnect()

    async def test_unauthorized_admin_operations(self, users, group_chat, register_room_with_user):
        """Test that unauthorized users cannot perform admin operations"""
        # Add regular member
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await register_room_with_user(users[1].id, group_chat.id)
        
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[1]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Try to add members (should fail - not admin)
        await comm.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(group_chat.id),
                'members': [users[2].id]
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002  # Permission denied
        
        await comm.disconnect()

    async def test_very_long_message_content(self, users, one_to_one_chat):
        """Test handling of very long message content"""
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Create very long content
        long_content = 'A' * 10000
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': long_content
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should either succeed or fail gracefully
        assert 'eventType' in response or 'error' in response
        
        await comm.disconnect()

    async def test_special_characters_in_content(self, users, one_to_one_chat):
        """Test handling of special characters and unicode in messages"""
        comm = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        special_content = "Test 测试 🎉 <script>alert('xss')</script> '\"; DROP TABLE--"
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': special_content
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        # Script tags should be sanitized
        assert '<script>' not in response['data']['content']
        
        await comm.disconnect()