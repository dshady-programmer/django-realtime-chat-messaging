import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from realtime_chat_messaging.permissions.helpers import (
    have_room_permission,
    have_message_permission,
    is_message_sender,
    have_room_permissions_to_add_or_remove_members,
    have_send_message_permission,
    have_admin_privileges
)
from realtime_chat_messaging.models import (
    OneToOneChat, GroupChat, Channel, Message
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
class TestRoomPermission:
    """Test have_room_permission function"""

    async def test_participant_has_room_permission_one_to_one(self, users, one_to_one_chat):
        """Test that participant has permission to access one-to-one chat"""
        has_perm, room = await have_room_permission(users['user1'], str(one_to_one_chat.id))
        
        assert has_perm is True
        assert room.id == one_to_one_chat.id

    async def test_non_participant_no_room_permission_one_to_one(self, users, one_to_one_chat):
        """Test that non-participant has no permission"""
        has_perm, room = await have_room_permission(users['user3'], str(one_to_one_chat.id))
        
        assert has_perm is False

    async def test_participant_has_room_permission_group(self, users, group_chat):
        """Test that participant has permission to access group chat"""
        has_perm, room = await have_room_permission(users['user1'], str(group_chat.id))
        
        assert has_perm is True
        assert room.id == group_chat.id

    async def test_non_participant_no_room_permission_group(self, users, group_chat):
        """Test that non-participant has no permission to group"""
        has_perm, room = await have_room_permission(users['user2'], str(group_chat.id))
        
        assert has_perm is False

    async def test_subscriber_has_room_permission_channel(self, users, channel_fixture):
        """Test that subscriber has permission to access channel"""
        has_perm, room = await have_room_permission(users['user1'], str(channel_fixture.id))
        
        assert has_perm is True
        assert room.id == channel_fixture.id

    async def test_non_subscriber_no_room_permission_channel(self, users, channel_fixture):
        """Test that non-subscriber has no permission to channel"""
        has_perm, room = await have_room_permission(users['user2'], str(channel_fixture.id))
        
        assert has_perm is False

    async def test_invalid_room_id_type_raises_error(self, users):
        """Test that invalid room_id type raises ValidationError"""
        with pytest.raises(ValidationError, match="Invalid room_id type"):
            await have_room_permission(users['user1'], ['invalid', 'list'])


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessagePermission:
    """Test have_message_permission function"""

    async def test_room_member_has_message_permission(self, users, one_to_one_chat):
        """Test that room member has permission to access message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        has_perm = await have_message_permission(users['user1'], str(message.id))
        
        assert has_perm is True

    async def test_non_room_member_no_message_permission(self, users, one_to_one_chat):
        """Test that non-room member has no permission"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        has_perm = await have_message_permission(users['user3'], str(message.id))
        
        assert has_perm is False

    async def test_multiple_messages_all_accessible(self, users, one_to_one_chat):
        """Test checking permission for multiple messages"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user2'],
            content="Test 2"
        )
        
        has_perm = await have_message_permission(
            users['user1'],
            [str(message1.id), str(message2.id)]
        )
        
        assert has_perm is True

    async def test_multiple_messages_one_not_accessible(self, users, one_to_one_chat, group_chat):
        """Test that permission fails if one message is not accessible"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users['user1'],
            content="Test 2"
        )
        
        # user2 is in one_to_one_chat but not group_chat
        has_perm = await have_message_permission(
            users['user2'],
            [str(message1.id), str(message2.id)]
        )
        
        assert has_perm is False

    async def test_invalid_message_id_type_raises_error(self, users):
        """Test that invalid message_id type raises ValidationError"""
        with pytest.raises(ValidationError, match="Invalid message_id type"):
            await have_message_permission(users['user1'], {'invalid': 'dict'})


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageSenderPermission:
    """Test is_message_sender function"""

    async def test_sender_is_authorized(self, users, one_to_one_chat):
        """Test that message sender is authorized to modify"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        is_authorized, room = await is_message_sender(users['user1'], str(message.id))
        
        assert is_authorized is True
        assert room.id == one_to_one_chat.id

    async def test_non_sender_not_authorized(self, users, one_to_one_chat):
        """Test that non-sender is not authorized to modify"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        is_authorized, room = await is_message_sender(users['user2'], str(message.id))
        
        assert is_authorized is False

    async def test_multiple_messages_same_sender(self, users, one_to_one_chat):
        """Test authorization for multiple messages from same sender"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test 2"
        )
        
        is_authorized, room = await is_message_sender(
            users['user1'],
            [str(message1.id), str(message2.id)]
        )
        
        assert is_authorized is True

    async def test_multiple_messages_different_senders_not_authorized(self, users, one_to_one_chat):
        """Test that authorization fails if messages have different senders"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user2'],
            content="Test 2"
        )
        
        is_authorized, room = await is_message_sender(
            users['user1'],
            [str(message1.id), str(message2.id)]
        )
        
        assert is_authorized is False

    async def test_messages_from_different_rooms_raises_error(self, users, one_to_one_chat, group_chat):
        """Test that messages from different rooms raise ValidationError"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users['user1'],
            content="Test 2"
        )
        
        with pytest.raises(ValidationError, match="All messages marked for modification must come from the same room"):
            await is_message_sender(
                users['user1'],
                [str(message1.id), str(message2.id)]
            )

    async def test_empty_message_list_raises_error(self, users):
        """Test that empty message list raises ValidationError"""
        with pytest.raises(ValidationError, match="Atleast one message_id is required for modification"):
            await is_message_sender(users['user1'], [])


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAddRemoveMembersPermission:
    """Test have_room_permissions_to_add_or_remove_members function"""

    async def test_group_creator_can_add_members(self, users, group_chat):
        """Test that group creator can add members"""
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user1'],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_group_admin_can_add_members(self, users, group_chat):
        """Test that group admin can add members"""
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        await database_sync_to_async(group_chat.admins.add)(users['user2'])
        
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user2'],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_group_regular_member_cannot_add_members(self, users, group_chat):
        """Test that regular member cannot add members"""
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user2'],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is False

    async def test_channel_creator_can_add_subscribers(self, users, channel_fixture):
        """Test that channel creator can add subscribers"""
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user1'],
            str(channel_fixture.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_channel_moderator_can_add_subscribers(self, users, channel_fixture):
        """Test that channel moderator can add subscribers"""
        await database_sync_to_async(channel_fixture.subscribers.add)(users['user2'])
        await database_sync_to_async(channel_fixture.moderators.add)(users['user2'])
        
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user2'],
            str(channel_fixture.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_channel_regular_subscriber_cannot_add(self, users, channel_fixture):
        """Test that regular subscriber cannot add members"""
        await database_sync_to_async(channel_fixture.subscribers.add)(users['user2'])
        
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user2'],
            str(channel_fixture.id),
            "add_new"
        )
        
        assert has_perm is False

    async def test_one_to_one_chat_raises_error(self, users, one_to_one_chat):
        """Test that one-to-one chat raises ValidationError"""
        with pytest.raises(ValidationError, match="Can only add or remove members from Groups/Channels"):
            await have_room_permissions_to_add_or_remove_members(
                users['user1'],
                str(one_to_one_chat.id),
                "add_new"
            )

    async def test_user_with_permission_can_add_members(self, users, group_chat):
        """Test that user with specific permission can add members"""
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        # Grant permission manually
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(assign_perm)('can_add_new_participants', users['user2'], group_chat)
        
        has_perm, room = await have_room_permissions_to_add_or_remove_members(
            users['user2'],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is True


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSendMessagePermission:
    """Test have_send_message_permission function"""

    async def test_one_to_one_participant_can_send(self, users, one_to_one_chat):
        """Test that one-to-one participant can send message"""
        has_perm, room = await have_send_message_permission(
            users['user1'],
            {'room_id': str(one_to_one_chat.id)}
        )
        
        assert has_perm is True

    async def test_group_participant_can_send_when_not_locked(self, users, group_chat):
        """Test that group participant can send when group is not locked"""
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        has_perm, room = await have_send_message_permission(
            users['user2'],
            {'room_id': str(group_chat.id)}
        )
        
        assert has_perm is True

    async def test_group_admin_can_send_when_locked(self, users, group_chat):
        """Test that admin can send to locked group"""
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        
        has_perm, room = await have_send_message_permission(
            users['user1'],
            {'room_id': str(group_chat.id)}
        )
        
        assert has_perm is True

    async def test_group_regular_member_cannot_send_when_locked(self, users, group_chat):
        """Test that regular member cannot send to locked group"""
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        has_perm, room = await have_send_message_permission(
            users['user2'],
            {'room_id': str(group_chat.id)}
        )
        
        assert has_perm is False

    async def test_channel_moderator_can_send(self, users, channel_fixture):
        """Test that channel moderator can send message"""
        has_perm, room = await have_send_message_permission(
            users['user1'],
            {'room_id': str(channel_fixture.id)}
        )
        
        assert has_perm is True

    async def test_channel_regular_subscriber_cannot_send(self, users, channel_fixture):
        """Test that regular subscriber cannot send to channel"""
        await database_sync_to_async(channel_fixture.subscribers.add)(users['user2'])
        
        has_perm, room = await have_send_message_permission(
            users['user2'],
            {'room_id': str(channel_fixture.id)}
        )
        
        assert has_perm is False

    async def test_channel_subscriber_with_permission_can_send(self, users, channel_fixture):
        """Test that subscriber with permission can send to channel"""
        await database_sync_to_async(channel_fixture.subscribers.add)(users['user2'])
        
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(assign_perm)('can_send_messages', users['user2'], channel_fixture)
        
        has_perm, room = await have_send_message_permission(
            users['user2'],
            {'room_id': str(channel_fixture.id)}
        )
        
        assert has_perm is True

    async def test_permission_check_with_message_id(self, users, one_to_one_chat):
        """Test permission check using message_id instead of room_id"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        has_perm, room = await have_send_message_permission(
            users['user1'],
            {'message_id': str(message.id)}
        )
        
        assert has_perm is True
        assert room.id == one_to_one_chat.id


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAdminPrivileges:
    """Test have_admin_privileges function"""

    async def test_group_creator_has_admin_privileges(self, users, group_chat):
        """Test that group creator has admin privileges"""
        has_priv, room = await have_admin_privileges(users['user1'], str(group_chat.id))
        
        assert has_priv is True

    async def test_group_admin_has_admin_privileges(self, users, group_chat):
        """Test that group admin has admin privileges"""
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        await database_sync_to_async(group_chat.admins.add)(users['user2'])
        
        has_priv, room = await have_admin_privileges(users['user2'], str(group_chat.id))
        
        assert has_priv is True

    async def test_group_regular_member_no_admin_privileges(self, users, group_chat):
        """Test that regular member has no admin privileges"""
        await database_sync_to_async(group_chat.participants.add)(users['user2'])
        
        has_priv, room = await have_admin_privileges(users['user2'], str(group_chat.id))
        
        assert has_priv is False

    async def test_channel_creator_has_admin_privileges(self, users, channel_fixture):
        """Test that channel creator has admin privileges"""
        has_priv, room = await have_admin_privileges(users['user1'], str(channel_fixture.id))
        
        assert has_priv is True

    async def test_channel_moderator_has_admin_privileges(self, users, channel_fixture):
        """Test that channel moderator has admin privileges"""
        await database_sync_to_async(channel_fixture.subscribers.add)(users['user2'])
        await database_sync_to_async(channel_fixture.moderators.add)(users['user2'])
        
        has_priv, room = await have_admin_privileges(users['user2'], str(channel_fixture.id))
        
        assert has_priv is True

    async def test_channel_regular_subscriber_no_admin_privileges(self, users, channel_fixture):
        """Test that regular subscriber has no admin privileges"""
        await database_sync_to_async(channel_fixture.subscribers.add)(users['user2'])
        
        has_priv, room = await have_admin_privileges(users['user2'], str(channel_fixture.id))
        
        assert has_priv is False

    async def test_non_member_no_admin_privileges(self, users, group_chat):
        """Test that non-member has no admin privileges"""
        has_priv, room = await have_admin_privileges(users['user2'], str(group_chat.id))
        
        assert has_priv is False