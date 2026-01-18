import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from realtime_chat_messaging.permissions.handlers import PermissionHandler
from realtime_chat_messaging.models import Message
from django.http.response import Http404
import uuid

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create 10 test users"""
    return create_users(10)


@pytest.fixture
def one_to_one_chat(users, create_one_to_one_chat):
    """Create a one-to-one chat"""
    return create_one_to_one_chat(users[0], users[1])
    


@pytest.fixture
def group_chat(users, create_group_chat):
    """Create a group chat"""

    return create_group_chat(users[0], "Test Group", description="A test group")
    

@pytest.fixture
def channel(users, create_channel):
    """Create a channel"""
    return create_channel(users[0], "Test Channel", description="A test channel", is_public=True)


permission_handler = PermissionHandler()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestRoomPermission:
    """Test have_room_permission function"""

    async def test_participant_has_room_permission_one_to_one(self, users, one_to_one_chat):
        """Test that participant has permission to access one-to-one chat"""
        has_perm, room = await permission_handler.have_room_permission(users[0], str(one_to_one_chat.id))
        
        assert has_perm is True
        assert room.id == one_to_one_chat.id

    async def test_non_participant_no_room_permission_one_to_one(self, users, one_to_one_chat):
        """Test that non-participant has no permission"""
        has_perm, _ = await permission_handler.have_room_permission(users[3], str(one_to_one_chat.id))
        
        assert has_perm is False

    async def test_participant_has_room_permission_group(self, users, group_chat):
        """Test that participant has permission to access group chat"""
        has_perm, room = await permission_handler.have_room_permission(users[0], str(group_chat.id))
        
        assert has_perm is True
        assert room.id == group_chat.id

    async def test_non_participant_no_room_permission_group(self, users, group_chat):
        """Test that non-participant has no permission to group"""
        has_perm, _ = await permission_handler.have_room_permission(users[4], str(group_chat.id))
        
        assert has_perm is False

    async def test_subscriber_has_room_permission_channel(self, users, channel):
        """Test that subscriber has permission to access channel"""
        has_perm, room = await permission_handler.have_room_permission(users[0], str(channel.id))
        
        assert has_perm is True
        assert room.id == channel.id

    async def test_non_subscriber_no_room_permission_channel(self, users, channel):
        """Test that non-subscriber has no permission to channel"""
        has_perm, room = await permission_handler.have_room_permission(users[5], str(channel.id))
        
        assert has_perm is False

    async def test_invalid_room_id_type_raises_error(self, users):
        """Test that invalid room_id type raises ValidationError"""
        with pytest.raises(ValidationError, match="Invalid room_id type"):
            await permission_handler.have_room_permission(users[0], ['invalid', 'list'])
        with pytest.raises(ValidationError, match="Invalid room_id type"):
            await permission_handler.have_room_permission(users[0], {'invalid', 'list'})
        with pytest.raises(ValidationError, match="Invalid room_id type"):
            await permission_handler.have_room_permission(users[0], {'invalid': 'list'})

    async def test_invalid_room_id_raises_error(self, users):
        """Test that invalid room_id raises ValidationError"""
        with pytest.raises(Http404):
            await permission_handler.have_room_permission(users[0], str(uuid.uuid4()))
        with pytest.raises(Http404):
            await permission_handler.have_room_permission(users[0], 421)
        with pytest.raises(ValidationError):
            await permission_handler.have_room_permission(users[0], "uuid-uuid")



@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessagePermission:
    """Test have_message_permission function"""

    async def test_room_member_has_message_permission(self, users, one_to_one_chat):
        """Test that room member has permission to access message"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        has_perm = await permission_handler.have_message_permission(users[0], str(message.id))
        
        assert has_perm is True

    async def test_non_room_member_no_message_permission(self, users, one_to_one_chat):
        """Test that non-room member has no permission"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        has_perm = await permission_handler.have_message_permission(users[2], str(message.id))
        
        assert has_perm is False

    async def test_multiple_messages_all_accessible(self, users, one_to_one_chat):
        """Test checking permission for multiple messages"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[1],
            content="Test 2"
        )
        
        has_perm = await permission_handler.have_message_permission(
            users[0],
            [str(message1.id), str(message2.id)]
        )
        
        assert has_perm is True

    async def test_multiple_messages_one_not_accessible(self, users, one_to_one_chat, group_chat):
        """Test that permission fails if one message is not accessible"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users[0],
            content="Test 2"
        )
        
        # user2 is in one_to_one_chat but not group_chat
        has_perm = await permission_handler.have_message_permission(
            users[1],
            [str(message1.id), str(message2.id)]
        )
        
        assert has_perm is False

    async def test_invalid_message_id_type_raises_error(self, users):
        """Test that invalid message_id type raises ValidationError"""
        with pytest.raises(ValidationError, match="Invalid message_id type"):
            await permission_handler.have_message_permission(users[0], {'invalid': 'dict'})


    async def test_invalid_message_id_raises_error(self, one_to_one_chat, users):
        """Test that invalid message_id raises ValidationError"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 1"
        )
        with pytest.raises(Http404):
            await permission_handler.have_message_permission(users[0], [str(message1.id), str(uuid.uuid4())])


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMessageSenderPermission:
    """Test is_message_sender function"""

    async def test_sender_is_authorized(self, users, one_to_one_chat):
        """Test that message sender is authorized to modify"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        is_authorized, room = await permission_handler.is_message_sender(users[0], str(message.id))
        
        assert is_authorized is True
        assert room.id == one_to_one_chat.id

    async def test_non_sender_not_authorized(self, users, one_to_one_chat):
        """Test that non-sender is not authorized to modify"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        is_authorized, _ = await permission_handler.is_message_sender(users[1], str(message.id))
        
        assert is_authorized is False

    async def test_multiple_messages_same_sender(self, users, one_to_one_chat):
        """Test authorization for multiple messages from same sender"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 2"
        )
        
        is_authorized, _ = await permission_handler.is_message_sender(
            users[0],
            [str(message1.id), str(message2.id)]
        )
        
        assert is_authorized is True

    async def test_multiple_messages_different_senders_not_authorized(self, users, one_to_one_chat):
        """Test that authorization fails if messages have different senders (1st authorized, 2nd unauthorized )"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[1],
            content="Test 2"
        )
        
        is_authorized, _ = await permission_handler.is_message_sender(
            users[0],
            [str(message1.id), str(message2.id)]
        )
        
        assert is_authorized is False

    async def test_messages_from_different_rooms_raises_error(self, users, one_to_one_chat, group_chat):
        """Test that messages from different rooms raise ValidationError"""
        message1 = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test 1"
        )
        message2 = await database_sync_to_async(Message.objects.create)(
            room=group_chat,
            sender=users[0],
            content="Test 2"
        )
        
        with pytest.raises(ValidationError, match="All messages marked for modification must come from the same room"):
            await permission_handler.is_message_sender(
                users[0],
                [str(message1.id), str(message2.id)]
            )

    async def test_empty_message_list_raises_error(self, users):
        """Test that empty message list raises ValidationError"""
        with pytest.raises(ValidationError, match="Atleast one message_id is required for modification"):
            await permission_handler.is_message_sender(users[0], [])


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAddRemoveMembersPermission:
    """Test have_room_permissions_to_add_or_remove_members function"""

    async def test_group_creator_can_add_members(self, users, group_chat):
        """Test that group creator can add members"""
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[0],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_group_admin_can_add_members(self, users, group_chat):
        """Test that group admin can add members"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_group_regular_member_cannot_add_members(self, users, group_chat):
        """Test that regular member cannot add members"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is False

    async def test_group_creator_can_remove_members(self, users, group_chat):
        """Test that group creator can remove members"""
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[0],
            str(group_chat.id),
            "remove"
        )
        
        assert has_perm is True

    async def test_group_admin_can_remove_members(self, users, group_chat):
        """Test that group admin can remove members"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(group_chat.id),
            "remove"
        )
        
        assert has_perm is True

    async def test_group_regular_member_cannot_remove_members(self, users, group_chat):
        """Test that regular member cannot remove members"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(group_chat.id),
            "remove"
        )
        
        assert has_perm is False



    async def test_channel_creator_can_add_subscribers(self, users, channel):
        """Test that channel creator can add subscribers"""
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[0],
            str(channel.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_channel_moderator_can_add_subscribers(self, users, channel):
        """Test that channel moderator can add subscribers"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(channel.moderators.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(channel.id),
            "add_new"
        )
        
        assert has_perm is True

    async def test_channel_regular_subscriber_cannot_add(self, users, channel):
        """Test that regular subscriber cannot add members"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(channel.id),
            "add_new"
        )
        
        assert has_perm is False

    async def test_one_to_one_chat_raises_error(self, users, one_to_one_chat):
        """Test that one-to-one chat raises ValidationError"""
        with pytest.raises(ValidationError, match="Can only add or remove members from Groups/Channels"):
            await permission_handler.have_room_permissions_to_add_or_remove_members(
                users[0],
                str(one_to_one_chat.id),
                "add_new"
            )

    async def test_user_with_permission_can_add_members(self, users, group_chat):
        """Test that user with specific permission can add members"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        # Grant permission manually
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(assign_perm)('can_add_new_participants', users[1], group_chat)
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(group_chat.id),
            "add_new"
        )
        
        assert has_perm is True


    async def test_channel_creator_can_remove_subscribers(self, users, channel):
        """Test that channel creator can remove subscribers"""
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[0],
            str(channel.id),
            "remove"
        )
        
        assert has_perm is True

    async def test_channel_moderator_can_remove_subscribers(self, users, channel):
        """Test that channel moderator can remove subscribers"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(channel.moderators.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(channel.id),
            "remove"
        )
        
        assert has_perm is True

    async def test_channel_regular_subscriber_cannot_remove(self, users, channel):
        """Test that regular subscriber cannot remove members"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(channel.id),
            "remove"
        )
        
        assert has_perm is False



    async def test_user_with_permission_can_remove_members(self, users, group_chat):
        """Test that user with specific permission can remove members"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        # Grant permission manually
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(assign_perm)('can_remove_participants', users[1], group_chat)
        
        has_perm, _ = await permission_handler.have_room_permissions_to_add_or_remove_members(
            users[1],
            str(group_chat.id),
            "remove"
        )

        assert has_perm is True



@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestSendMessagePermission:
    """Test have_send_message_permission function"""

    async def test_one_to_one_participant_can_send(self, users, one_to_one_chat):
        """Test that one-to-one participant can send message"""
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[0],
            {'room_id': str(one_to_one_chat.id)}
        )
        
        assert has_perm is True

    async def test_group_participant_can_send_when_not_locked(self, users, group_chat):
        """Test that group participant can send when group is not locked"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[1],
            {'room_id': str(group_chat.id)}
        )
        
        assert has_perm is True

    async def test_group_admin_can_send_when_locked(self, users, group_chat):
        """Test that admin can send to locked group"""
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[0],
            {'room_id': str(group_chat.id)}
        )
        
        assert has_perm is True

    async def test_group_regular_member_cannot_send_when_locked(self, users, group_chat):
        """Test that regular member cannot send to locked group"""
        await database_sync_to_async(setattr)(group_chat, 'group_locked', True)
        await database_sync_to_async(group_chat.save)()
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[1],
            {'room_id': str(group_chat.id)}
        )
        
        assert has_perm is False

    async def test_channel_moderator_can_send(self, users, channel):
        """Test that channel moderator can send message"""
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[0],
            {'room_id': str(channel.id)}
        )
        
        assert has_perm is True

    async def test_channel_regular_subscriber_cannot_send(self, users, channel):
        """Test that regular subscriber cannot send to channel"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[1],
            {'room_id': str(channel.id)}
        )
        
        assert has_perm is False

    async def test_channel_subscriber_with_permission_can_send(self, users, channel):
        """Test that subscriber with permission can send to channel"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(assign_perm)('can_send_messages', users[1], channel)
        
        has_perm, _ = await permission_handler.have_send_message_permission(
            users[1],
            {'room_id': str(channel.id)}
        )
        
        assert has_perm is True

    async def test_permission_check_with_message_id(self, users, one_to_one_chat):
        """Test permission check using message_id instead of room_id"""
        message = await database_sync_to_async(Message.objects.create)(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        has_perm, room = await permission_handler.have_send_message_permission(
            users[0],
            {'message_id': str(message.id)}
        )
        
        assert has_perm is True
        assert room.id == one_to_one_chat.id

    async def test_permission_check_with_invalid_room_id_raises_error(self, users):
        """Test permission check using invalid room id raises error"""


        # uuid but not associated with any room

        with pytest.raises(Http404):
            await permission_handler.have_send_message_permission(
                users[0],
                {'room_id': str(uuid.uuid4())}
            )

        # invalid room_id type
        with pytest.raises(ValidationError, match="Invalid room_id type"):
            await permission_handler.have_send_message_permission(
                users[0],
                {'room_id': ['id']}
            )

    async def test_permission_check_with_invalid_message_id_raises_error(self, users):
        """Test permission check using invalid message id raises error"""

        # uuid but not associated with any message

        with pytest.raises(Http404):
            await permission_handler.have_send_message_permission(
                users[0],
                {'message_id': str(uuid.uuid4())}
            )

        # invalid message_id type
        with pytest.raises(ValidationError, match="Invalid message_id type"):
            await permission_handler.have_send_message_permission(
                users[0],
                {'message_id': ['id']}
            )


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestAdminPrivileges:
    """Test have_admin_privileges function"""

    async def test_group_creator_has_admin_privileges(self, users, group_chat):
        """Test that group creator has admin privileges"""
        has_priv, _ = await permission_handler.have_admin_privileges(users[0], str(group_chat.id), action="" )
        
        assert has_priv is True

    async def test_group_creator_can_delete(self, users, group_chat):
        """Test that group creator has privileges to delete group chat"""
        has_priv, _ = await permission_handler.have_admin_privileges(users[0], str(group_chat.id), action="delete" )
        
        assert has_priv is True

    async def test_group_admin_has_admin_privileges(self, users, group_chat):
        """Test that group admin has admin privileges"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="")
        
        assert has_priv is True

    async def test_group_admin_cannot_delete(self, users, group_chat):
        """Test that group admin cannot carry out delete action"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        await database_sync_to_async(group_chat.admins.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="delete")
        
        assert has_priv is False

    async def test_group_regular_member_no_admin_privileges(self, users, group_chat):
        """Test that regular member has no admin privileges"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="")
        
        assert has_priv is False

    async def test_group_regular_member_cannot_delete_groupchat(self, users, group_chat):
        """Test that regular member has no privileges to delete groupchat"""
        await database_sync_to_async(group_chat.participants.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="delete")
        
        assert has_priv is False

    async def test_channel_creator_has_admin_privileges(self, users, channel):
        """Test that channel creator has admin privileges"""
        has_priv, _ = await permission_handler.have_admin_privileges(users[0], str(channel.id), action="")
        
        assert has_priv is True

    async def test_channel_creator_can_delete(self, users, channel):
        """Test that channel creator has privileges to delete the channel"""
        has_priv, _ = await permission_handler.have_admin_privileges(users[0], str(channel.id), action="delete")
        
        assert has_priv is True

    async def test_channel_moderator_has_admin_privileges(self, users, channel):
        """Test that channel moderator has admin privileges"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(channel.moderators.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(channel.id), action="")
        
        assert has_priv is True

    async def test_channel_moderator_cannot_delete_channel(self, users, channel):
        """Test that channel moderator cannot delete channel"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(channel.moderators.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(channel.id), action="delete")
        
        assert has_priv is False

    async def test_channel_regular_subscriber_no_admin_privileges(self, users, channel):
        """Test that regular subscriber has no admin privileges"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(channel.id), action="")
        
        assert has_priv is False

    async def test_channel_regular_subscriber_cannot_delete_channel(self, users, channel):
        """Test that regular subscriber cannot delete channel"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(channel.id), action="delete")
        
        assert has_priv is False

    async def test_non_member_no_admin_privileges(self, users, group_chat):
        """Test that non-member has no admin privileges"""
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="")
        
        assert has_priv is False

    async def test_non_member_cannot_delete_room(self, users, group_chat):
        """Test that non-member cannot delete room"""
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="delete")
        
        assert has_priv is False
    
    async def test_any_onetonechat_member_can_delete_chat(self, users, one_to_one_chat):
        """Test that any participants of one_to_one_chat can delete chat"""
        
        has_priv0, _ = await permission_handler.have_admin_privileges(users[0], str(one_to_one_chat.id), action="delete")
        has_priv1, _ = await permission_handler.have_admin_privileges(users[1], str(one_to_one_chat.id), action="delete")
        
        assert has_priv0 is True
        assert has_priv1 is True

    async def test_non_onetonechat_member_cannot_delete_chat(self, users, one_to_one_chat):
        """Test that non participants of one_to_one_chat cannot delete chat"""
        
        has_priv, _ = await permission_handler.have_admin_privileges(users[3], str(one_to_one_chat.id), action="delete")
     
        assert has_priv is False



    async def test_member_with_permissions_do_not_have_admin_privileges(self, users, channel, group_chat):
        """Test that non moderator/admin member with permission has no admin privileges"""
        await database_sync_to_async(channel.subscribers.add)(users[1])
        await database_sync_to_async(group_chat.participants.add)(users[1])
        from guardian.shortcuts import assign_perm
        await database_sync_to_async(assign_perm)('can_add_new_participants', users[1], group_chat)
        await database_sync_to_async(assign_perm)('can_remove_participants', users[1], group_chat)
        await database_sync_to_async(assign_perm)('can_add_new_subscribers', users[1], channel)
        await database_sync_to_async(assign_perm)('can_remove_subscribers', users[1], channel)
        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(group_chat.id), action="")
        assert has_priv is False

        has_priv, _ = await permission_handler.have_admin_privileges(users[1], str(channel.id), action="")
        assert has_priv is False