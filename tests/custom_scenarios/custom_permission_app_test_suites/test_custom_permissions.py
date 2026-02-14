"""
Integration tests for Scenario 3: Custom Permissions Only

Tests that overriding only the permission handler works correctly while
all models and serializers remain default.

Key test areas:
- Archived room read-only enforcement
- VIP user special privileges
- Time-based restrictions
- Message quota enforcement
- Admin privilege override
"""
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from realtime_chat_messaging.models import GroupChat, RoomProperty, OneToOneChat
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from custom_permission_app.permissions import CustomPermissionHandler

User = get_user_model()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestArchivedRoomPermissions:
    """Test archived room read-only behavior"""
    
    async def test_archived_room_blocks_messages_regular_user(self, users, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that archived rooms block message sending for regular users"""
        # Create room
        group = await database_sync_to_async(create_group_chat)(
            name='Test Group',
            creator=users[0], 
            participants=users[:2]
        )

        # Create and set archived property
        room_property = await database_sync_to_async(RoomProperty.objects.create)(
            preferences={"archived": True}
        )
        group.property = room_property
        await database_sync_to_async(group.save)()
        

        # register users
        await add_users_to_room_channel_group(group.id, users[:2])

        # Try to send message as regular user
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group.id),
                'content': 'Should be blocked'
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should receive error for archived room
        assert 'error' in response
        
        await comm.disconnect()
    
    async def test_vip_user_bypasses_archived_restriction(self, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that VIP users can send messages in archived rooms"""
        # Create VIP user (username contains 'vip')
        vip_user = await database_sync_to_async(User.objects.create_user)(
            username='vip_user',
            email='vip@test.com',
            password='testpass123'
        )
        
        regular_user = await database_sync_to_async(User.objects.create_user)(
            username='regular',
            email='regular@test.com',
            password='testpass123'
        )
        
        # Create archived room
        group = await database_sync_to_async(create_group_chat)(
            name='Archived Group',
            creator=vip_user, 
            participants=[vip_user, regular_user]
        )
     
        room_property = await database_sync_to_async(RoomProperty.objects.create)(
            preferences={"archived": True}
        )
        group.property = room_property
        await database_sync_to_async(group.save)()


        # register users into the room

        await add_users_to_room_channel_group(group.id, [vip_user, regular_user])
        
        # VIP user sends message
        comm = await websocket_communicator(vip_user)
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group.id),
                'content': 'VIP message in archived room'
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should succeed for VIP user
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'VIP message in archived room'
        
        await comm.disconnect()
    
    async def test_archived_room_can_be_viewed(self, users, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that archived rooms can still be viewed/accessed"""
        # Create archived room
        group = await database_sync_to_async(create_group_chat)(
            name='Archived Room',
            creator=users[0],
            participants=users[:2]
        )
        room_property = await database_sync_to_async(RoomProperty.objects.create)(
            preferences={"archived": True}
        )
        group.property = room_property
        await database_sync_to_async(group.save)()

        # register users into the room
        await add_users_to_room_channel_group(group.id, users=[users[0], users[1]])
        
        # User can still view room info
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': str(group.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should succeed - viewing is allowed
        assert response['eventType'] == 'roominfo.dispatch'
        assert response['data']['id'] == str(group.id)
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestVIPUserPrivileges:
    """Test VIP user special privileges"""
    
    async def test_vip_user_has_admin_privileges(self, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that VIP users have admin privileges in any room"""
        vip_user = await database_sync_to_async(User.objects.create_user)(
            username='vip_admin',
            email='vipadmin@test.com',
            password='testpass123'
        )
        
        regular_user = await database_sync_to_async(User.objects.create_user)(
            username='regular',
            email='regular@test.com',
            password='testpass123'
        )
        
        another_user = await database_sync_to_async(User.objects.create_user)(
            username='user3',
            email='user3@test.com',
            password='testpass123'
        )
        
        # Create room (regular user is creator)
        group = await database_sync_to_async(create_group_chat)(
            name='Test Group',
            creator=regular_user,
            participants=[vip_user, regular_user]
        )
        
        await add_users_to_room_channel_group(group.id, [vip_user, regular_user])
        # VIP user tries to add members (admin action)
        comm = await websocket_communicator(vip_user)
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(group.id),
                'members': [another_user.id]
            }
        })
        
        response = await comm.receive_json_from()
        
        # VIP user should succeed even though not creator/admin
        assert response['eventType'] == 'roomaddmembers.dispatch'
        assert 'user3' in response['data']['new_members']
        
        await comm.disconnect()
    
    async def test_vip_user_can_remove_members(self, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that VIP users can remove members from any room"""
        vip_user = await database_sync_to_async(User.objects.create_user)(
            username='vip_moderator',
            email='vipmod@test.com',
            password='testpass123'
        )
        
        creator = await database_sync_to_async(User.objects.create_user)(
            username='creator',
            email='creator@test.com',
            password='testpass123'
        )
        
        to_remove = await database_sync_to_async(User.objects.create_user)(
            username='removeme',
            email='removeme@test.com',
            password='testpass123'
        )
        
        # Create room
        group = await database_sync_to_async(create_group_chat)(
            name='Test Group',
            creator=creator,
            participants=[creator, vip_user, to_remove]
        )
        
        await add_users_to_room_channel_group(group.id, [vip_user, creator, to_remove])

        # VIP user removes member
        comm = await websocket_communicator(vip_user)
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.remove_members',
            'data': {
                'room_id': str(group.id),
                'members': [to_remove.id]
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should succeed
        assert response['eventType'] == 'roomremovemembers.dispatch'
        
        await comm.disconnect()
    
    async def test_vip_user_bypass_in_locked_group(self, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that VIP users can send messages in locked groups"""
        vip_user = await database_sync_to_async(User.objects.create_user)(
            username='vip_sender',
            email='vipsender@test.com',
            password='testpass123'
        )
        
        creator = await database_sync_to_async(User.objects.create_user)(
            username='group_creator',
            email='creator@test.com',
            password='testpass123'
        )
        
        # Create locked group
        group = await database_sync_to_async(create_group_chat)(
            name='Locked Group',
            creator=creator,
            group_locked=True,
            participants=[creator, vip_user]
        )
        await add_users_to_room_channel_group(group.id, [vip_user, creator])
        # VIP user sends message in locked group
        comm = await websocket_communicator(vip_user)
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group.id),
                'content': 'VIP message in locked group'
            }
        })
        
        response = await comm.receive_json_from()
        
        # Should succeed - VIP bypasses lock
        assert response['eventType'] == 'message.dispatch'
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestPermissionHandlerMethods:
    """Test permission handler methods directly"""
    
    async def test_is_vip_user_detection(self, create_group_chat):
        """Test _is_vip_user helper method"""

        vip_user = await database_sync_to_async(User.objects.create_user)(
            username='vip_test',
            email='vip@test.com',
            password='test123'
        )
        
        regular_user = await database_sync_to_async(User.objects.create_user)(
            username='regular',
            email='regular@test.com',
            password='test123'
        )
        
        group = await database_sync_to_async(create_group_chat)(
            name='Test Group',
            creator=regular_user,
            participants=[regular_user, vip_user]
        )
        handler = CustomPermissionHandler()
        
        is_vip = await handler._is_vip_user(vip_user, group)
        is_regular = await handler._is_vip_user(regular_user, group)
        
        assert is_vip is True
        assert is_regular is False
    
    async def test_have_room_permission_with_regular_user(self, one_to_one_chat,  users):
        """Test have_room_permission for regular user"""
        # Create room
     
        
        handler = CustomPermissionHandler()
        has_perm, room = await handler.have_room_permission(users[0], str(one_to_one_chat.id))
        
        assert has_perm is True
        assert room.id == one_to_one_chat.id
    
    async def test_have_send_message_permission_regular_user(self, users, one_to_one_chat):
        """Test have_send_message_permission for regular user"""
        handler = CustomPermissionHandler()
        can_send, room = await handler.have_send_message_permission(users[0], {"room_id": str(one_to_one_chat.id)})
        
        assert can_send is True
        assert room.id == one_to_one_chat.id
    
    async def test_check_message_quota_under_limit(self, users, one_to_one_chat):
        """Test check_message_quota when under limit"""
        from realtime_chat_messaging.models import Message
        
        # Create 50 messages (under 100 limit)
        for i in range(50):
            await database_sync_to_async(Message.objects.create)(
                room=one_to_one_chat,
                sender=users[0],
                content=f'Message {i}'
            )
        
        handler = CustomPermissionHandler()
        can_send = await handler.check_message_quota(users[0], one_to_one_chat)
        
        assert can_send is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestBackwardCompatibilityWithPermissions:
    """Test that custom permissions don't break existing functionality"""
    
    async def test_normal_message_flow_unchanged(self, users, websocket_communicator, one_to_one_chat):
        """Test that normal message sending still works"""

        
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Normal message'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        assert response['data']['content'] == 'Normal message'
        
        await comm.disconnect()
    
    async def test_regular_admin_privileges_still_work(self, users, websocket_communicator, create_group_chat, add_users_to_room_channel_group):
        """Test that regular admin privileges still work"""
        group = await database_sync_to_async(create_group_chat)(
            name='Test Group',
            creator=users[0],
            participants=users[:2]
        )
        await database_sync_to_async(group.admins.add)(users[0])
        await add_users_to_room_channel_group(group.id, users=users[:2])
        # Creator/admin can add members
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.add_members',
            'data': {
                'room_id': str(group.id),
                'members': [users[2].id]
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'roomaddmembers.dispatch'
        
        await comm.disconnect()
    
    async def test_unauthorized_access_still_blocked(self,  users, one_to_one_chat, websocket_communicator):
        """Test that unauthorized users still can't access rooms"""
      
        # User 2 (not a participant) tries to access
        comm = await websocket_communicator(users[2])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': str(one_to_one_chat.id)
            }
        })
        
        response = await comm.receive_json_from()
        
        assert 'error' in response
        assert response['error']['code'] == 4002 # Permission denied error code
        
        await comm.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestEdgeCasesWithCustomPermissions:
    """Test edge cases with custom permission logic"""
    
    async def test_non_archived_room_works_normally(self, websocket_communicator, users, create_group_chat, add_users_to_room_channel_group):
        """Test that non-archived rooms work normally"""
        group = await database_sync_to_async(create_group_chat)(
            name='Normal Group',
            creator=users[0],
            participants=users[:2]
        )
        
        await add_users_to_room_channel_group(group.id, users=users[:2])
        # No archived property - should work normally
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(group.id),
                'content': 'Normal message'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        
        await comm.disconnect()
    
    async def test_room_without_property_works(self, websocket_communicator, users, one_to_one_chat):
        """Test that rooms without RoomProperty work"""
        
        # OneToOneChat typically doesn't have property
        comm = await websocket_communicator(users[0])
        await comm.connect()
        await comm.receive_json_from()
        
        await comm.send_json_to({
            'event_type': 'message.send',
            'data': {
                'room_id': str(one_to_one_chat.id),
                'content': 'Test'
            }
        })
        
        response = await comm.receive_json_from()
        
        assert response['eventType'] == 'message.dispatch'
        
        await comm.disconnect()
    
    async def test_vip_in_username_case_insensitive(self, create_group_chat):
        """Test that VIP detection is case insensitive"""
        vip_upper = await database_sync_to_async(User.objects.create_user)(
            username='VIP_USER',
            email='vip1@test.com',
            password='test123'
        )
        
        vip_lower = await database_sync_to_async(User.objects.create_user)(
            username='vip_user',
            email='vip2@test.com',
            password='test123'
        )
        
        vip_mixed = await database_sync_to_async(User.objects.create_user)(
            username='ViP_user',
            email='vip3@test.com',
            password='test123'
        )
        
        group = await database_sync_to_async(create_group_chat)(
            name="Test Group",
            creator=vip_upper,
            participants=[vip_upper, vip_lower, vip_mixed]
        )
        handler = CustomPermissionHandler()
        
        assert await handler._is_vip_user(vip_upper, group) is True
        assert await handler._is_vip_user(vip_lower, group) is True
        assert await handler._is_vip_user(vip_mixed, group) is True
