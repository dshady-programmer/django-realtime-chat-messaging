import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from guardian.shortcuts import assign_perm, remove_perm
from realtime_chat_messaging.models import (
    OneToOneChat, GroupChat, Channel, Message,
    ReadReceipt, Reaction, ChatNotification, MessageMediaAsset
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
def one_to_one_chat(users):
    """Create a one-to-one chat"""
    chat = OneToOneChat.objects.create()
    chat.participants.set([users['user1'], users['user2']])
    return chat


@pytest.fixture
def group_chat(users):
    """Create a group chat"""
    group = GroupChat.objects.create(
        name="Test Group",
        description="A test group",
        creator=users['user1']
    )
    return group


@pytest.fixture
def channel(users):
    """Create a channel"""
    chan = Channel.objects.create(
        name="Test Channel",
        description="A test channel",
        creator=users['user1'],
        is_public=True
    )
    return chan


class TestOneToOneChat:
    """Test suite for OneToOneChat model"""

    def test_create_one_to_one_chat_success(self, users):
        """Test successful creation of one-to-one chat"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users['user1'], users['user2']])
        
        assert chat.participants.count() == 2
        assert users['user1'] in chat.participants.all()
        assert users['user2'] in chat.participants.all()

    def test_one_to_one_chat_enforces_two_participants(self, users):
        """Test that one-to-one chat enforces exactly 2 participants"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users['user1'], users['user2']])
        
        # Try adding a third participant
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            chat.participants.add(users['user3'])

    def test_one_to_one_chat_prevents_less_than_two_participants(self, users):
        """Test that one-to-one chat prevents having less than 2 participants"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users['user1'], users['user2']])
        
        # Try removing a participant
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            chat.participants.remove(users['user1'])

    def test_duplicate_one_to_one_chat_prevented(self, users):
        """Test that duplicate one-to-one chats are prevented"""
        chat1 = OneToOneChat.objects.create()
        chat1.participants.set([users['user1'], users['user2']])
        
        # Try creating duplicate
        chat2 = OneToOneChat.objects.create()
        with pytest.raises(ValidationError, match="Chat already exists"):
            chat2.participants.set([users['user1'], users['user2']])

    def test_one_to_one_chat_preferences(self, one_to_one_chat):
        """Test preferences field works correctly"""
        preferences = {"theme": "dark", "notifications": True}
        one_to_one_chat.preferences = preferences
        one_to_one_chat.save()
        one_to_one_chat.refresh_from_db()
        
        assert one_to_one_chat.preferences == preferences

    def test_one_to_one_chat_last_message(self, one_to_one_chat, users):
        """Test last_message field updates correctly"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test message"
        )
        one_to_one_chat.last_message = message
        one_to_one_chat.save()
        one_to_one_chat.refresh_from_db()
        
        assert one_to_one_chat.last_message == message


class TestGroupChat:
    """Test suite for GroupChat model"""

    def test_create_group_chat_success(self, users):
        """Test successful creation of group chat"""
        group = GroupChat.objects.create(
            name="New Group",
            description="Test group",
            creator=users['user1']
        )
        
        assert group.name == "New Group"
        assert group.creator == users['user1']
        assert group.participants.count() == 1
        assert group.admins.count() == 1
        assert users['user1'] in group.participants.all()
        assert users['user1'] in group.admins.all()

    def test_creator_automatically_added_as_participant_and_admin(self, users):
        """Test that creator is automatically added as participant and admin"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users['user1']
        )
        
        assert users['user1'] in group.participants.all()
        assert users['user1'] in group.admins.all()

    def test_creator_gets_permissions(self, users):
        """Test that creator gets add/remove participant permissions"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users['user1']
        )
        
        assert users['user1'].has_perm('can_add_new_participants', group)
        assert users['user1'].has_perm('can_remove_participants', group)

    def test_add_participants_to_group(self, group_chat, users):
        """Test adding participants to group"""
        group_chat.participants.add(users['user2'], users['user3'])
        
        assert group_chat.participants.count() == 3
        assert users['user2'] in group_chat.participants.all()
        assert users['user3'] in group_chat.participants.all()

    def test_max_participants_enforcement(self, group_chat, users):
        """Test that max_participants limit is enforced"""
        group_chat.max_participants = 2
        group_chat.save()
        
        # Already has user1 (creator)
        group_chat.participants.add(users['user2'])
        
        # Try adding beyond limit
        with pytest.raises(ValidationError, match="Maximum number of group participants exceeded"):
            group_chat.participants.add(users['user3'])

    def test_group_deleted_when_no_participants(self, group_chat, users):
        """Test that group is deleted when all participants leave"""
        group_chat.participants.remove(users['user1'])
        
        assert not GroupChat.objects.filter(id=group_chat.id).exists()

    def test_add_admin_grants_permissions(self, group_chat, users):
        """Test that adding admin grants permissions"""
        group_chat.participants.add(users['user2'])
        group_chat.admins.add(users['user2'])
        
        assert users['user2'].has_perm('can_add_new_participants', group_chat)
        assert users['user2'].has_perm('can_remove_participants', group_chat)

    def test_remove_admin_revokes_permissions(self, group_chat, users):
        """Test that removing admin revokes permissions"""
        group_chat.participants.add(users['user2'])
        group_chat.admins.add(users['user2'])
        
        # Verify permissions granted
        assert users['user2'].has_perm('can_add_new_participants', group_chat)
        
        # Remove admin
        group_chat.admins.remove(users['user2'])
        
        # Verify permissions revoked
        assert not users['user2'].has_perm('can_add_new_participants', group_chat)
        assert not users['user2'].has_perm('can_remove_participants', group_chat)

    def test_group_locked_feature(self, group_chat):
        """Test group_locked field"""
        assert not group_chat.group_locked
        
        group_chat.group_locked = True
        group_chat.save()
        group_chat.refresh_from_db()
        
        assert group_chat.group_locked


class TestChannel:
    """Test suite for Channel model"""

    def test_create_channel_success(self, users):
        """Test successful creation of channel"""
        channel = Channel.objects.create(
            name="New Channel",
            description="Test channel",
            creator=users['user1'],
            is_public=True
        )
        
        assert channel.name == "New Channel"
        assert channel.creator == users['user1']
        assert channel.subscribers.count() == 1
        assert channel.moderators.count() == 1
        assert users['user1'] in channel.subscribers.all()
        assert users['user1'] in channel.moderators.all()

    def test_creator_automatically_added_as_subscriber_and_moderator(self, users):
        """Test that creator is automatically added as subscriber and moderator"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users['user1']
        )
        
        assert users['user1'] in channel.subscribers.all()
        assert users['user1'] in channel.moderators.all()

    def test_creator_gets_channel_permissions(self, users):
        """Test that creator gets channel permissions"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users['user1']
        )
        
        assert users['user1'].has_perm('can_add_new_subscribers', channel)
        assert users['user1'].has_perm('can_remove_subscribers', channel)
        assert users['user1'].has_perm('can_send_messages', channel)

    def test_add_subscribers_to_channel(self, channel, users):
        """Test adding subscribers to channel"""
        channel.subscribers.add(users['user2'], users['user3'])
        
        assert channel.subscribers.count() == 3
        assert users['user2'] in channel.subscribers.all()
        assert users['user3'] in channel.subscribers.all()

    def test_max_subscribers_enforcement(self, channel, users):
        """Test that max_subscribers limit is enforced"""
        channel.max_subscribers = 2
        channel.save()
        
        # Already has user1 (creator)
        channel.subscribers.add(users['user2'])
        
        # Try adding beyond limit
        with pytest.raises(ValidationError, match="Maximum number of channel subscribers exceeded"):
            channel.subscribers.add(users['user3'])

    def test_channel_deleted_when_no_subscribers(self, channel, users):
        """Test that channel is deleted when all subscribers leave"""
        channel.subscribers.remove(users['user1'])
        
        assert not Channel.objects.filter(id=channel.id).exists()

    def test_add_moderator_grants_permissions(self, channel, users):
        """Test that adding moderator grants permissions"""
        channel.subscribers.add(users['user2'])
        channel.moderators.add(users['user2'])
        
        assert users['user2'].has_perm('can_add_new_subscribers', channel)
        assert users['user2'].has_perm('can_remove_subscribers', channel)
        assert users['user2'].has_perm('can_send_messages', channel)

    def test_remove_moderator_revokes_permissions(self, channel, users):
        """Test that removing moderator revokes permissions"""
        channel.subscribers.add(users['user2'])
        channel.moderators.add(users['user2'])
        
        # Verify permissions granted
        assert users['user2'].has_perm('can_send_messages', channel)
        
        # Remove moderator
        channel.moderators.remove(users['user2'])
        
        # Verify permissions revoked
        assert not users['user2'].has_perm('can_add_new_subscribers', channel)
        assert not users['user2'].has_perm('can_remove_subscribers', channel)
        assert not users['user2'].has_perm('can_send_messages', channel)

    def test_public_channel_flag(self, channel):
        """Test is_public field"""
        assert channel.is_public
        
        channel.is_public = False
        channel.save()
        channel.refresh_from_db()
        
        assert not channel.is_public


class TestMessage:
    """Test suite for Message model"""

    def test_create_message_success(self, one_to_one_chat, users):
        """Test successful message creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Hello World"
        )
        
        assert message.content == "Hello World"
        assert message.sender == users['user1']
        assert message.room == one_to_one_chat
        assert not message.is_forwarded
        assert not message.is_edited
        assert not message.is_deleted

    def test_message_reply(self, one_to_one_chat, users):
        """Test message reply functionality"""
        original = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original message"
        )
        
        reply = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user2'],
            content="Reply to message",
            parent_message=original
        )
        
        assert reply.parent_message == original
        assert original.replies.count() == 1
        assert reply in original.replies.all()

    def test_message_forward(self, one_to_one_chat, group_chat, users):
        """Test message forwarding"""
        original = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original message"
        )
        
        forwarded = Message.objects.create(
            room=group_chat,
            sender=users['user1'],
            content="Original message",
            is_forwarded=True,
            forwarded_from=original
        )
        
        assert forwarded.is_forwarded
        assert forwarded.forwarded_from == original

    def test_forwarded_message_cannot_be_reply(self, one_to_one_chat, group_chat, users):
        """Test that forwarded messages cannot be replies (constraint)"""
        original = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original"
        )
        
        parent = Message.objects.create(
            room=group_chat,
            sender=users['user1'],
            content="Parent"
        )
        
        # This should violate the constraint
        with pytest.raises(IntegrityError):
            Message.objects.create(
                room=group_chat,
                sender=users['user1'],
                content="Invalid",
                is_forwarded=True,
                forwarded_from=original,
                parent_message=parent
            )

    def test_message_edit_flag(self, one_to_one_chat, users):
        """Test message edit functionality"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original content"
        )
        
        message.content = "Edited content"
        message.is_edited = True
        message.save()
        message.refresh_from_db()
        
        assert message.content == "Edited content"
        assert message.is_edited

    def test_message_soft_delete(self, one_to_one_chat, users):
        """Test message soft delete"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="To be deleted"
        )
        
        message.is_deleted = True
        message.save()
        message.refresh_from_db()
        
        assert message.is_deleted

    def test_message_delivered_to(self, one_to_one_chat, users):
        """Test delivered_to many-to-many field"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        message.delivered_to.add(users['user2'])
        
        assert users['user2'] in message.delivered_to.all()
        assert message.delivered_to.count() == 1


class TestReadReceipt:
    """Test suite for ReadReceipt model"""

    def test_create_read_receipt_success(self, one_to_one_chat, users):
        """Test successful read receipt creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        receipt = ReadReceipt.objects.create(
            message=message,
            reader=users['user2']
        )
        
        assert receipt.message == message
        assert receipt.reader == users['user2']
        assert receipt.read_at is not None

    def test_unique_read_receipt_constraint(self, one_to_one_chat, users):
        """Test that a user can only have one read receipt per message"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        ReadReceipt.objects.create(message=message, reader=users['user2'])
        
        # Try creating duplicate
        with pytest.raises(IntegrityError):
            ReadReceipt.objects.create(message=message, reader=users['user2'])

    def test_multiple_users_can_read_same_message(self, group_chat, users):
        """Test that multiple users can read the same message"""
        message = Message.objects.create(
            room=group_chat,
            sender=users['user1'],
            content="Test"
        )
        
        ReadReceipt.objects.create(message=message, reader=users['user2'])
        ReadReceipt.objects.create(message=message, reader=users['user3'])
        
        assert message.read_receipts.count() == 2


class TestReaction:
    """Test suite for Reaction model"""

    def test_create_reaction_success(self, one_to_one_chat, users):
        """Test successful reaction creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        reaction = Reaction.objects.create(
            message=message,
            user=users['user2'],
            reaction_content="👍"
        )
        
        assert reaction.message == message
        assert reaction.user == users['user2']
        assert reaction.reaction_content == "👍"

    def test_unique_reaction_per_user_per_message(self, one_to_one_chat, users):
        """Test that a user can only have one reaction per message"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        Reaction.objects.create(message=message, user=users['user2'], reaction_content="👍")
        
        # Try creating duplicate
        with pytest.raises(IntegrityError):
            Reaction.objects.create(message=message, user=users['user2'], reaction_content="❤️")

    def test_reaction_update_deletes_old(self, one_to_one_chat, users):
        """Test that updating reaction deletes old one (signal)"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        reaction1 = Reaction.objects.create(
            message=message,
            user=users['user2'],
            reaction_content="👍"
        )
        
        # Create new reaction with different content
        reaction2 = Reaction(
            message=message,
            user=users['user2'],
            reaction_content="❤️"
        )
        reaction2.save()
        
        # Old reaction should be deleted
        assert not Reaction.objects.filter(id=reaction1.id).exists()
        assert Reaction.objects.filter(message=message, user=users['user2']).count() == 1

    def test_empty_reaction_content_raises_error(self, one_to_one_chat, users):
        """Test that empty reaction content raises ValidationError"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        reaction = Reaction(
            message=message,
            user=users['user2'],
            reaction_content=""
        )
        
        with pytest.raises(ValidationError, match="reaction_content can't be empty"):
            reaction.save()


class TestChatNotification:
    """Test suite for ChatNotification model"""

    def test_create_chat_notification_success(self, one_to_one_chat, users):
        """Test successful chat notification creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        notification = ChatNotification.objects.create(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        notification.recipients.add(users['user2'])
        
        assert notification.message == message
        assert notification.notification_type == 'NEW_MESSAGE'
        assert users['user2'] in notification.recipients.all()

    def test_notification_deleted_when_no_recipients(self, one_to_one_chat, users):
        """Test that notification is deleted when all recipients are removed"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        notification = ChatNotification.objects.create(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        notification.recipients.add(users['user2'])
        notification_id = notification.id
        
        # Remove all recipients
        notification.recipients.remove(users['user2'])
        
        # Notification should be deleted
        assert not ChatNotification.objects.filter(id=notification_id).exists()

    def test_notification_types(self, one_to_one_chat, users):
        """Test different notification types"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        for noti_type, _ in [('REACTION', 'Reaction'), ('NEW_MESSAGE', 'New Message'), ('REPLY', 'Reply')]:
            notification = ChatNotification.objects.create(
                message=message,
                notification_type=noti_type
            )
            assert notification.notification_type == noti_type


class TestMessageMediaAsset:
    """Test suite for MessageMediaAsset model"""

    def test_create_media_asset_success(self, one_to_one_chat, users):
        """Test successful media asset creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Media message"
        )
        
        asset = MessageMediaAsset.objects.create(
            message=message,
            media_url="https://example.com/image.jpg",
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024
        )
        
        assert asset.message == message
        assert asset.media_url == "https://example.com/image.jpg"
        assert asset.media_type == "image"
        assert asset.mime_type == "image/jpeg"

    def test_media_asset_with_metadata(self, one_to_one_chat, users):
        """Test media asset with metadata"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Video message"
        )
        
        metadata = {
            "duration": 15.2,
            "resolution": "1080x1920",
            "fps": 30
        }
        
        asset = MessageMediaAsset.objects.create(
            message=message,
            media_url="https://example.com/video.mp4",
            media_type="video",
            mime_type="video/mp4",
            file_size=2048000,
            metadata=metadata
        )
        
        assert asset.metadata == metadata

    def test_invalid_mime_type_constraint(self, one_to_one_chat, users):
        """Test that invalid mime types are rejected"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Media message"
        )
        
        with pytest.raises(IntegrityError):
            MessageMediaAsset.objects.create(
                message=message,
                media_url="https://example.com/file.invalid",
                media_type="file",
                mime_type="application/invalid",  # Not in ALLOWED_MIME_TYPES
                file_size=1024
            )

    def test_multiple_media_assets_per_message(self, one_to_one_chat, users):
        """Test that a message can have multiple media assets"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Multiple media"
        )
        
        MessageMediaAsset.objects.create(
            message=message,
            media_url="https://example.com/image1.jpg",
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024
        )
        
        MessageMediaAsset.objects.create(
            message=message,
            media_url="https://example.com/image2.png",
            media_type="image",
            mime_type="image/png",
            file_size=2048
        )
        
        assert message.attachments.count() == 2