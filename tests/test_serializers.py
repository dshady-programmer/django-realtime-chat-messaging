import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError
from django.db import IntegrityError
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




class TestUserSerializer:
    """Test suite for UserSerializer"""

    def test_user_serialization(self, users):
        """Test that user serialization works correctly"""
        serializer = UserSerializer(users[0])
        data = serializer.data
        
        assert data['id'] == users[0].id
        assert data['username'] == "user0"
        assert data['email'] == 'user0@example.com'
        assert 'password' not in data
        assert 'first_name' in data and 'last_name' in data

    def test_multiple_users_serialization(self, users):
        """Test serializing multiple users"""
        serializer = UserSerializer(users, many=True)
        data = serializer.data
        
        assert len(data) == 10
        assert all('username' in user and 'email' in user and 'id' in user and 'first_name' in user and 'last_name' in user for user in data)


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
            context={'user': users[0]}
        )
        data = serializer.data
        
        # Should return the peer (other participant)
        assert data['peer']['username'] == 'user1'


        # test for the other user
        serializer = OneToOneChatListSerializer(
            one_to_one_chat,
            context={'user': users[1]}
        )
        data = serializer.data
        
        # Should return the peer (other participant)
        assert data['peer']['username'] == 'user0'

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
            sender=users[0],
            content="Last message"
        )
        one_to_one_chat.last_message = message
        one_to_one_chat.save()
        
        serializer = OneToOneChatListSerializer(
            one_to_one_chat,
            context={'user': users[0]}
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
        assert data['creator']['username'] == 'user0'
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
        group_chat.participants.add(*users[1:6])
        
        serializer = GroupChatSerializer(group_chat)
        data = serializer.data
        
        assert len(data['participants']) == 6
        participant_usernames = [p['username'] for p in data['participants']]
        for u in users[:6]:
            u.username in participant_usernames



class TestChannelSerializer:
    """Test suite for Channel serializers"""

    def test_channel_serialization(self, channel):
        """Test channel serialization"""
        serializer = ChannelSerializer(channel)
        data = serializer.data
        
        assert data['name'] == "Test Channel"
        assert data['description'] == "A test channel"
        assert data['creator']['username'] == 'user0'
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

    def test_channel_with_last_meessage(self, users, channel):
        """
        Test channel has last message after message association with channel
        """
        message = Message.objects.create(
            room=channel,
            sender=users[0],
            content="Last message"
        )
        channel.last_message = message
        channel.save()
        
        serializer = ChannelListSerializer(
            channel
        )
        data = serializer.data
        
        assert data['last_message']['content'] == "Last message"

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
            'participants': [users[3].id]
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[1]}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert isinstance(instance, OneToOneChat)
        assert instance.participants.count() == 2

    def test_create_group_chat(self, users):
        """Test creating GroupChat through polymorphic serializer"""
        participants = [users[0].id, users[2].id, users[3].id]
        data = {
            'type': 'GroupChat',
            'name': 'New Group',
            'description': 'Test description',
            'participants': participants
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[1]}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert isinstance(instance, GroupChat)
        assert instance.name == 'New Group'
        assert instance.creator == users[1]
        participants.append(users[1].id)
        for p in instance.participants.all():
            assert p.id in participants

    def test_create_channel(self, users):
        """Test creating Channel through polymorphic serializer"""
        subscribers = [users[0].id, users[2].id, users[3].id]
        data = {
            'type': 'Channel',
            'name': 'New Channel',
            'description': 'Test description',
            'subscribers': subscribers
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[1]}
        )
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        
        assert isinstance(instance, Channel)
        assert instance.name == 'New Channel'
        assert instance.creator == users[1]

        subscribers.append(users[1].id)
        for s in instance.subscribers.all():
            assert s.id in subscribers

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
            context={'user': users[0]}
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
            context={'user': users[0]}
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
            context={'user': users[0]}
        )
        
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
            serializer.save()

    def test_create_onetonechat_without_atleast_one_participants_raises_error(self, users):
        """
        Test that creating a onetoonechat without atleast one participants raises an error
        """

        data1 = {
            'type': 'OneToOneChat',
        }
        data2 = {
            'type': 'OneToOneChat', 
            'participants': []
        }

        serializer1 = RoomPolymorphicSerializer(
            data=data1,
            context={'user': users[0]}
        )

        serializer2 = RoomPolymorphicSerializer(
            data=data2,
            context={'user': users[0]}
        )

        assert serializer1.is_valid(raise_exception=True) # data remains valid at this point
        assert serializer2.is_valid(raise_exception=True) # data remains valid at this point


        with pytest.raises(ValidationError,  match="A one to one chat can only have 2 participants"):
            serializer1.save()

        with pytest.raises(ValidationError,  match="A one to one chat can only have 2 participants"):  
            serializer2.save()


    def test_create_groupchat_without_participants_does_not_raise_error(self, users):
        """Test that creating groupchat without participantss does not raise error instead creates a groupchat with one participants which is the creator"""
        data = {
            'type': 'GroupChat',
            'name': 'New GroupChat'
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[0]}
        )
        
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        assert instance.participants.count() == 1
        assert instance.participants.all()[0] == users[0]
        assert instance.admins.all()[0] == users[0]

    def test_create_groupchat_with_empty_participants_does_not_raise_error(self, users):
        """Test that creating groupchat with empty participants does not raise error instead creates a groupchat with one participant which is the creator"""
        data = {
            'type': 'GroupChat',
            'name': 'New GroupChat',
            'participants': []
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[0]}
        )
        
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        assert instance.participants.count() == 1
        assert instance.participants.all()[0] == users[0]
        assert instance.admins.all()[0] == users[0]


    def test_create_channel_without_subscribers_does_not_raise_error(self, users):
        """Test that creating channel without subscribers does not raise error instead creates a channel with one subscriber which is the creator"""
        data = {
            'type': 'Channel',
            'name': 'New Channel'
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[0]}
        )
        
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        assert instance.subscribers.count() == 1
        assert instance.subscribers.all()[0] == users[0]
        assert instance.moderators.all()[0] == users[0]

    def test_create_channel_with_empty_subscribers_does_not_raise_error(self, users):
        """Test that creating channel with empty subscribers does not raise error instead creates a channel with one subscriber which is the creator"""
        data = {
            'type': 'Channel',
            'name': 'New Channel',
            'subscribers': []
        }
        
        serializer = RoomPolymorphicSerializer(
            data=data,
            context={'user': users[0]}
        )
        
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        assert instance.subscribers.count() == 1
        assert instance.subscribers.all()[0] == users[0]
        assert instance.moderators.all()[0] == users[0]


class TestMessageSerializer:
    """Test suite for Message serializer"""

    def test_message_serialization(self, one_to_one_chat, users):
        """Test message serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[1],
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
            'sender_id': users[0].id,
            'content': 'New message'
        }
        
        serializer = MessageSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        assert message.content == 'New message'
        assert message.sender == users[0]

    def test_message_with_reply(self, one_to_one_chat, users):
        """Test message serialization with reply"""
        parent = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Parent message"
        )
        
        reply = Message.objects.create(
            room=one_to_one_chat,
            sender=users[1],
            content="Reply message",
            parent_message=parent
        )
        
        serializer = MessageSerializer(reply)
        data = serializer.data
        
        assert data['parent_message']['content'] == "Parent message"

    def test_message_deserialization_with_reply(self, one_to_one_chat, users):
        """Test message reply creation with serializersy"""
        parent = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Parent message"
        )
        
        data = {
            'parent_message_id': str(parent.id),
            'sender_id': str(users[1].id),
            'room_id': str(one_to_one_chat.id),
            'content': "Reply message"
        }
        
        serializer = MessageSerializer(data=data)
        
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        assert instance in parent.realtime_chat_messaging_message_replies.all()
        assert instance.parent_message == parent


    def test_message_with_forward(self, one_to_one_chat, group_chat, users):
        """Test message serialization with forward"""
        original = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Original"
        )
        
        forwarded = Message.objects.create(
            room=group_chat,
            sender=users[0],
            content="Original",
            is_forwarded=True,
            forwarded_from=original
        )
        
        serializer = MessageSerializer(forwarded)
        data = serializer.data
        
        assert data['is_forwarded'] is True
        assert data['forwarded_from']['content'] == "Original"

    def test_message_deserialization_with_forward(self,one_to_one_chat, group_chat, users):
        """
        test forwarded message creation with serializers
        """
        original = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Original"
        )
        data = {
            'forwarded_from_id': str(original.id),
            'is_forwarded': True,
            'sender_id': str(users[0].id),
            'room_id': str(group_chat.id),
            'content': "Forward"
        }
        serializer = MessageSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        assert instance.is_forwarded
        assert instance.forwarded_from == original

    def test_message_content_sanitization(self, one_to_one_chat, users, html_payload):
        """Test that message content is sanitized (bleach)"""
        content, expected = html_payload
        data = {
            'room_id': str(one_to_one_chat.id),
            'sender_id': users[0].id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        message = serializer.save()
        
        # Script tags should be removed, allowed tags kept
        assert message.content == expected

    def test_message_with_reactions(self, one_to_one_chat, users):
        """Test message serialization includes reactions"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        Reaction.objects.create(
            message=message,
            user=users[1],
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
            sender=users[0],
            content="Test"
        )
        
        ReadReceipt.objects.create(
            message=message,
            reader=users[1]
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert len(data['read_receipts']) == 1
        assert data['read_receipts'][0]['reader']['username'] == 'user1'

    def test_message_with_attachments(self, one_to_one_chat, users):
        """Test message serialization includes attachments"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
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
            sender=users[0],
            content="Test"
        )
        message.delivered_to.add(users[1])
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        assert 'user1' in data['delivered_to']


class TestReadReceiptSerializer:
    """Test suite for ReadReceipt serializer"""

    def test_read_receipt_serialization(self, one_to_one_chat, users):
        """Test read receipt serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        receipt = ReadReceipt.objects.create(
            message=message,
            reader=users[1]
        )
        
        serializer = ReadReceiptSerializer(receipt)
        data = serializer.data
        
        print(data)
        assert data['reader']['username'] == 'user1'
        assert 'read_at' in data

    def test_read_receipt_deserialization(self, one_to_one_chat, users):
        """Test read receipt creation through serializer"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        data = {
            'reader_id': users[1].id,
            'message_id': message.id
        }
        
        serializer = ReadReceiptSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        receipt = serializer.save()
        
        assert receipt.reader == users[1]
        assert receipt.message == message


class TestReactionSerializer:
    """Test suite for Reaction serializer"""

    def test_reaction_serialization(self, one_to_one_chat, users):
        """Test reaction serialization"""
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
        
        serializer = ReactionSerializer(reaction)
        data = serializer.data
        
        assert data['user']['username'] == 'user1'
        assert data['reaction_content'] == "👍"

    def test_reaction_deserialization(self, one_to_one_chat, users):
        """Test reaction creation through serializer"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        data = {
            'user_id': users[1].id,
            'message': message.id,
            'reaction_content': '❤️'
        }
        
        serializer = ReactionSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        reaction = serializer.save()
        
        assert reaction.user == users[1]
        assert reaction.reaction_content == '❤️'

    def test_reaction_deserialization_with_duplicate_reaction(self, one_to_one_chat, users):
        """
            Test reaction creation through serializer with duplicate reaction
        
        """
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        data = {
            'user_id': users[1].id,
            'message': message.id,
            'reaction_content': '❤️'
        }
        
        serializer = ReactionSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        reaction = serializer.save()
        
        assert reaction.user == users[1]
        assert reaction.reaction_content == '❤️'


        serializer2 = ReactionSerializer(data=data)
        assert serializer2.is_valid(raise_exception=True)
        with pytest.raises(IntegrityError):
            serializer2.save()


    def test_reaction_overriding_deserialization(self, one_to_one_chat, users):
        """Test reaction creation through serializer"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
            content="Test"
        )
        
        data = {
            'user_id': users[1].id,
            'message': message.id,
            'reaction_content': '❤️'
        }
        
        serializer = ReactionSerializer(data=data)
        assert serializer.is_valid(raise_exception=True)
        reaction = serializer.save()
        
        assert reaction.user == users[1]
        assert reaction.reaction_content == '❤️'

        data2 = {
            'user_id': users[1].id,
            'message': message.id,
            'reaction_content': '👍'
        }

        serializer2 = ReactionSerializer(data=data2)
        assert serializer2.is_valid(raise_exception=True)
        reaction = serializer2.save()
        
        assert reaction.user == users[1]
        assert reaction.reaction_content == '👍'


class TestMessageMediaAssetSerializer:
    """Test suite for MessageMediaAsset serializer"""

    def test_media_asset_serialization(self, one_to_one_chat, users):
        """Test media asset serialization"""
        message = Message.objects.create(
            room=one_to_one_chat,
            sender=users[0],
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
            sender=users[0],
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
            sender=users[0],
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
            context={'user': users[0]}
        )
        data = serializer.data
        
        assert len(data) == 3
        types = [room['type'] for room in data]
        assert 'OneToOneChat' in types
        assert 'GroupChat' in types
        assert 'Channel' in types