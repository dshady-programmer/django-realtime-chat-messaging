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


class TestOneToOneChat:
    """Test suite for OneToOneChat model"""

    def test_create_one_to_one_chat_success(self, one_to_one_chat, users):
        """Test successful creation of one-to-one chat"""

        
        assert one_to_one_chat.participants.count() == 2
        assert users[0] in one_to_one_chat.participants.all()
        assert users[1] in one_to_one_chat.participants.all()

    def test_one_to_one_chat_enforces_two_participants(self, one_to_one_chat, users):
        """Test that one-to-one chat enforces exactly 2 participants"""
        
        # Try adding a third participant
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            one_to_one_chat.participants.add(users[2])

    def test_one_to_one_chat_prevents_less_than_two_participants(self, one_to_one_chat, users):
        """Test that one-to-one chat prevents having less than 2 participants"""
        
        # Try removing a participant
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            one_to_one_chat.participants.remove(users[1])

    def test_duplicate_one_to_one_chat_prevented(self, one_to_one_chat, users):
        """Test that duplicate one-to-one chats are prevented"""
        # Try creating duplicate
        chat2 = OneToOneChat.objects.create()
        with pytest.raises(ValidationError, match="Chat already exists"):
            chat2.participants.set([users[0], users[1]])

    def test_one_to_one_chat_preferences(self, one_to_one_chat):
        """Test preferences field works correctly"""
        preferences = {"theme": "dark", "notifications": True}
        one_to_one_chat.preferences = preferences
        one_to_one_chat.save()
        one_to_one_chat.refresh_from_db()
        
        assert one_to_one_chat.preferences == preferences



class TestGroupChat:
    """Test suite for GroupChat model"""

    def test_create_group_chat_success(self, group_chat, users):
        """Test successful creation of group chat"""
        
        assert group_chat.name == "Test Group"
        assert group_chat.creator == users[0]
        assert group_chat.participants.count() == 1
        assert group_chat.admins.count() == 1
    
    def test_creator_automatically_added_as_participant_and_admin(self, group_chat, users):
        """Test that creator is automatically added as participant and admin"""

        
        assert users[0] in group_chat.participants.all()
        assert users[0] in group_chat.admins.all()

    def test_creator_gets_permissions(self, group_chat, users):
        """Test that creator gets add/remove participant permissions"""
        
        assert users[0].has_perm('can_add_new_participants', group_chat)
        assert users[0].has_perm('can_remove_participants', group_chat)

    def test_add_participants_to_group(self, group_chat, users):
        """Test adding participants to group"""
        group_chat.participants.add(users[1], users[2])
        
        assert group_chat.participants.count() == 3
        assert users[1] in group_chat.participants.all()
        assert users[2] in group_chat.participants.all()

    def test_max_participants_enforcement(self, group_chat, users):
        """Test that max_participants limit is enforced"""
        group_chat.max_participants = 2
        group_chat.save()
        
        # Already has user1 (creator)
        group_chat.participants.add(users[1])
        
        # Try adding beyond limit
        with pytest.raises(ValidationError, match="Maximum number of group participants exceeded"):
            group_chat.participants.add(users[2])

    def test_group_deleted_when_no_participants(self, group_chat, users):
        """Test that group is deleted when all participants leave"""
        group_chat.participants.remove(users[0])
        
        assert not GroupChat.objects.filter(id=group_chat.id).exists()

    def test_add_admin_grants_permissions(self, group_chat, users):
        """Test that adding admin grants permissions"""
        group_chat.participants.add(users[1])
        group_chat.admins.add(users[1])
        
        assert users[1].has_perm('can_add_new_participants', group_chat)
        assert users[1].has_perm('can_remove_participants', group_chat)

    def test_remove_admin_revokes_permissions(self, group_chat, users):
        """Test that removing admin revokes permissions"""
        group_chat.participants.add(users[1])
        group_chat.admins.add(users[1])
        
        # Verify permissions granted
        assert users[1].has_perm('can_add_new_participants', group_chat)
        
        # Remove admin
        group_chat.admins.remove(users[1])
        
        # Verify permissions revoked
        assert not users[1].has_perm('can_add_new_participants', group_chat)
        assert not users[1].has_perm('can_remove_participants', group_chat)



class TestChannel:
    """Test suite for Channel model"""

    def test_create_channel_success(self, channel, users):
        """Test successful creation of channel"""
   
        assert channel.name == "Test Channel"
        assert channel.creator == users[0]
        assert channel.subscribers.count() == 1
        assert channel.moderators.count() == 1
        assert users[0] in channel.subscribers.all()
        assert users[0] in channel.moderators.all()

    def test_creator_automatically_added_as_subscriber_and_moderator(self, channel, users):
        """Test that creator is automatically added as subscriber and moderator"""

        
        assert users[0] in channel.subscribers.all()
        assert users[0] in channel.moderators.all()

    def test_creator_gets_channel_permissions(self, channel,  users):
        """Test that creator gets channel permissions"""

        
        assert users[0].has_perm('can_add_new_subscribers', channel)
        assert users[0].has_perm('can_remove_subscribers', channel)
        assert users[0].has_perm('can_send_messages', channel)

    def test_add_subscribers_to_channel(self, channel, users):
        """Test adding subscribers to channel"""
        channel.subscribers.add(users[1], users[2])
        
        assert channel.subscribers.count() == 3
        assert users[1] in channel.subscribers.all()
        assert users[2] in channel.subscribers.all()

    def test_max_subscribers_enforcement(self, channel, users):
        """Test that max_subscribers limit is enforced"""
        channel.max_subscribers = 2
        channel.save()
        
        # Already has user1 (creator)
        channel.subscribers.add(users[1])
        
        # Try adding beyond limit
        with pytest.raises(ValidationError, match="Maximum number of channel subscribers exceeded"):
            channel.subscribers.add(users[2])

    def test_channel_deleted_when_no_subscribers(self, channel, users):
        """Test that channel is deleted when all subscribers leave"""
        channel.subscribers.remove(users[0])
        
        assert not Channel.objects.filter(id=channel.id).exists()

    def test_add_moderator_grants_permissions(self, channel, users):
        """Test that adding moderator grants permissions"""
        channel.subscribers.add(users[2])
        channel.moderators.add(users[2])
        
        assert users[2].has_perm('can_add_new_subscribers', channel)
        assert users[2].has_perm('can_remove_subscribers', channel)
        assert users[2].has_perm('can_send_messages', channel)

    def test_remove_moderator_revokes_permissions(self, channel, users):
        """Test that removing moderator revokes permissions"""
        channel.subscribers.add(users[3])
        channel.moderators.add(users[3])
        
        # Verify permissions granted
        assert users[3].has_perm('can_send_messages', channel)
        
        # Remove moderator
        channel.moderators.remove(users[3])
        
        # Verify permissions revoked
        assert not users[3].has_perm('can_add_new_subscribers', channel)
        assert not users[3].has_perm('can_remove_subscribers', channel)
        assert not users[3].has_perm('can_send_messages', channel)

    def test_public_channel_flag(self, channel):
        """Test is_public field"""
        assert channel.is_public
        
        channel.is_public = False
        channel.save()
        channel.refresh_from_db()
        
        assert not channel.is_public


class TestMessage:
    """Test suite for Message model"""

    def test_create_message_success(self, one_to_one_chat, create_message, users):
        """Test successful message creation"""

        message = create_message(   
            room=one_to_one_chat,
            sender=users[1],
            content="Hello World"
        )
        assert message.content == "Hello World"
        assert message.sender == users[1]
        assert message.room == one_to_one_chat
        assert not message.is_forwarded
        assert not message.is_edited
        assert not message.is_deleted

    def test_message_reply(self, one_to_one_chat, create_message, users):
        """Test message reply functionality"""
        original = create_message(
            room=one_to_one_chat,
            sender=users[0],
            content="Original message"
        )
        
        reply = create_message(
            room=one_to_one_chat,
            sender=users[1],
            content="Reply to message",
            parent_message=original
        )
        
        assert reply.parent_message == original
        assert original.replies.count() == 1
        assert reply in original.replies.all()

    def test_message_forward(self, one_to_one_chat, group_chat,create_message, users):
        """Test message forwarding"""
        original = create_message(
            room=one_to_one_chat,
            sender=users[0],
            content="Original message"
        )
        
        forwarded = create_message(
            room=group_chat,
            sender=users[0],
            content="Original message",
            is_forwarded=True,
            forwarded_from=original
        )
        
        assert forwarded.is_forwarded
        assert forwarded.forwarded_from == original

    def test_forwarded_message_cannot_be_reply(self, one_to_one_chat, group_chat, create_message, users):
        """Test that forwarded messages cannot be replies (constraint)"""
        original = create_message(
            room=one_to_one_chat,
            sender=users[0],
            content="Original"
        )
        
        parent = create_message(
            room=group_chat,
            sender=users[0],
            content="Parent"
        )
        
        # This should violate the constraint
        with pytest.raises(IntegrityError):
            create_message(
                room=group_chat,
                sender=users[0],
                content="Invalid",
                is_forwarded=True,
                forwarded_from=original,
                parent_message=parent
            )

    def test_message_edit_flag(self, one_to_one_chat, create_message, users):
        """Test message edit functionality"""
        message = create_message(
            room=one_to_one_chat,
            sender=users[0],
            content="Original content"
        )
        
        message.content = "Edited content"
        message.is_edited = True
        message.save()
        message.refresh_from_db()
        
        assert message.content == "Edited content"
        assert message.is_edited

    def test_message_soft_delete(self, one_to_one_chat, create_message, users):
        """Test message soft delete"""
        message = create_message(
            room=one_to_one_chat,
            sender=users[0],
            content="To be deleted"
        )
        
        message.is_deleted = True
        message.save()
        message.refresh_from_db()
        
        assert message.is_deleted

    def test_message_delivered_to(self, one_to_one_chat, create_message, users):
        """Test delivered_to many-to-many field"""
        message = create_message(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        message.delivered_to.add(users[1])
        
        assert users[1] in message.delivered_to.all()
        assert message.delivered_to.count() == 1


class TestReadReceipt:
    """Test suite for ReadReceipt model"""

    def test_create_read_receipt_success(self, one_to_one_chat, users):
        """Test successful read receipt creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        receipt = ReadReceipt.objects.create(
            message=message,
            reader=users[1]
        )
        
        assert message.read_receipts.count() == 1
        assert receipt in message.read_receipts.all()
        assert receipt.message == message
        assert receipt.reader == users[1]
        import datetime
        assert receipt.read_at is not None and isinstance(receipt.read_at, datetime.datetime)

    def test_unique_read_receipt_constraint(self, one_to_one_chat, users):
        """Test that a user can only have one read receipt per message"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[1],
            content="Test"
        )
        
        ReadReceipt.objects.create(message=message, reader=users[2])
        
        # Try creating duplicate
        with pytest.raises(IntegrityError):
            ReadReceipt.objects.create(message=message, reader=users[2])

    def test_multiple_users_can_read_same_message(self, group_chat, users):
        """Test that multiple users can read the same message"""
        message = Message.objects.create(
            room=group_chat,
            sender=users[0],
            content="Test"
        )
        
        ReadReceipt.objects.create(message=message, reader=users[1])
        ReadReceipt.objects.create(message=message, reader=users[2])
        
        assert message.read_receipts.count() == 2


class TestReaction:
    """Test suite for Reaction model"""

    def test_create_reaction_success(self, one_to_one_chat, users):
        """Test successful reaction creation"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        reaction = Reaction.objects.create(
            message=message,
            user=users[1],
            reaction_content="👍"
        )
        
        assert reaction.message == message
        assert reaction.user == users[1]
        assert reaction.reaction_content == "👍"

    def test_unique_reaction_per_user_per_message(self, one_to_one_chat, users):
        """Test that a user can only have one reaction per message"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        Reaction.objects.create(message=message, user=users[1], reaction_content="👍")
        
        # Try creating duplicate
        with pytest.raises(IntegrityError):
            Reaction.objects.create(message=message, user=users[1], reaction_content="👍")

    def test_reaction_update_deletes_old(self, one_to_one_chat, users):
        """Test that updating reaction deletes old one (signal)"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        reaction1 = Reaction.objects.create(
            message=message,
            user=users[1],
            reaction_content="👍"
        )
        
        # Create new reaction with different content
        reaction2 = Reaction.objects.create(
            message=message,
            user=users[1],
            reaction_content="❤️"
        )
    
        
        # Old reaction should be deleted
        assert not Reaction.objects.filter(id=reaction1.id).exists()
        assert Reaction.objects.filter(message=message, user=users[1]).count() == 1
        assert Reaction.objects.filter(message=message, user=users[1]).first() == reaction2
        assert Reaction.objects.filter(message=message, user=users[1]).first().reaction_content == reaction2.reaction_content


    def test_empty_reaction_content_raises_error(self, one_to_one_chat, users):
        """Test that empty reaction content raises ValidationError"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        reaction = Reaction(
            message=message,
            user=users[1],
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
            sender=users[0],
            content="Test"
        )
        
        notification = ChatNotification.objects.create(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        notification.recipients.add(users[1])
        
        assert notification.message == message
        assert notification.notification_type == 'NEW_MESSAGE'
        assert users[1] in notification.recipients.all()

    def test_notification_deleted_when_no_recipients(self, one_to_one_chat, users):
        """Test that notification is deleted when all recipients are removed"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        notification = ChatNotification.objects.create(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        notification.recipients.add(users[1])
        notification_id = notification.id
        
        # Remove all recipients
        notification.recipients.remove(users[1])
        
        # Notification should be deleted
        assert not ChatNotification.objects.filter(id=notification_id).exists()

    def test_notification_types(self, one_to_one_chat, users):
        """Test different notification types"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        from realtime_chat_messaging.types import NOTIFICATION_TYPE
        for noti_type, _ in NOTIFICATION_TYPE:
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
            sender=users[0],
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
            sender=users[0],
            content="Media message"
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
            sender=users[0],
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

    def test_multiple_media_assets_per_message(self, group_chat, users):
        """Test that a message can have multiple media assets"""
        message = Message.objects.create(
            room=group_chat,
            sender=users[0],
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