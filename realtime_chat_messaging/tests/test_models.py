"""
Tests for chat application models
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from unittest.mock import patch
import uuid

from realtime_chat_messaging.models import (
    Room, OneToOneChat, GroupChat, Channel, Message,
    ReadReceipt, ChatNotification, Reaction, MessageMediaAsset
)

User = get_user_model()


class RoomModelTest(TestCase):
    """Test the base Room model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_room_creation(self):
        """Test creating a basic room"""
        room = Room.objects.create()
        self.assertIsInstance(room.id, uuid.UUID)
        self.assertIsNotNone(room.created_at)
        self.assertIsNotNone(room.updated_at)
        self.assertEqual(room.preferences, {})

    def test_room_preferences_default(self):
        """Test that preferences defaults to empty dict"""
        room = Room.objects.create()
        self.assertIsInstance(room.preferences, dict)
        self.assertEqual(len(room.preferences), 0)

    def test_room_preferences_custom(self):
        """Test setting custom preferences"""
        prefs = {'theme': 'dark', 'notifications': True}
        room = Room.objects.create(preferences=prefs)
        self.assertEqual(room.preferences, prefs)


class OneToOneChatModelTest(TestCase):
    """Test OneToOneChat model"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.user3 = User.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='pass123'
        )

    def test_one_to_one_chat_creation(self):
        """Test creating a one-to-one chat"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        self.assertEqual(chat.participants.count(), 2)
        self.assertIn(self.user1, chat.participants.all())
        self.assertIn(self.user2, chat.participants.all())

    def test_one_to_one_chat_participants_relationship(self):
        """Test the reverse relationship from User"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        self.assertIn(chat, self.user1.chats.all())
        self.assertIn(chat, self.user2.chats.all())


class GroupChatModelTest(TestCase):
    """Test GroupChat model"""

    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass123'
        )
        self.member1 = User.objects.create_user(
            username='member1',
            email='member1@example.com',
            password='pass123'
        )
        self.member2 = User.objects.create_user(
            username='member2',
            email='member2@example.com',
            password='pass123'
        )

    def test_group_chat_creation(self):
        """Test creating a group chat"""
        group = GroupChat.objects.create(
            name='Test Group',
            description='A test group',
            creator=self.creator
        )
        self.assertEqual(group.name, 'Test Group')
        self.assertEqual(group.description, 'A test group')
        self.assertEqual(group.creator, self.creator)
        self.assertIn(self.creator, group.participants.all())
        self.assertIn(self.creator, group.admins.all())

    def test_group_chat_max_participants_default(self):
        """Test default max participants"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        self.assertEqual(group.max_participants, 10)

    def test_group_chat_participants(self):
        """Test adding participants to group"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group.participants.add(self.member1, self.member2)
        self.assertEqual(group.participants.count(), 3)

    def test_group_chat_admins(self):
        """Test adding admins to group"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group.admins.add(self.member1)
        self.assertEqual(group.admins.count(), 2)

    def test_group_chat_avatar_optional(self):
        """Test that avatar is optional"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        self.assertIsNone(group.avatar)

    def test_group_chat_avatar_url(self):
        """Test setting avatar URL"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator,
            avatar='https://example.com/avatar.jpg'
        )
        self.assertEqual(group.avatar, 'https://example.com/avatar.jpg')

    def test_group_chat_join_approval_default(self):
        """Test default join approval setting"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        self.assertFalse(group.join_approval_required)

    def test_group_chat_group_locked_default(self):
        """Test default group locked setting"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        self.assertFalse(group.group_locked)

    def test_group_chat_reverse_relationships(self):
        """Test reverse relationships"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group.participants.add(self.member1)
        group.admins.add(self.creator)
        
        self.assertIn(group, self.creator.groups_owned.all())
        self.assertIn(group, self.member1.groups_in.all())
        self.assertIn(group, self.creator.groups_moderated.all())


class ChannelModelTest(TestCase):
    """Test Channel model"""

    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass123'
        )
        self.subscriber = User.objects.create_user(
            username='subscriber',
            email='subscriber@example.com',
            password='pass123'
        )

    def test_channel_creation(self):
        """Test creating a channel"""
        channel = Channel.objects.create(
            name='Test Channel',
            description='A test channel',
            creator=self.creator
        )
        self.assertEqual(channel.name, 'Test Channel')
        self.assertEqual(channel.description, 'A test channel')
        self.assertEqual(channel.creator, self.creator)
        self.assertIn(self.creator, channel.subscribers.all())
        self.assertIn(self.creator, channel.moderators.all())

    def test_channel_is_public_default(self):
        """Test default is_public setting"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        self.assertFalse(channel.is_public)

    def test_channel_subscribers(self):
        """Test adding subscribers"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel.subscribers.add(self.subscriber)
        self.assertEqual(channel.subscribers.count(), 2)

    def test_channel_moderators(self):
        """Test adding moderators"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel.moderators.add(self.subscriber)
        self.assertEqual(channel.moderators.count(), 2)

    def test_channel_reverse_relationships(self):
        """Test reverse relationships"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel.subscribers.add(self.subscriber)
        channel.moderators.add(self.creator)
        
        self.assertIn(channel, self.creator.channels_owned.all())
        self.assertIn(channel, self.subscriber.channels_subscribed.all())
        self.assertIn(channel, self.creator.channels_moderated.all())


class MessageModelTest(TestCase):
    """Test Message model"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.room = OneToOneChat.objects.create()
        self.room.participants.add(self.user1, self.user2)

    def test_message_creation(self):
        """Test creating a message"""
        message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Hello World'
        )
        self.assertEqual(message.content, 'Hello World')
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.room, self.room)
        self.assertIsInstance(message.id, uuid.UUID)

    def test_message_default_flags(self):
        """Test default message flags"""
        message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Test'
        )
        self.assertFalse(message.is_forwarded)
        self.assertFalse(message.is_edited)
        self.assertFalse(message.is_deleted)

    def test_message_parent_message(self):
        """Test message reply functionality"""
        parent = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Parent message'
        )
        reply = Message.objects.create(
            room=self.room,
            sender=self.user2,
            content='Reply message',
            parent_message=parent
        )
        self.assertEqual(reply.parent_message, parent)
        self.assertIn(reply, parent.replies.all())

    def test_message_forwarded_from(self):
        """Test message forwarding"""
        original = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Original message'
        )
        forwarded = Message.objects.create(
            room=self.room,
            sender=self.user2,
            content='Original message',
            is_forwarded=True,
            forwarded_from=original
        )
        self.assertTrue(forwarded.is_forwarded)
        self.assertEqual(forwarded.forwarded_from, original)
        self.assertIn(forwarded, original.forwarded.all())

    def test_message_timestamps(self):
        """Test message timestamps"""
        message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Test'
        )
        self.assertIsNotNone(message.created_at)
        self.assertIsNotNone(message.updated_at)

    def test_message_indexes_exist(self):
        """Test that indexes are created"""
        # This is a meta test - just ensures the model definition is correct
        indexes = Message._meta.indexes
        self.assertEqual(len(indexes), 2)

    def test_message_constraint_forwarded_cant_be_reply(self):
        """Test constraint that forwarded messages can't be replies"""
        original = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Original'
        )
        parent = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Parent'
        )
        
        # This should violate the constraint
        with self.assertRaises(IntegrityError):
            Message.objects.create(
                room=self.room,
                sender=self.user2,
                content='Test',
                is_forwarded=True,
                forwarded_from=original,
                parent_message=parent
            )


class ReadReceiptModelTest(TestCase):
    """Test ReadReceipt model"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.room = OneToOneChat.objects.create()
        self.room.participants.add(self.user1, self.user2)
        self.message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Test message'
        )

    def test_read_receipt_creation(self):
        """Test creating a read receipt"""
        receipt = ReadReceipt.objects.create(
            message=self.message,
            reader=self.user2
        )
        self.assertEqual(receipt.message, self.message)
        self.assertEqual(receipt.reader, self.user2)
        self.assertIsNotNone(receipt.read_at)

    def test_read_receipt_relationship(self):
        """Test read receipt relationships"""
        receipt = ReadReceipt.objects.create(
            message=self.message,
            reader=self.user2
        )
        self.assertIn(receipt, self.message.read_receipts.all())


class ChatNotificationModelTest(TestCase):
    """Test ChatNotification model"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.room = OneToOneChat.objects.create()
        self.room.participants.add(self.user1, self.user2)
        self.message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Test message'
        )

    def test_notification_creation(self):
        """Test creating a notification"""
        notification = ChatNotification.objects.create(
            recipient=self.user2,
            message=self.message,
            notification_type='NEW_MESSAGE'
        )
        self.assertEqual(notification.recipient, self.user2)
        self.assertEqual(notification.message, self.message)
        self.assertEqual(notification.notification_type, 'NEW_MESSAGE')

    def test_notification_default_type(self):
        """Test default notification type"""
        notification = ChatNotification.objects.create(
            recipient=self.user2,
            message=self.message
        )
        self.assertEqual(notification.notification_type, 'NEW_MESSAGE')

    def test_notification_is_read_default(self):
        """Test default is_read value"""
        notification = ChatNotification.objects.create(
            recipient=self.user2,
            message=self.message
        )
        self.assertFalse(notification.is_read)

    def test_notification_types(self):
        """Test all notification types"""
        types = ['REACTION', 'NEW_MESSAGE', 'REPLY']
        for notif_type in types:
            notification = ChatNotification.objects.create(
                recipient=self.user2,
                message=self.message,
                notification_type=notif_type
            )
            self.assertEqual(notification.notification_type, notif_type)

    def test_notification_relationships(self):
        """Test notification relationships"""
        notification = ChatNotification.objects.create(
            recipient=self.user2,
            message=self.message
        )
        self.assertIn(notification, self.user2.notifications.all())
        self.assertIn(notification, self.message.notifications.all())


class ReactionModelTest(TestCase):
    """Test Reaction model"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='pass123'
        )
        self.room = OneToOneChat.objects.create()
        self.room.participants.add(self.user1, self.user2)
        self.message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Test message'
        )

    def test_reaction_creation(self):
        """Test creating a reaction"""
        reaction = Reaction.objects.create(
            message=self.message,
            user=self.user2,
            reaction_content='👍'
        )
        self.assertEqual(reaction.message, self.message)
        self.assertEqual(reaction.user, self.user2)
        self.assertEqual(reaction.reaction_content, '👍')

    def test_reaction_timestamps(self):
        """Test reaction timestamp"""
        reaction = Reaction.objects.create(
            message=self.message,
            user=self.user2,
            reaction_content='❤️'
        )
        self.assertIsNotNone(reaction.created_at)

    def test_reaction_relationships(self):
        """Test reaction relationships"""
        reaction = Reaction.objects.create(
            message=self.message,
            user=self.user2,
            reaction_content='😂'
        )
        self.assertIn(reaction, self.message.reactions.all())
        self.assertIn(reaction, self.user2.reactions.all())


class MessageMediaAssetModelTest(TestCase):
    """Test MessageMediaAsset model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.room = OneToOneChat.objects.create()
        self.message = Message.objects.create(
            room=self.room,
            sender=self.user,
            content='Message with media'
        )

    def test_media_asset_creation(self):
        """Test creating a media asset"""
        asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/image.jpg',
            media_type='image',
            mime_type='image/jpeg',
            file_size=1024
        )
        self.assertEqual(asset.message, self.message)
        self.assertEqual(asset.media_url, 'https://example.com/image.jpg')
        self.assertEqual(asset.media_type, 'image')

    def test_media_asset_types(self):
        """Test all media types"""
        types = ['image', 'video', 'audio', 'file']
        for media_type in types:
            asset = MessageMediaAsset.objects.create(
                message=self.message,
                media_url=f'https://example.com/{media_type}',
                media_type=media_type,
                mime_type='image/jpeg' if media_type == 'image' else 'video/mp4'
            )
            self.assertEqual(asset.media_type, media_type)

    def test_media_asset_metadata_default(self):
        """Test default metadata"""
        asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/file',
            media_type='file',
            mime_type='application/pdf'
        )
        self.assertEqual(asset.metadata, {})

    def test_media_asset_metadata_custom(self):
        """Test custom metadata"""
        metadata = {
            'duration': 12.5,
            'resolution': '1080x1920'
        }
        asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/video.mp4',
            media_type='video',
            mime_type='video/mp4',
            metadata=metadata
        )
        self.assertEqual(asset.metadata, metadata)

    def test_media_asset_file_size_default(self):
        """Test default file size"""
        asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/file',
            media_type='file',
            mime_type='application/pdf'
        )
        self.assertEqual(asset.file_size, 0)

    def test_media_asset_relationships(self):
        """Test media asset relationships"""
        asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/image.jpg',
            media_type='image',
            mime_type='image/jpeg'
        )
        self.assertIn(asset, self.message.attachments.all())

    def test_media_asset_valid_mime_types(self):
        """Test valid MIME types constraint"""
        # Valid MIME type should work
        asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/image.jpg',
            media_type='image',
            mime_type='image/jpeg'
        )
        self.assertIsNotNone(asset)

    def test_media_asset_invalid_mime_type(self):
        """Test invalid MIME type constraint"""
        # Invalid MIME type should fail
        with self.assertRaises(IntegrityError):
            MessageMediaAsset.objects.create(
                message=self.message,
                media_url='https://example.com/file',
                media_type='file',
                mime_type='invalid/mime'
            )