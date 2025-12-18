"""
Tests for chat application serializers
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from realtime_chat_messaging.models import (
    OneToOneChat, GroupChat, Channel, Message,
    ReadReceipt, Reaction, MessageMediaAsset, ChatNotification
)
from realtime_chat_messaging.serializers import (
    UserSerializer, OneToOneChatSerializer, GroupChatSerializer,
    ChannelSerializer, MessageSerializer, ReadReceiptSerializer,
    ReactionSerializer, MessageMediaAssetSerializer,
    ChatNotificationSerializer, RoomPolymorphicSerializer
)

User = get_user_model()


class UserSerializerTest(TestCase):
    """Test UserSerializer"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_user_serialization(self):
        """Test serializing a user"""
        serializer = UserSerializer(self.user)
        data = serializer.data
        
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['email'], 'test@example.com')
        self.assertNotIn('password', data)

    def test_user_serializer_excludes_password(self):
        """Test that password is excluded from serialization"""
        serializer = UserSerializer(self.user)
        self.assertNotIn('password', serializer.data)


class OneToOneChatSerializerTest(TestCase):
    """Test OneToOneChatSerializer"""

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
        self.chat = OneToOneChat.objects.create()
        self.chat.participants.add(self.user1, self.user2)

    def test_one_to_one_chat_serialization(self):
        """Test serializing a one-to-one chat"""
        serializer = OneToOneChatSerializer(self.chat)
        data = serializer.data
        
        self.assertIn('participants', data)
        self.assertEqual(len(data['participants']), 2)

    def test_one_to_one_chat_participants_read_only_after_write(self):
        """Test that participants field is read-only while creating a new chat"""
        serializer = OneToOneChatSerializer(data={})
        # participants should be in data but read-only
        self.assertTrue(serializer.is_valid())
        serializer.save()
        self.assertIn('participants', serializer.data)

    def test_one_to_one_chat_nested_user_data(self):
        """Test that participants are nested with user data"""
        serializer = OneToOneChatSerializer(self.chat)
        data = serializer.data
        
        participant_usernames = [p['username'] for p in data['participants']]
        self.assertIn('user1', participant_usernames)
        self.assertIn('user2', participant_usernames)


class GroupChatSerializerTest(TestCase):
    """Test GroupChatSerializer"""

    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='pass123'
        )
        self.group = GroupChat.objects.create(
            name='Test Group',
            description='A test group',
            creator=self.creator,
            max_participants=10
        )
        self.group.participants.add(self.member)
        self.group.admins.add(self.creator)

    def test_group_chat_serialization(self):
        """Test serializing a group chat"""
        serializer = GroupChatSerializer(self.group)
        data = serializer.data
        
        self.assertIn('creator', data)
        self.assertIn('participants', data)
        self.assertIn('admins', data)
        self.assertIn('name', data)

    def test_group_chat_creator_nested(self):
        """Test that creator is nested with user data"""
        serializer = GroupChatSerializer(self.group)
        data = serializer.data
        
        self.assertEqual(data['creator']['username'], 'creator')

    def test_group_chat_participants_read_only(self):
        """Test that participants, admins, creator are read-only"""
        serializer = GroupChatSerializer(self.group)
        # These fields should be in the serialized data
        self.assertIn('creator', serializer.data)
        self.assertIn('participants', serializer.data)
        self.assertIn('admins', serializer.data)

    def test_group_chat_write(self):
        """ Test group chat creation"""

        serializer = GroupChatSerializer(data={"name": "New Group Chat", "description": "Group chat description"})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save(creator=self.creator)
        self.assertEqual(instance.creator, self.creator)
        self.assertIn(instance.creator, instance.participants.all())
        self.assertIn(instance.creator, instance.admins.all())



class ChannelSerializerTest(TestCase):
    """Test ChannelSerializer"""

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
        self.channel = Channel.objects.create(
            name='Test Channel',
            description='A test channel',
            creator=self.creator,
            is_public=True
        )
        self.channel.subscribers.add(self.subscriber)
        self.channel.moderators.add(self.creator)

    def test_channel_serialization(self):
        """Test serializing a channel"""
        serializer = ChannelSerializer(self.channel)
        data = serializer.data
        
        self.assertIn('creator', data)
        self.assertIn('subscribers', data)
        self.assertIn('moderators', data)
        self.assertIn('name', data)
        self.assertIn('is_public', data)

    def test_channel_creator_nested(self):
        """Test that creator is nested with user data"""
        serializer = ChannelSerializer(self.channel)
        data = serializer.data
        
        self.assertEqual(data['creator']['username'], 'creator')

    def test_channel_subscribers_nested(self):
        """Test that subscribers are nested with user data"""
        serializer = ChannelSerializer(self.channel)
        data = serializer.data
        
        subscriber_usernames = [s['username'] for s in data['subscribers']]
        self.assertIn('subscriber', subscriber_usernames)

    def test_channel_write(self):
        """ Test channel creation"""

        serializer = ChannelSerializer(data={"name": "New Channel", "description": "Channel description"})
        self.assertTrue(serializer.is_valid())
        instance = serializer.save(creator=self.creator)
        self.assertEqual(instance.creator, self.creator)
        self.assertIn(instance.creator, instance.subscribers.all())
        self.assertIn(instance.creator, instance.moderators.all())

class MessageSerializerTest(TestCase):
    """Test MessageSerializer"""

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

    def test_message_serialization(self):
        """Test serializing a message"""
        serializer = MessageSerializer(self.message)
        data = serializer.data
        
        self.assertEqual(data['content'], 'Test message')
        self.assertIn('sender', data)
        self.assertIn('room', data)
        self.assertIn('created_at', data)

    def test_message_sender_nested(self):
        """Test that sender is nested with user data"""
        serializer = MessageSerializer(self.message)
        data = serializer.data
        
        self.assertEqual(data['sender']['username'], 'user1')

    def test_message_room_nested(self):
        """Test that room is nested with polymorphic data"""
        serializer = MessageSerializer(self.message)

        data = serializer.data
        
        self.assertIn('participants', data['room'])

    def test_message_with_parent(self):
        """Test serializing a message with parent_message"""
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
        
        serializer = MessageSerializer(reply)
        data = serializer.data
        
        self.assertIsNotNone(data['parent_message'])
        self.assertEqual(data['parent_message']['content'], 'Parent message')

    def test_message_with_forwarded_from(self):
        """Test serializing a forwarded message"""
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
        
        serializer = MessageSerializer(forwarded)
        data = serializer.data
        
        self.assertTrue(data['is_forwarded'])
        self.assertIsNotNone(data['forwarded_from'])

    def test_message_serializer_write_with_ids(self):
        """Test creating a message using _id fields"""
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': 'New message'
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertEqual(message.content, 'New message')
        self.assertEqual(message.sender, self.user1)
        self.assertEqual(message.room, self.room)

    def test_message_with_attachments(self):
        """Test serializing a message with attachments"""
        MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/image.jpg',
            media_type='image',
            mime_type='image/jpeg'
        )
        
        serializer = MessageSerializer(self.message)
        data = serializer.data
        
        self.assertIn('attachments', data)
        self.assertEqual(len(data['attachments']), 1)
        self.assertEqual(data['attachments'][0]['media_url'], 'https://example.com/image.jpg')

    def test_message_content_strips_dangerous_html(self):
        """Test that dangerous HTML tags are stripped from content"""
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': '<script>alert("XSS")</script>Hello <b>World</b>'
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # Script tag should be stripped, but <b> should remain
        # print("message content", message.content)
        self.assertNotIn('<script>', message.content)
        self.assertIn('<b>World</b>', message.content)
        self.assertIn('Hello', message.content)

    def test_message_content_allows_safe_html_tags(self):
        """Test that allowed HTML tags are preserved"""
        safe_content = 'Hello <b>bold</b> and <i>italic</i> and <strong>strong</strong> text'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': safe_content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # All allowed tags should be preserved
        self.assertIn('<b>bold</b>', message.content)
        self.assertIn('<i>italic</i>', message.content)
        self.assertIn('<strong>strong</strong>', message.content)

    def test_message_content_sanitizes_anchor_attributes(self):
        """Test that anchor tags with allowed attributes are preserved"""
        content = 'Check <a href="https://example.com" title="Example" target="_blank">this link</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # Anchor tag with allowed attributes should be preserved
        self.assertIn('<a href="https://example.com"', message.content)
        self.assertIn('this link</a>', message.content)

    def test_message_content_strips_disallowed_attributes(self):
        """Test that disallowed attributes are stripped from tags"""
        content = '<a href="https://example.com" onclick="malicious()">Link</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # onclick should be stripped
        self.assertNotIn('onclick', message.content)
        # href should remain (it's allowed)
        self.assertIn('href="https://example.com"', message.content)

    def test_message_content_strips_completely_disallowed_tags(self):
        """Test that completely disallowed tags are removed"""
        content = 'Normal text <div>in div</div> <span>in span</span> <b>bold</b>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # div and span should be stripped (tags removed but content remains)
        self.assertNotIn('<div>', message.content)
        self.assertNotIn('<span>', message.content)
        self.assertIn('in div', message.content)  # Content preserved
        self.assertIn('in span', message.content)  # Content preserved
        # b is allowed
        self.assertIn('<b>bold</b>', message.content)

    def test_message_content_allows_em_tag(self):
        """Test that <em> tag is allowed"""
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': 'This is <em>emphasized</em> text'
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertIn('<em>emphasized</em>', message.content)

    def test_message_content_allows_multiple_anchor_attributes(self):
        """Test anchor tag with all allowed attributes"""
        content = '<a href="https://example.com" title="Click me" target="_blank">Full link</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # All three allowed attributes should be present
        self.assertIn('href="https://example.com"', message.content)
        self.assertIn('title="Click me"', message.content)
        self.assertIn('target="_blank"', message.content)

    def test_message_content_anchor_with_only_href(self):
        """Test anchor tag with only href attribute"""
        content = '<a href="https://example.com">Simple link</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertIn('href="https://example.com"', message.content)
        self.assertIn('Simple link</a>', message.content)

    def test_message_content_nested_allowed_tags(self):
        """Test nested allowed HTML tags"""
        content = '<b>Bold with <i>italic inside</i> and <strong>strong too</strong></b>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # All nested tags should be preserved
        self.assertIn('<b>', message.content)
        self.assertIn('<i>italic inside</i>', message.content)
        self.assertIn('<strong>strong too</strong>', message.content)

    def test_message_content_multiple_links(self):
        """Test content with multiple anchor tags"""
        content = 'Visit <a href="https://site1.com">Site 1</a> and <a href="https://site2.com" title="Second">Site 2</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertIn('href="https://site1.com"', message.content)
        self.assertIn('href="https://site2.com"', message.content)
        self.assertIn('title="Second"', message.content)

    def test_message_content_strips_style_attribute(self):
        """Test that style attribute is stripped from all tags"""
        content = '<b style="color: red;">Red bold</b> <i style="font-size: 20px;">Big italic</i>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # style attribute should be stripped from all tags
        self.assertNotIn('style=', message.content)
        # But tags themselves should remain
        self.assertIn('<b>', message.content)
        self.assertIn('<i>', message.content)
        self.assertIn('Red bold', message.content)
        self.assertIn('Big italic', message.content)

    def test_message_content_strips_class_and_id(self):
        """Test that class and id attributes are stripped"""
        content = '<b class="highlight" id="msg1">Bold text</b>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertNotIn('class=', message.content)
        self.assertNotIn('id=', message.content)
        self.assertIn('<b>', message.content)
        self.assertIn('Bold text', message.content)

    def test_message_content_strips_javascript_in_href(self):
        """Test that javascript: in href is stripped"""
        content = '<a href="javascript:alert(\'XSS\')">Malicious link</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # javascript: protocol should be removed/sanitized
        # print("message content", message.content)
        self.assertNotIn('javascript:', message.content.lower())

    def test_message_content_all_allowed_tags_together(self):
        """Test all allowed tags in one message"""
        content = '<b>Bold</b> <i>Italic</i> <strong>Strong</strong> <em>Emphasis</em> <a href="https://test.com">Link</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # All allowed tags should be present
        self.assertIn('<b>Bold</b>', message.content)
        self.assertIn('<i>Italic</i>', message.content)
        self.assertIn('<strong>Strong</strong>', message.content)
        self.assertIn('<em>Emphasis</em>', message.content)
        self.assertIn('<a href="https://test.com">Link</a>', message.content)

    def test_message_content_plain_text_unchanged(self):
        """Test that plain text without HTML remains unchanged"""
        content = 'This is just plain text with no HTML tags at all.'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertEqual(message.content, content)

    def test_message_content_strips_img_tag(self):
        """Test that img tag is stripped"""
        content = 'Text with <img src="malicious.jpg" onerror="alert(1)"> image'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        # print("message content", message.content)
        self.assertNotIn('<img', message.content)
        self.assertNotIn('onerror', message.content)
        self.assertIn('Text with', message.content)
        self.assertIn('image', message.content)

    def test_message_content_strips_iframe(self):
        """Test that iframe tag is stripped"""
        content = 'Content <iframe src="evil.com"></iframe> here'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        self.assertNotIn('<iframe', message.content)
        self.assertNotIn('evil.com', message.content)
        self.assertIn('Content', message.content)
        self.assertIn('here', message.content)

    def test_message_content_strips_event_handlers(self):
        """Test that all event handlers are stripped"""
        content = '''
            <b onclick="bad()">Click</b>
            <i onmouseover="worse()">Hover</i>
            <a href="#" onload="evil()">Load</a>
        '''
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # All event handlers should be stripped
        self.assertNotIn('onclick', message.content)
        self.assertNotIn('onmouseover', message.content)
        self.assertNotIn('onload', message.content)
        # But tags and content should remain
        self.assertIn('Click', message.content)
        self.assertIn('Hover', message.content)
        self.assertIn('Load', message.content)

    def test_message_content_empty_anchor_tag(self):
        """Test anchor tag with no href"""
        content = '<a>Link without href</a>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # Anchor tag should still be preserved even without href
        self.assertIn('<a>', message.content)
        self.assertIn('Link without href', message.content)

    def test_message_content_case_insensitive_tags(self):
        """Test that tags work regardless of case"""
        content = '<B>Bold</B> <I>Italic</I> <STRONG>Strong</STRONG>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # Content should be preserved (bleach normalizes to lowercase)
        self.assertIn('Bold', message.content)
        self.assertIn('Italic', message.content)
        self.assertIn('Strong', message.content)

    def test_message_content_whitespace_preserved(self):
        """Test that whitespace in content is preserved"""
        content = '<b>Bold</b>    <i>Italic</i>\n<strong>Strong</strong>'
        data = {
            'room_id': self.room.id,
            'sender_id': self.user1.id,
            'content': content
        }
        
        serializer = MessageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        message = serializer.save()
        
        # Whitespace should be preserved
        self.assertIn('    ', message.content)
        self.assertIn('\n', message.content)








class ReadReceiptSerializerTest(TestCase):
    """Test ReadReceiptSerializer"""

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
        self.receipt = ReadReceipt.objects.create(
            message=self.message,
            reader=self.user2
        )

    def test_read_receipt_serialization(self):
        """Test serializing a read receipt"""
        serializer = ReadReceiptSerializer(self.receipt)
        data = serializer.data
        
        self.assertIn('reader', data)
        self.assertIn('message', data)
        self.assertIn('read_at', data)

    def test_read_receipt_reader_nested(self):
        """Test that reader is nested with user data"""
        serializer = ReadReceiptSerializer(self.receipt)
        data = serializer.data
        
        self.assertEqual(data['reader']['username'], 'user2')

    def test_read_receipt_serializer_write_with_id(self):
        """Test creating a read receipt using reader_id"""
        data = {
            'message': self.message.id,
            'reader_id': self.user1.id
        }
        
        serializer = ReadReceiptSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        receipt = serializer.save()
        
        self.assertEqual(receipt.reader, self.user1)
        self.assertEqual(receipt.message, self.message)
    


class ReactionSerializerTest(TestCase):
    """Test ReactionSerializer"""

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
        self.reaction = Reaction.objects.create(
            message=self.message,
            user=self.user2,
            reaction_content='👍'
        )

    def test_reaction_serialization(self):
        """Test serializing a reaction"""
        serializer = ReactionSerializer(self.reaction)
        data = serializer.data
        
        self.assertIn('user', data)
        self.assertIn('message', data)
        self.assertIn('reaction_content', data)
        self.assertEqual(data['reaction_content'], '👍')

    def test_reaction_user_nested(self):
        """Test that user is nested with user data"""
        serializer = ReactionSerializer(self.reaction)
        data = serializer.data
        
        self.assertEqual(data['user']['username'], 'user2')

    def test_reaction_serializer_write_with_id(self):
        """Test creating a reaction using user_id"""
        data = {
            'message': self.message.id,
            'user_id': self.user1.id,
            'reaction_content': '❤️'
        }
        
        serializer = ReactionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        reaction = serializer.save()
        
        self.assertEqual(reaction.user, self.user1)
        self.assertEqual(reaction.reaction_content, '❤️')


class MessageMediaAssetSerializerTest(TestCase):
    """Test MessageMediaAssetSerializer"""

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
        self.asset = MessageMediaAsset.objects.create(
            message=self.message,
            media_url='https://example.com/image.jpg',
            media_type='image',
            mime_type='image/jpeg',
            file_size=1024,
            metadata={'width': 1920, 'height': 1080}
        )

    def test_media_asset_serialization(self):
        """Test serializing a media asset"""
        serializer = MessageMediaAssetSerializer(self.asset)
        data = serializer.data
        
        self.assertEqual(data['media_url'], 'https://example.com/image.jpg')
        self.assertEqual(data['media_type'], 'image')
        self.assertEqual(data['mime_type'], 'image/jpeg')
        self.assertEqual(data['file_size'], 1024)

    def test_media_asset_metadata_serialization(self):
        """Test that metadata is properly serialized"""
        serializer = MessageMediaAssetSerializer(self.asset)
        data = serializer.data
        
        self.assertEqual(data['metadata']['width'], 1920)
        self.assertEqual(data['metadata']['height'], 1080)

    def test_media_asset_serializer_write(self):
        """Test creating a media asset"""
        data = {
            'message': self.message.id,
            'media_url': 'https://example.com/video.mp4',
            'media_type': 'video',
            'mime_type': 'video/mp4',
            'file_size': 2048,
            'metadata': {'duration': 30}
        }
        
        serializer = MessageMediaAssetSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        asset = serializer.save()
        
        self.assertEqual(asset.media_url, 'https://example.com/video.mp4')
        self.assertEqual(asset.metadata['duration'], 30)


class ChatNotificationSerializerTest(TestCase):
    """Test ChatNotificationSerializer"""

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
        self.notification = ChatNotification.objects.create(
            recipients=self.user2,
            message=self.message,
            notification_type='NEW_MESSAGE'
        )

    def test_notification_serialization(self):
        """Test serializing a notification"""
        serializer = ChatNotificationSerializer(self.notification)
        data = serializer.data
        
        self.assertIn('recipient', data)
        self.assertIn('message', data)
        self.assertIn('notification_type', data)
        self.assertEqual(data['notification_type'], 'NEW_MESSAGE')

    def test_notification_message_nested(self):
        """Test that message is nested with full message data"""
        serializer = ChatNotificationSerializer(self.notification)
        data = serializer.data
        
        self.assertEqual(data['message']['content'], 'Test message')

    def test_notification_serializer_write_with_id(self):
        """Test creating a notification using message_id"""
        data = {
            'recipient': self.user1.id,
            'message_id': self.message.id,
            'notification_type': 'REPLY'
        }
        
        serializer = ChatNotificationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        notification = serializer.save()
        
        self.assertEqual(notification.message, self.message)
        self.assertEqual(notification.notification_type, 'REPLY')


class RoomPolymorphicSerializerTest(TestCase):
    """Test RoomPolymorphicSerializer"""

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

    def test_polymorphic_one_to_one_chat(self):
        """Test polymorphic serialization of OneToOneChat"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        serializer = RoomPolymorphicSerializer(chat)
        data = serializer.data
        
        self.assertIn('participants', data)

    def test_polymorphic_group_chat(self):
        """Test polymorphic serialization of GroupChat"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        
        serializer = RoomPolymorphicSerializer(group)
        data = serializer.data
        
        self.assertIn('name', data)
        self.assertIn('creator', data)

    def test_polymorphic_channel(self):
        """Test polymorphic serialization of Channel"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.user1
        )
        
        serializer = RoomPolymorphicSerializer(channel)
        data = serializer.data
        
        self.assertIn('name', data)
        self.assertIn('creator', data)
        self.assertIn('is_public', data)

    def test_polymorphic_list_mixed_types(self):
        """Test polymorphic serialization of mixed room types"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        
        Channel.objects.create(
            name='Test Channel',
            creator=self.user1
        )
        
        from realtime_chat_messaging.models import Room
        rooms = Room.objects.all()
        
        serializer = RoomPolymorphicSerializer(rooms, many=True)
        data = serializer.data
        
        # Should serialize all three different types
        self.assertEqual(len(data), 3)


class SerializerIntegrationTest(TestCase):
    """Integration tests for serializers"""

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

    def test_full_message_with_all_relations(self):
        """Test serializing a message with all possible relations"""
        message = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Test message'
        )
        
        # Add attachment
        MessageMediaAsset.objects.create(
            message=message,
            media_url='https://example.com/image.jpg',
            media_type='image',
            mime_type='image/jpeg'
        )
        
        # Add reaction
        Reaction.objects.create(
            message=message,
            user=self.user2,
            reaction_content='👍'
        )
        
        # Add read receipt
        ReadReceipt.objects.create(
            message=message,
            reader=self.user2
        )
        
        serializer = MessageSerializer(message)
        data = serializer.data
        
        self.assertEqual(len(data['attachments']), 1)
        self.assertEqual(len(data['reactions']), 1)
        self.assertEqual(len(data['read_receipts']), 1)

    def test_nested_reply_chain(self):
        """Test serializing nested reply chains"""
        parent = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Parent'
        )
        child = Message.objects.create(
            room=self.room,
            sender=self.user2,
            content='Child',
            parent_message=parent
        )
        grandchild = Message.objects.create(
            room=self.room,
            sender=self.user1,
            content='Grandchild',
            parent_message=child
        )
        
        serializer = MessageSerializer(grandchild)
        data = serializer.data
        
        # Should have nested parent_message
        self.assertIsNotNone(data['parent_message'])
        self.assertEqual(data['parent_message']['content'], 'Child')
        
        # Parent should also have nested parent_message
        self.assertIsNotNone(data['parent_message']['parent_message'])
        self.assertEqual(data['parent_message']['parent_message']['content'], 'Parent')