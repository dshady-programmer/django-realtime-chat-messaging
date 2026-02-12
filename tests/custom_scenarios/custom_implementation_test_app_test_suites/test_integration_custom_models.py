"""
Integration tests using custom models, serializers, and handlers.
Tests that the ENTIRE application flow works with swapped implementations.
Focus: Consumer events should work seamlessly with custom components.
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from realtime_chat_messaging.utils.cache_utils import add_group_to_user_groups
from realtime_chat_messaging.consumers import GROUP_STRING
from asgiref.sync import async_to_sync

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(10)

@pytest.fixture
def one_to_one_chat(users, register_room_with_user, create_one_to_one_chat):
    """Create a one-to-one chat"""
    room = create_one_to_one_chat(users[0], users[1])
    async_to_sync(register_room_with_user)(users[0].id, room.id)
    async_to_sync(register_room_with_user)(users[1].id, room.id)
    return room


@pytest.fixture
def register_room_with_user():
    async def _register_room(user_id, room_id):
        group = GROUP_STRING.format(group_id=room_id)
        await add_group_to_user_groups(user_id, group)
    return _register_room





# ==================== INTEGRATION TESTS WITH CUSTOM MESSAGE MODEL ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestConsumerWithCustomMessage:
    """Test all consumer message events work with custom Message model"""
    
    async def test_message_send_with_custom_model(self, users, one_to_one_chat):
        """Test message.send event with CustomMessage model"""

        sender = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        sender.scope['user'] = users[0]
        
        receiver = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        receiver.scope['user'] = users[1]
        
        await sender.connect()
        await sender.receive_json_from()
        
        await receiver.connect()
        await receiver.receive_json_from()
        
        # Send message
        await sender.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Test with custom message model',
                'extra_fields': {
                    'priority': 'urgent'  # Custom field
                }
            }
        })
        
        sender_response = await sender.receive_json_from()
        receiver_response = await receiver.receive_json_from()
        
        assert sender_response['eventType'] == 'message.dispatch'
        assert receiver_response['eventType'] == 'message.dispatch'
        assert sender_response['data']['content'] == 'Test with custom message model'
        
        # Verify custom model was used
        from custom_implementation_test_app.models import CustomMessage
        message = await database_sync_to_async(
            CustomMessage.objects.filter(content='Test with custom message model').first
        )()
        assert message is not None
        assert message.priority == 'urgent'
        
        await sender.disconnect()
        await receiver.disconnect()

    
    async def test_message_edit_with_custom_model(self, users, one_to_one_chat):
        """Test message.modify (edit) with CustomMessage model"""
        from custom_implementation_test_app.models import CustomMessage
        
        
        
        # Create message with custom model
        message = await database_sync_to_async(CustomMessage.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Original",
            priority="normal"
        )
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        await comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': str(message.id),
                'extra_fields': {
                    'content': 'Edited content',
                    'priority': 'high'  # Edit custom field as well
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['message']['content'] == 'Edited content'
        
        await comm.disconnect()


# ==================== STRESS TESTS WITH ALL CUSTOM COMPONENTS ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestCompleteCustomStack:
    """Test entire application with ALL custom components"""
    
    async def test_complete_custom_stack_integration(self, users):
        """
        Ultimate integration test: ALL components are custom
        Tests: Custom models + serializers + handlers + permissions
        """
        from custom_implementation_test_app.models import (
            CustomMessage, CustomGroupChat, CustomSession,
        )

        
        # Step 1: Connect users (CustomSession)
        user1 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        user1.scope['user'] = users[0]
        
        user2 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        user2.scope['user'] = users[1]
        
        user3 = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        user3.scope['user'] = users[2]
        
        await user1.connect()
        await user1.receive_json_from()
        
        await user2.connect()
        await user2.receive_json_from()
        
        await user3.connect()
        await user3.receive_json_from()
        
        # Verify CustomSession created
        sessions = await database_sync_to_async(
            lambda: CustomSession.objects.count()
        )()
        assert sessions == 3
        
        # Step 2: Create room (CustomGroupChat + CustomEventHandler)
        await user1.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'CustomGroupChat',
                'name': 'Full Custom Stack Test',
                'participants': [users[1].id, users[2].id],
                'extra_fields': {
                    'tags': ['custom', 'integration', 'test']
                }
            }
        })
        
        room_response1 = await user1.receive_json_from()

        room_response2 = await user2.receive_json_from()
        room_response3 = await user3.receive_json_from()
        assert room_response1['eventType'] == 'roomcreate.dispatch'
        assert room_response2['eventType'] == 'roomcreate.dispatch'
        assert room_response3['eventType'] == 'roomcreate.dispatch'
        
        room_id = room_response1['data']['id']
        
        # Verify CustomGroupChat with tags
        group = await database_sync_to_async(
            CustomGroupChat.objects.filter(id=room_id).first
        )()
        assert group is not None
        assert group.tags == ['custom', 'integration', 'test']
        
        # Step 3: Send message (CustomMessage + CustomMessageSerializer)
        await user1.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Testing complete custom stack',
                'extra_fields': {
                    'priority': 'critical',
                    'metadata': {
                        'test_type': 'integration',
                        'custom_field': True
                    }
                }
            }
        })
        
        msg1 = await user1.receive_json_from()
        msg2 = await user2.receive_json_from()
        msg3 = await user3.receive_json_from()
        
        assert msg1['eventType'] == 'message.dispatch'
        assert msg2['eventType'] == 'message.dispatch'
        assert msg3['eventType'] == 'message.dispatch'
        
        message_id = msg1['data']['id']
        
        # Verify CustomMessage with custom fields
        message = await database_sync_to_async(
            CustomMessage.objects.filter(id=message_id).first
        )()
        assert message is not None
        assert message.priority == 'critical'
        assert message.metadata['test_type'] == 'integration'
        
        # Step 4: React (CustomPermissionHandler checks)
        await user2.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'add',
                'message_id': message_id,
                'reaction_content': '🚀'
            }
        })
        
        await user1.receive_json_from()
        await user2.receive_json_from()
        await user3.receive_json_from()
        
        # Step 5: Edit message
        await user1.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'update',
                'message_id': message_id,
                'extra_fields': {
                    'content': 'Edited with custom stack'
                }
            }
        })
        
        edit1 = await user1.receive_json_from()
        edit2 = await user2.receive_json_from()
        edit3 = await user3.receive_json_from()
        
        assert edit1['eventType'] == edit2['eventType'] == edit3['eventType'] == 'messagemodification.dispatch'
        assert edit1['data']['message']['content'] == edit2['data']['message']['content']  == edit3['data']['message']['content'] == 'Edited with custom stack'
        
        # Step 6: Add members (CustomPermissionHandler)
        await user1.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': room_id,
                'members': [users[3].id]
            }
        })
        
        add1 = await user1.receive_json_from()
        add2 = await user2.receive_json_from()
        add3 = await user3.receive_json_from()
        
        assert add1['eventType'] == add2['eventType'] == add3['eventType'] == 'roomaddmembers.dispatch'
        assert 'user3' in add1['data']['new_members'] and 'user3' in add2['data']['new_members'] and 'user3' in add3['data']['new_members']

        # Step 7: Fetch room messages
        await user2.send_json_to({
            'event_type': 'room.messages',
            'data': {
                'room_id': room_id,
                'paginate': {
                    'page': 1,
                    'size': 10
                }
            }
        })
        
        messages_response = await user2.receive_json_from()
        
        assert messages_response['eventType'] == 'roommessages.dispatch'
        assert len(messages_response['data']['data']['messages']) >= 1
        
        # Step 8: Room info (CustomGroupChatSerializer)
        await user1.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': room_id
            }
        })
        
        info_response = await user1.receive_json_from()
        
        assert info_response['eventType'] == 'roominfo.dispatch'
        assert info_response['data']['id'] == room_id
        assert info_response['data']['type'] == "CustomGroupChat"
        
        # Step 9: List rooms
        await user1.send_json_to({
            'event_type': 'room.list',
            'data': {}
        })
        
        list_response = await user1.receive_json_from()
        
        assert list_response['eventType'] == 'roomlist.dispatch'
        assert len(list_response['data']) >= 1
        
        # Step 10: Typing indicator
        await user2.send_json_to({
            'event_type': 'message.typing',
            'data': {
                'room_id': room_id
            }
        })
        
        typing1 = await user1.receive_json_from()
        typing2 = await user2.receive_json_from()
        typing3 = await user3.receive_json_from()
        
        assert typing1['eventType'] == typing2['eventType'] == typing3['eventType'] == 'messagetyping.dispatch'
        
        # Cleanup
        await user1.disconnect()
        await user2.disconnect()
        await user3.disconnect()
        
    
    async def test_custom_stack_with_concurrent_users(self, users):
        """Test custom stack with 10 concurrent users"""

        from custom_implementation_test_app.models  import CustomSession
        

        
        # Connect 10 users
        communicators = []
        for i in range(10):
            comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            comm.scope['user'] = users[i]
            await comm.connect()
            await comm.receive_json_from()
            communicators.append(comm)
        
        # Verify 10 sessions
        sessions = await database_sync_to_async(
            lambda: CustomSession.objects.count()
        )()
        assert sessions == 10
        
        # User 0 creates room with all users
        participant_ids = [users[i].id for i in range(1, 10)]
        await communicators[0].send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Large Group Test',
                'participants': participant_ids,
                'extra_fields': {
                    'tags': ['large', 'test']
                }
            }
        })
        
        # All receive room creation
        responses = []
        for comm in communicators:
            response = await comm.receive_json_from()
            responses.append(response)
        
        assert all(r['eventType'] == 'roomcreate.dispatch' for r in responses)
        room_id = responses[0]['data']['id']
        
        # All users send messages
        for i, comm in enumerate(communicators):
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': room_id,
                    'content': f'Message {i}',
                    'priority': 'normal' if i % 2 == 0 else 'urgent'
                }
            })
        
        # Each user receives 10 messages
        for comm in communicators:
            for _ in range(10):
                msg = await comm.receive_json_from()
                assert msg['eventType'] == 'message.dispatch'
        
        for comm in communicators:
            await comm.disconnect()

    
    async def test_custom_stack_error_handling(self, users):
        """Test that errors are handled correctly with custom stack"""

        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Test invalid room ID
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': 'invalid-uuid-format',
                'content': 'Test'
            }
        })
        
        error_response = await comm.receive_json_from()
        assert 'error' in error_response
        
        # Test unauthorized access
        await comm.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': '00000000-0000-0000-0000-000000000000'
            }
        })
        
        error_response2 = await comm.receive_json_from()
        assert 'error' in error_response2
        assert error_response2['error']['code'] == 4004
        
        await comm.disconnect()
   


# ==================== BACKWARD COMPATIBILITY TESTS ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestBackwardCompatibilityWithCustomModels:
    """Test that custom models maintain backward compatibility with existing features"""
   
    
    async def test_polymorphic_serialization_with_custom_models(self, users):
        """Test polymorphic serialization works with mixed default and custom models"""
        from realtime_chat_messaging.models import OneToOneChat
        from custom_implementation_test_app.models  import CustomGroupChat
        from realtime_chat_messaging.serializers import RoomListPolymorphicSerializer
        
        # Create OneToOneChat (default model)
        chat = await database_sync_to_async(OneToOneChat.objects.create)()
        await database_sync_to_async(chat.participants.set)([users[0], users[1]])
        
        # Create CustomGroupChat
        group = await database_sync_to_async(CustomGroupChat.objects.create)(
            name="Mixed Test",
            creator=users[0],
            tags=['mixed']
        )
        
        # Get both rooms
        from realtime_chat_messaging.models import Room
        rooms = await database_sync_to_async(
            lambda: list(Room.objects.filter(id__in=[chat.id, group.id]))
        )()
        
        # Serialize both
        serializer = RoomListPolymorphicSerializer(rooms, many=True, context={'user': users[0]})
        data = await database_sync_to_async(lambda: serializer.data)()
        
        assert len(data) == 2
        types = [r['type'] for r in data]
        assert 'OneToOneChat' in types
        assert 'CustomGroupChat' in types


# ==================== PERFORMANCE TESTS WITH CUSTOM MODELS ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceWithCustomModels:
    """Test performance isn't degraded with custom models"""
    
    async def test_bulk_message_creation_with_custom_model(self, users, one_to_one_chat):
        """Test creating many messages with custom model"""

        from custom_implementation_test_app.models import CustomMessage
  
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Send 50 messages
        for i in range(50):
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': str(one_to_one_chat.id),
                    'content': f'Message {i}',
                    'priority': 'normal'
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

    
    async def test_many_concurrent_sessions_with_custom_model(self, users):
        """Test many concurrent sessions with CustomSession"""

        from custom_implementation_test_app.models  import CustomSession

        # Create 20 sessions (4 per user for 5 users)
        communicators = []
        for user_idx in range(5):
            for device_idx in range(4):
                comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
                comm.scope['user'] = users[user_idx]
                await comm.connect()
                await comm.receive_json_from()
                communicators.append(comm)
        
        # Verify 20 sessions
        sessions = await database_sync_to_async(
            lambda: CustomSession.objects.count()
        )()
        assert sessions == 20
        
        for comm in communicators:
            await comm.disconnect()
        


    
    async def test_message_delete_with_custom_model(self, users, one_to_one_chat):
        """Test message.modify (delete) with CustomMessage model"""
 
        from custom_implementation_test_app.models  import CustomMessage
        

        
        message = await database_sync_to_async(CustomMessage.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="To delete",
            priority="low"
        )
        message_id = str(message.id)
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.modify',
            'data': {
                'action': 'delete',
                'message_id': [message_id]
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'messagemodification.dispatch'
        assert response['data']['action'] == 'delete'
        assert message_id in response['data']['message_ids']
        
        await comm.disconnect()

    async def test_message_react_with_custom_model(self, users, one_to_one_chat):
        """Test message.react with CustomMessage model"""

        from custom_implementation_test_app.models import CustomMessage

   
        message = await database_sync_to_async(CustomMessage.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="React to this",
            priority="high"
        )
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[1]
        
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'add',
                'message_id': str(message.id),
                'reaction_content': '👍'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'reaction.dispatch'
        assert response['data']['status'] == 'successful'
        
        await comm.disconnect()
        
    
    async def test_message_read_with_custom_model(self, users, one_to_one_chat):
        """Test message.read with CustomMessage model"""

        from custom_implementation_test_app.models  import CustomMessage
        

        

        
        message = await database_sync_to_async(CustomMessage.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Mark as read",
            metadata={"important": True}
        )
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[1]
        
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': str(message.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'readreceipt.dispatch'
        
        await comm.disconnect()
        
    
    async def test_room_messages_with_custom_model(self, users, one_to_one_chat):
        """Test room.messages retrieval with CustomMessage model"""

        from custom_implementation_test_app.models import CustomMessage
        

        # Create messages with custom model
        for i in range(5):
            await database_sync_to_async(CustomMessage.objects.create)(
                room=one_to_one_chat,
                sender=users[0],
                content=f"Message {i}",
                priority="normal" if i % 2 == 0 else "urgent"
            )
        
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
        assert len(response['data']['data']['messages']) == 5
        
        await comm.disconnect()
        


# ==================== INTEGRATION TESTS WITH CUSTOM SESSION MODEL ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestConsumerWithCustomSession:
    """Test consumer connection/session management with custom Session model"""
    
    async def test_connection_with_custom_session(self, users):
        """Test WebSocket connection creates CustomSession"""

        from custom_implementation_test_app.models import CustomSession
        
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Verify CustomSession was created
        sessions = await database_sync_to_async(
            lambda: list(CustomSession.objects.filter(user=users[0]))
        )()
        
        assert len(sessions) == 1
        assert hasattr(sessions[0], 'device_type')
        assert hasattr(sessions[0], 'ip_address')
        
        await comm.disconnect()
        

    async def test_multiple_sessions_with_custom_model(self, users):
        """Test concurrent connections with CustomSession"""

        from custom_implementation_test_app.models import CustomSession
        
        devices = []
        for i in range(3):
            device = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            device.scope['user'] = users[0]
            await device.connect()
            await device.receive_json_from()
            devices.append(device)
        
        sessions = await database_sync_to_async(
            lambda: list(CustomSession.objects.filter(user=users[0]))
        )()
        
        assert len(sessions) == 3
        
        for device in devices:
            await device.disconnect()
        


# ==================== INTEGRATION TESTS WITH CUSTOM GROUPCHAT MODEL ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestConsumerWithCustomGroupChat:
    """Test all room operations work with custom GroupChat model"""
    
    async def test_room_create_groupchat_with_custom_model(self, users):
        """Test room.create for GroupChat with custom model"""
  
        from custom_implementation_test_app.models import CustomGroupChat

        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Custom Group',
                'participants': [users[1].id, users[2].id],
                'extra_fields': {
                    'tags': ['work', 'urgent']  # Custom field
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomcreate.dispatch'
        assert response['data']['name'] == 'Custom Group'
        
        # Verify custom model was used
        group = await database_sync_to_async(
            CustomGroupChat.objects.filter(name='Custom Group').first
        )()
        assert group is not None
        assert group.tags == ['work', 'urgent']
        
        await comm.disconnect()

    
    async def test_room_add_members_with_custom_model(self, users, register_room_with_user):
        """Test room.add_members with CustomGroupChat"""

        from custom_implementation_test_app.models import CustomGroupChat

        
        group = await database_sync_to_async(CustomGroupChat.objects.create)(
            name="Test Group",
            creator=users[0],
            tags=['test']
        )

        # add creator to group
        await database_sync_to_async(group.participants.add)(users[0])
        await register_room_with_user(users[0].id, group.id)
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(group.id),
                'members': [users[1].id, users[2].id]
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user1' in response['data']['new_members']
        assert 'user2' in response['data']['new_members']
        
        await comm.disconnect()
        

    
    async def test_room_modify_with_custom_model(self, users, register_room_with_user):
        """Test room.modify with CustomGroupChat"""

        from custom_implementation_test_app.models import CustomGroupChat

        
        group = await database_sync_to_async(CustomGroupChat.objects.create)(
            name="Original Name",
            creator=users[0],
            tags=['old']
        )

        # add creator to group
        await database_sync_to_async(group.participants.add)(users[0])
        await register_room_with_user(users[0].id, group.id)

        
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
                    'name': 'Updated Name',
                    'description': 'New description'
                }
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomupdate.dispatch'
        assert response['data']['name'] == 'Updated Name'
        
        await comm.disconnect()
        
 


# ==================== INTEGRATION TESTS WITH MULTIPLE CUSTOM MODELS ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestConsumerWithMultipleCustomModels:
    """Test entire consumer flow with multiple custom models"""
    
    async def test_complete_flow_with_all_custom_models(self, users):
        """Test complete messaging flow: create room → send message → react → read"""

        from custom_implementation_test_app.models import CustomMessage, CustomGroupChat, CustomSession
        
        
        # Connect users (creates CustomSession)
        user1_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        user1_comm.scope['user'] = users[0]
        
        user2_comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        user2_comm.scope['user'] = users[1]
        
        await user1_comm.connect()
        await user1_comm.receive_json_from()
        
        await user2_comm.connect()
        await user2_comm.receive_json_from()
        
        # Verify sessions created
        sessions = await database_sync_to_async(
            lambda: CustomSession.objects.count()
        )()
        assert sessions == 2
        
        # Create room (CustomGroupChat)
        await user1_comm.send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Integration Test Group',
                'participants': [users[1].id],
                'extra_fields': {
                    'tags': ['integration', 'test']
                }
            }
        })
        
        create_response = await user1_comm.receive_json_from()
        await user2_comm.receive_json_from()  # user2 receives room creation
        
        assert create_response['eventType'] == 'roomcreate.dispatch'
        room_id = create_response['data']['id']
        
        # Verify CustomGroupChat created
        group = await database_sync_to_async(
            CustomGroupChat.objects.filter(id=room_id).first
        )()
        assert group is not None
        assert group.tags == ['integration', 'test']
        
        # Send message (CustomMessage)
        await user1_comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': room_id,
                'content': 'Test message with all custom models',
                'extra_fields': {
                    'priority': 'urgent'
                },
            }
        })
        
        msg_response1 = await user1_comm.receive_json_from()
        msg_response2 = await user2_comm.receive_json_from()
        
        assert msg_response1['eventType'] == 'message.dispatch'
        assert msg_response2['eventType'] == 'message.dispatch'
        message_id = msg_response1['data']['id']
        
        # Verify CustomMessage created
        message = await database_sync_to_async(
            CustomMessage.objects.filter(id=message_id).first
        )()
        assert message is not None
        assert message.priority == 'urgent'
        
        # React to message
        await user2_comm.send_json_to({
            'event_type': 'message.react',
            'data': {
                'type': 'add',
                'message_id': message_id,
                'reaction_content': '🎉'
            }
        })
        
        await user1_comm.receive_json_from()
        await user2_comm.receive_json_from()
        
        # Read message
        await user2_comm.send_json_to({
            'event_type': 'message.read',
            'data': {
                'message_id': message_id
            }
        })
        
        await user2_comm.receive_json_from()
        await user1_comm.receive_json_from()
        
        # List rooms
        await user1_comm.send_json_to({
            'event_type': 'room.list',
            'data': {}
        })
        
        list_response = await user1_comm.receive_json_from()
        
        assert list_response['eventType'] == 'roomlist.dispatch'
        assert len(list_response['data']) >= 1
        
        await user1_comm.disconnect()
        await user2_comm.disconnect()

    
    async def test_concurrent_operations_with_custom_models(self, users):
        """Test concurrent users with custom models"""

        # Connect 5 users
        communicators = []
        for i in range(5):
            comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
            comm.scope['user'] = users[i]
            await comm.connect()
            await comm.receive_json_from()
            communicators.append(comm)
        
        # User 0 creates group with all users
        await communicators[0].send_json_to({
            'event_type': 'room.create',
            'data': {
                'type': 'GroupChat',
                'name': 'Concurrent Test',
                'participants': [u.id for u in users[1:5]]
            }
        })
        
        # All users receive room creation
        responses = []
        for comm in communicators:
            response = await comm.receive_json_from()
            responses.append(response)
        
        assert all(r['eventType'] == 'roomcreate.dispatch' for r in responses)
        room_id = responses[0]['data']['id']
        
        # All users send messages simultaneously
        for i, comm in enumerate(communicators):
            await comm.send_json_to({
                'event_type': 'message.send',
                'data': {
                    'room_id': room_id,
                    'content': f'Message from user{i}'
                }
            })
        
        # Each user should receive 5 messages
        for comm in communicators:
            for _ in range(5):
                msg = await comm.receive_json_from()
                assert msg['eventType'] == 'message.dispatch'
        
        for comm in communicators:
            await comm.disconnect()
        


# ==================== INTEGRATION TESTS WITH CUSTOM HANDLERS ====================

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestConsumerWithCustomHandler:
    """Test consumer events with custom event handler"""
    
    async def test_all_events_with_custom_handler(self, users, one_to_one_chat):
        """Test that all consumer events work with CustomEventHandler"""

        
        
        comm = WebsocketCommunicator(ChatMessagingConsumer.as_asgi(), "/messaging/")
        comm.scope['user'] = users[0]
        
        await comm.connect()
        await comm.receive_json_from()
        
        # Test message send
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Test with custom handler'
            }
        })
        
        response = await comm.receive_json_from()
        assert response['eventType'] == 'message.dispatch'
        
        # Test room list
        await comm.send_json_to({
            'event_type': 'room.list',
            'data': {}
        })
        
        list_response = await comm.receive_json_from()
        assert list_response['eventType'] == 'roomlist.dispatch'
        
        await comm.disconnect()
        


# ==================== INTEGRATION TESTS WITH CUSTOM PERMISSION HANDLER ====================

# @pytest.mark.asyncio
# @pytest.mark.django_db(transaction=True)
# @pytest.mark.integration
# @override_settings(
#     REALTIME_CHAT_MESSAGING={
#         'PERMISSION_HANDLER_CLASS': 'tests.test_custom_implementations.CustomPermissionHandler'
#     }
# )
# class TestConsumerWithCustomPermissionHandler:
#     """Test consumer permission checks with custom permission handler"""
    
#     async def test_permissions_with_custom_handler(self, users, create_one_to_one_chat, register_room_with_user):
#         """Test that custom permission handler is used in consumer"""
#         from realtime_chat_messaging.conf import realtime_chat_settings

        
#         chat = create_one_to_one_chat(users[0], users[1])
#         await register_room_with_user(users[0].id, chat.id)
        
#         comm