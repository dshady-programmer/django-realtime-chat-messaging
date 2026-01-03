import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from realtime_chat_messaging.models import (
    OneToOneChat, GroupChat, Channel, Message,
    ReadReceipt, Reaction, MessageMediaAsset
)
from realtime_chat_messaging.serializers import (
    UserSerializer, OneToOneChatSerializer, GroupChatSerializer,
    ChannelSerializer, RoomPolymorphicSerializer, MessageSerializer,
    ReadReceiptSerializer, ReactionSerializer, MessageMediaAssetSerializer,
    OneToOneChatListSerializer, GroupChatListSerializer, ChannelListSerializer,
    RoomListPolymorphicSerializer, ChatNotificationSerializer
)

User = get_user_model()


@pytest.fixture
def users(db):
    """Create test users"""
    return {
        'user1': User.objects.create_user(username='user1', email='user1@test.com', password='pass123'),
        'user2': User.objects.create_user(username='user2', email='user2@test.com', password='pass123'),
        'user3': User.objects.create_user(username='user3', email='user3@test.com', password='pass123'),
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
    return GroupChat.objects.create(
        name="Test Group",
        description="A test group",
        creator=users['user1']
    )


@pytest.fixture
def channel(users):
    """Create a channel"""
    return Channel.objects.create(
        name="Test Channel",
        description="A test channel",
        creator=users['user1']
    )


class TestUserSerializer:
    """Test suite for UserSerializer"""

    def test_user_serialization(self, users):
        """Test that user serialization works correctly"""
        serializer = UserSerializer(users['user1'])
        data = serializer.data
        
        assert data['id'] == users['user1'].id
        assert data['username'] == 'user1'
        assert data['email'] == 'user1@test.com'
        assert 'password' not in data

    def test_multiple_users_serialization(self, users):
        """Test serializing multiple users"""
        user_list = [users['user1'], users['user2'], users['user3']]
        serializer = UserSerializer(user_list, many=True)
        data = serializer.data
        
        assert len(data) == 3
        assert all('username' in user for user in data)


class TestOneToOneChatSerializer:
    """Test suite for OneToOneChat serializers"""

    def test_one_to_one_chat_serialization(self, one_to_one_chat):
        """Test one-to-one chat serialization"""
        serializer = OneToOneChatSerializer(one_to_one_chat)
        data = serializer.data
        
        assert str(data['id']) == str(one_to_one_chat.id)
        assert len(data['participants']) == 2
        assert 'last_message' not in data

    def test_one_to_one_chat_list_serialization(self, one_to_one_chat, users):
        """Test one-to-one chat list serialization with peer"""
        serializer = OneToOneChatListSerializer(
            one_to_one_chat,
            context={'user': users['user1']}
        )
        data = serializer.data
        
        # Should return the peer (other participant)
        assert data['peer']['username'] == 'user2'
        assert 'participants' not in data

    def test_one_to_one_chat_list_requires_user_context(self, one_to_one_chat):
        """Test that list serializer requires user in context"""
        serializer = OneToOneChatListSerializer(one_to_one_chat)
        
        with pytest.raises(Exception, match="user context is required"):
            _ = serializer.data

    def test_one_to_one_chat_with_last_message(self, one_to_one_chat, users):
        """Test serialization with last message"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Last message"
        )
        one_to_one_chat.last_message = message
        one_to_one_chat.save()
        
        serializer = OneToOneChatListSerializer(
            one_to_one_chat,
            context={'user': users['user1']}
        )
        data = serializer.data
        
        assert data['last_message']['content'] == "Last message"


class TestGroupChatSerializer:
    """Test suite for GroupChat serializers"""

    def test_group_chat_serialization(self, group_chat):
        """Test group chat serialization"""
        serializer = GroupChatSerializer(group_chat)
        data = serializer.data
        
        assert data['name'] == "Test Group"
        assert data['description'] == "A test group"
        assert data['creator']['username'] == 'user1'
        assert len(data['participants']) == 1
        assert len(data['admins']) == 1

    def test_group_chat_list_serialization(self, group_chat):
        """Test group chat list serialization"""
        serializer = GroupChatListSerializer(group_chat)
        data = serializer.data
        
        assert data['name'] == "Test Group"
        assert 'participants' not in data
        assert 'admins' not in data
        assert 'creator' in data

    def test_group_chat_with_multiple_participants(self, group_chat, users):
        """Test serialization with multiple participants"""
        group_chat.participants.add(users['user2'], users['user3'])
        
        serializer = GroupChatSerializer(group_chat)
        data = serializer.data
        
        assert len(data['participants']) == 3
        participant_usernames = [p['username'] for p in data['participants']]
        assert 'user1' in participant_usernames
        assert 'user2' in participant_usernames
        assert 'user3' in participant_usernames


class TestChannelSerializer:
    """Test suite for Channel serializers"""

    def test_channel_serialization(self, channel):
        """Test channel serialization"""
        serializer = ChannelSerializer(channel)
        data = serializer.data
        
        assert data['name'] == "Test Channel"
        assert data['description'] == "A test channel"
        assert data['creator']['username'] == 'user1'
        assert data['is_public'] is True
        assert len(data['subscribers']) == 1
        assert len(data['moderators']) == 1

    def test_channel_list_serialization(self, channel):
        """Test channel list serialization"""
        serializer = ChannelListSerializer(channel)
        data = serializer.data
        
        assert data['name'] == "Test Channel"
        assert 'subscribers' not in data
        assert 'moderators' not in data
        assert 'creator' in data


class TestRoomPolymorphicSerializer:
    """Test suite for polymorphic room serializers"""

    def test_polymorphic_serialization_one_to_one(self, one_to_one_chat):
        """Test polymorphic serialization of OneToOneChat"""
        serializer = RoomPolymorphicSerializer(one_to_one_chat)
        data = serializer.data
        
        assert data['type'] == 'OneToOneChat'
        assert len(data['participants']) == 2

    def test_polymorphic_serialization_group(self, group_chat):
        """Test polymorphic serialization of GroupChat"""
        serializer = RoomPolymorphicSerializer(group_chat)
        data = serializer.data
        
        assert data['type'] == 'GroupChat'
        assert data['name'] == "Test Group"

    def test_polymorphic_serialization_channel(self, channel):
        """Test polymorphic serialization of Channel"""
        serializer = RoomPolymorphicSerializer(channel)
        data = serializer.data
        
        assert data['type'] == 'Channel'
        assert data['name'] == "Test Channel"

    def test_create_one_to_one_chat(self, users):
        """Test creating OneToOneChat through polymorphic serializer"""
        data = {
            'type': 'OneToOneChat',
            'participants': [users['user2'].id]
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert isinstance(instance, OneToOneChat)
        assert instance.participants.count() == 2

    def test_create_group_chat(self, users):
        """Test creating GroupChat through polymorphic serializer"""
        data = {
            'type': 'GroupChat',
            'name': 'New Group',
            'description': 'Test description',
            'participants': [users['user2'].id]
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert isinstance(instance, GroupChat)
        assert instance.name == 'New Group'
        assert instance.creator == users['user1']

    def test_create_channel(self, users):
        """Test creating Channel through polymorphic serializer"""
        data = {
            'type': 'Channel',
            'name': 'New Channel',
            'description': 'Test description',
            'subscribers': [users['user2'].id]
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert isinstance(instance, Channel)
        assert instance.name == 'New Channel'
        assert instance.creator == users['user1']

    def test_create_with_preferences(self, users):
        """Test creating room with preferences in extra_fields"""
        data = {
            'type': 'GroupChat',
            'name': 'New Group',
            'extra_fields': {
                'preferences': {'theme': 'dark', 'notifications': True}
            }
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert instance.preferences == {'theme': 'dark', 'notifications': True}

    def test_create_with_invalid_preferences(self, users):
        """Test that invalid preferences type raises error"""
        data = {
            'type': 'GroupChat',
            'name': 'New Group',
            'extra_fields': {
                'preferences': "invalid_string"
            }
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_create_with_invalid_type(self, users):
        """Test that invalid room type raises error"""
        data = {
            'type': 'InvalidType',
            'name': 'Test'
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_create_channel_without_subscribers_raises_error(self, users):
        """Test that creating channel without subscribers raises error"""
        data = {
            'type': 'Channel',
            'name': 'New Channel'
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users['user1']}
        )
        
        with pytest.raises(Exception, match="Channel must have at least one subscriber"):
            serializer.is_valid(raise_exception=True)
            serializer.save()


class TestMessageSerializer:
    """Test suite for Message serializer"""

    def test_message_serialization(self, one_to_one_chat, users):
        """Test message serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test message"
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert data['content'] == "Test message"
        assert data['sender']['username'] == 'user1'
        assert str(data['room']['id']) == str(one_to_one_chat.id)

    def test_message_deserialization(self, one_to_one_chat, users):
        """Test message creation through serializer"""
        data = {
            'room_id': str(one_to_one_chat.id),
            'sender_id': users['user1'].id,
            'content': 'New message'
        }
        
        serializer = MessageSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        assert message.content == 'New message'
        assert message.sender == users['user1']

    def test_message_with_reply(self, one_to_one_chat, users):
        """Test message serialization with reply"""
        parent = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Parent message"
        )
        
        reply = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user2'],
            content="Reply message",
            parent_message=parent
        )
        
        serializer = MessageSerializer(reply)
        data = serializer.data
        
        assert data['parent_message']['content'] == "Parent message"

    def test_message_with_forward(self, one_to_one_chat, group_chat, users):
        """Test message serialization with forward"""
        original = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Original"
        )
        
        forwarded = Message.objects.create(
            room=group_chat,
            sender=users['user1'],
            content="Original",
            is_forwarded=True,
            forwarded_from=original
        )
        
        serializer = MessageSerializer(forwarded)
        data = serializer.data
        
        assert data['is_forwarded'] is True
        assert data['forwarded_from']['content'] == "Original"

    def test_message_content_sanitization(self, one_to_one_chat, users):
        """Test that message content is sanitized (bleach)"""
        data = {
            'room_id': str(one_to_one_chat.id),
            'sender_id': users['user1'].id,
            'content': '<script>alert("xss")</script><b>Bold text</b>'
        }
        
        serializer = MessageSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        # Script tags should be removed, allowed tags kept
        assert '<script>' not in message.content
        assert '<b>Bold text</b>' in message.content

    def test_message_with_reactions(self, one_to_one_chat, users):
        """Test message serialization includes reactions"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        Reaction.objects.create(
            message=message,
            user=users['user2'],
            reaction_content="👍"
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert len(data['reactions']) == 1
        assert data['reactions'][0]['reaction_content'] == "👍"

    def test_message_with_read_receipts(self, one_to_one_chat, users):
        """Test message serialization includes read receipts"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        ReadReceipt.objects.create(
            message=message,
            reader=users['user2']
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert len(data['read_receipts']) == 1
        assert data['read_receipts'][0]['reader']['username'] == 'user2'

    def test_message_with_attachments(self, one_to_one_chat, users):
        """Test message serialization includes attachments"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        MessageMediaAsset.objects.create(
            message=message,
            media_url="https://example.com/image.jpg",
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert len(data['attachments']) == 1
        assert data['attachments'][0]['media_url'] == "https://example.com/image.jpg"

    def test_delivered_to_serialization(self, one_to_one_chat, users):
        """Test delivered_to field serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        message.delivered_to.add(users['user2'])
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert 'user2' in data['delivered_to']


class TestReadReceiptSerializer:
    """Test suite for ReadReceipt serializer"""

    def test_read_receipt_serialization(self, one_to_one_chat, users):
        """Test read receipt serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        receipt = ReadReceipt.objects.create(
            message=message,
            reader=users['user2']
        )
        
        serializer = ReadReceiptSerializer(receipt)
        data = serializer.data
        
        assert data['reader']['username'] == 'user2'
        assert 'read_at' in data

    def test_read_receipt_deserialization(self, one_to_one_chat, users):
        """Test read receipt creation through serializer"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        data = {
            'reader_id': users['user2'].id,
            'message': message.id
        }
        
        serializer = ReadReceiptSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        receipt = serializer.save()
        
        assert receipt.reader == users['user2']
        assert receipt.message == message


class TestReactionSerializer:
    """Test suite for Reaction serializer"""

    def test_reaction_serialization(self, one_to_one_chat, users):
        """Test reaction serialization"""
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
        
        serializer = ReactionSerializer(reaction)
        data = serializer.data
        
        assert data['user']['username'] == 'user2'
        assert data['reaction_content'] == "👍"

    def test_reaction_deserialization(self, one_to_one_chat, users):
        """Test reaction creation through serializer"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        data = {
            'user_id': users['user2'].id,
            'message': message.id,
            'reaction_content': '❤️'
        }
        
        serializer = ReactionSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        reaction = serializer.save()
        
        assert reaction.user == users['user2']
        assert reaction.reaction_content == '❤️'


class TestMessageMediaAssetSerializer:
    """Test suite for MessageMediaAsset serializer"""

    def test_media_asset_serialization(self, one_to_one_chat, users):
        """Test media asset serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        asset = MessageMediaAsset.objects.create(
            message=message,
            media_url="https://example.com/image.jpg",
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024,
            caption="Test image"
        )
        
        serializer = MessageMediaAssetSerializer(asset)
        data = serializer.data
        
        assert data['media_url'] == "https://example.com/image.jpg"
        assert data['media_type'] == "image"
        assert data['caption'] == "Test image"
        assert 'message' not in data

    def test_media_asset_deserialization(self, one_to_one_chat, users):
        """Test media asset creation through serializer"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Test"
        )
        
        data = {
            'message_id': message.id,
            'media_url': 'https://example.com/video.mp4',
            'media_type': 'video',
            'mime_type': 'video/mp4',
            'file_size': 2048000,
            'metadata': {'duration': 15.2, 'resolution': '1080x1920'}
        }
        
        serializer = MessageMediaAssetSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        asset = serializer.save()
        
        assert asset.media_url == 'https://example.com/video.mp4'
        assert asset.metadata['duration'] == 15.2

    def test_bulk_media_asset_creation(self, one_to_one_chat, users):
        """Test creating multiple media assets at once"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users['user1'],
            content="Multiple media"
        )
        
        data = [
            {
                'message_id': message.id,
                'media_url': 'https://example.com/image1.jpg',
                'media_type': 'image',
                'mime_type': 'image/jpeg',
                'file_size': 1024
            },
            {
                'message_id': message.id,
                'media_url': 'https://example.com/image2.png',
                'media_type': 'image',
                'mime_type': 'image/png',
                'file_size': 2048
            }
        ]
        
        serializer = MessageMediaAssetSerializer(data=data, many=True)
        assert serializer.is_valid(raise_exception=True)
        assets = serializer.save()
        
        assert len(assets) == 2


class TestRoomListPolymorphicSerializer:
    """Test suite for polymorphic room list serializers"""

    def test_list_serialization_mixed_rooms(self, one_to_one_chat, group_chat, channel, users):
        """Test serializing a list of different room types"""
        rooms = [one_to_one_chat, group_chat, channel]
        
        serializer = RoomListPolymorphicSerializer(
            rooms,
            many=True,
            context={'user': users['user1']}
        )
        data = serializer.data
        
        assert len(data) == 3
        types = [room['type'] for room in data]
        assert 'OneToOneChat' in types
        assert 'GroupChat' in types
        assert 'Channel' in types