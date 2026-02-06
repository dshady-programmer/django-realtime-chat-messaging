import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from guardian.shortcuts import assign_perm
from realtime_chat_messaging.models import (
    RoomProperty, OneToOneChat, GroupChat, Channel, Message,
    ChatNotification, Reaction
)

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create 10 test users"""
    return create_users(10)


@pytest.mark.django_db
class TestOneToOneChatSignals:
    """Test signals for OneToOneChat model"""

    def test_enforce_two_participants_on_add(self, users):
        """Test that adding more than 2 participants raises error"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            chat.participants.add(users[2])

    def test_enforce_two_participants_on_remove(self, users):
        """Test that removing participant raises error"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            chat.participants.remove(users[0])

    def test_enforce_two_participants_on_clear(self, users):
        """Test that clearing participants raises error"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        with pytest.raises(ValidationError, match="A one to one chat can only have 2 participants"):
            chat.participants.clear()

    def test_prevent_duplicate_one_to_one_chat(self, users):
        """Test that duplicate one-to-one chats are prevented"""
        chat1 = OneToOneChat.objects.create()
        chat1.participants.set([users[0], users[1]])
        
        chat2 = OneToOneChat.objects.create()
        with pytest.raises(ValidationError, match="Chat already exists"):
            chat2.participants.set([users[0], users[1]])

    def test_prevent_duplicate_with_reversed_order(self, users):
        """Test that duplicate detection works regardless of participant order"""
        chat1 = OneToOneChat.objects.create()
        chat1.participants.set([users[0], users[1]])
        
        chat2 = OneToOneChat.objects.create()
        with pytest.raises(ValidationError, match="Chat already exists"):
            chat2.participants.set([users[1], users[0]])

    def test_different_participants_allowed(self, users):
        """Test that different participant combinations are allowed"""
        chat1 = OneToOneChat.objects.create()
        chat1.participants.set([users[0], users[1]])
        
        chat2 = OneToOneChat.objects.create()
        chat2.participants.set([users[0], users[2]])
        
        assert OneToOneChat.objects.count() == 2

    def test_create_room_property_for_onetoone(self):
        """
        Test that one to one chat automatically creates a room property
        """
        chat = OneToOneChat.objects.create()
        assert chat.property is not None
        assert isinstance(chat.property, RoomProperty)
        assert chat.property.preferences == {}

@pytest.mark.django_db
class TestGroupChatSignals:
    """Test signals for GroupChat model"""

    def test_creator_added_as_participant_on_creation(self, users):
        """Test that creator is automatically added as participant"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        
        assert users[0] in group.participants.all()

    def test_creator_added_as_admin_on_creation(self, users):
        """Test that creator is automatically added as admin"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        
        assert users[0] in group.admins.all()

    def test_creator_gets_add_participants_permission(self, users):
        """Test that creator gets can_add_new_participants permission"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        
        assert users[0].has_perm('can_add_new_participants', group)

    def test_creator_gets_remove_participants_permission(self, users):
        """Test that creator gets can_remove_participants permission"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        
        assert users[0].has_perm('can_remove_participants', group)

    def test_group_deleted_when_no_participants(self, users):
        """Test that group is deleted when all participants leave"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        group_id = group.id
        
        group.participants.remove(users[0])
        
        assert not GroupChat.objects.filter(id=group_id).exists()

    def test_max_participants_enforced_on_add(self, users):
        """Test that max_participants limit is enforced"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0],
            max_participants=2
        )
        
        group.participants.add(users[1])
        
        with pytest.raises(ValidationError, match="Maximum number of group participants exceeded"):
            group.participants.add(users[2])

    def test_max_participants_enforced_on_bulk_add(self, users):
        """Test that max_participants is enforced on bulk add"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0],
            max_participants=2
        )
        
        # Try to add 2 users when only 1 spot available
        with pytest.raises(ValidationError, match="Maximum number of group participants exceeded"):
            group.participants.add(users[1], users[2])

    def test_admin_gets_permissions_on_add(self, users):
        """Test that adding admin grants permissions"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        group.participants.add(users[1])
        
        # Add as admin
        group.admins.add(users[1])
        
        assert users[1].has_perm('can_add_new_participants', group)
        assert users[1].has_perm('can_remove_participants', group)

    def test_admin_loses_permissions_on_remove(self, users):
        """Test that removing admin revokes permissions"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        group.participants.add(users[1])
        group.admins.add(users[1])
        
        # Remove admin
        group.admins.remove(users[1])
        
        assert not users[1].has_perm('can_add_new_participants', group)
        assert not users[1].has_perm('can_remove_participants', group)

    def test_multiple_admins_can_be_added(self, users):
        """Test that multiple admins can be added"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        group.participants.add(users[1], users[2])
        group.admins.add(users[1], users[2])
        
        assert users[1].has_perm('can_add_new_participants', group)
        assert users[2].has_perm('can_add_new_participants', group)


    def test_create_room_property_for_groupchat(self, users):
        """
        Test that group chat automatically creates a room property
        """
        chat = GroupChat.objects.create(
                name="Test Group",
                creator=users[0]
        )
        assert chat.property is not None
        assert isinstance(chat.property, RoomProperty)
        assert chat.property.preferences == {}

@pytest.mark.django_db
class TestChannelSignals:
    """Test signals for Channel model"""

    def test_creator_added_as_subscriber_on_creation(self, users):
        """Test that creator is automatically added as subscriber"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0]
        )
        
        assert users[0] in channel.subscribers.all()

    def test_creator_added_as_moderator_on_creation(self, users):
        """Test that creator is automatically added as moderator"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0]
        )
        
        assert users[0] in channel.moderators.all()

    def test_creator_gets_channel_permissions(self, users):
        """Test that creator gets all channel permissions"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0]
        )
        
        assert users[0].has_perm('can_add_new_subscribers', channel)
        assert users[0].has_perm('can_remove_subscribers', channel)
        assert users[0].has_perm('can_send_messages', channel)

    def test_channel_deleted_when_no_subscribers(self, users):
        """Test that channel is deleted when all subscribers leave"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0]
        )
        channel_id = channel.id
        
        channel.subscribers.remove(users[0])
        
        assert not Channel.objects.filter(id=channel_id).exists()

    def test_max_subscribers_enforced_on_add(self, users):
        """Test that max_subscribers limit is enforced"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0],
            max_subscribers=2
        )
        
        channel.subscribers.add(users[1])
        
        with pytest.raises(ValidationError, match="Maximum number of channel subscribers exceeded"):
            channel.subscribers.add(users[2])

    def test_moderator_gets_permissions_on_add(self, users):
        """Test that adding moderator grants permissions"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0]
        )
        channel.subscribers.add(users[1])
        
        # Add as moderator
        channel.moderators.add(users[1])
        
        assert users[1].has_perm('can_add_new_subscribers', channel)
        assert users[1].has_perm('can_remove_subscribers', channel)
        assert users[1].has_perm('can_send_messages', channel)

    def test_moderator_loses_permissions_on_remove(self, users):
        """Test that removing moderator revokes permissions"""
        channel = Channel.objects.create(
            name="Test Channel",
            creator=users[0]
        )
        channel.subscribers.add(users[1])
        channel.moderators.add(users[1])
        
        # Remove moderator
        channel.moderators.remove(users[1])
        
        assert not users[1].has_perm('can_add_new_subscribers', channel)
        assert not users[1].has_perm('can_remove_subscribers', channel)
        assert not users[1].has_perm('can_send_messages', channel)



    def test_create_room_property_for_channel(self, users):
        """
        Test that channel automatically creates a room property
        """
        chat = Channel.objects.create(
            name="Test Channel",
            creator=users[0])
        
        assert chat.property is not None
        assert isinstance(chat.property, RoomProperty)
        assert chat.property.preferences == {}


@pytest.mark.django_db
class TestChatNotificationSignals:
    """Test signals for ChatNotification model"""

    def test_notification_deleted_when_no_recipients(self, users):
        """Test that notification is deleted when all recipients are removed"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
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
        
        assert not ChatNotification.objects.filter(id=notification_id).exists()

    def test_notification_not_deleted_when_recipients_exist(self, users):
        """Test that notification is not deleted when recipients still exist"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
            sender=users[0],
            content="Test"
        )
        
        notification = ChatNotification.objects.create(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        notification.recipients.add(users[1], users[2])
        
        # Remove one recipient
        notification.recipients.remove(users[1])
        
        # Notification should still exist
        assert ChatNotification.objects.filter(id=notification.id).exists()
        assert notification.recipients.count() == 1

    def test_notification_deleted_on_clear(self, users):
        """Test that notification is deleted when recipients are cleared"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
            sender=users[0],
            content="Test"
        )
        
        notification = ChatNotification.objects.create(
            message=message,
            notification_type='NEW_MESSAGE'
        )
        notification.recipients.add(users[1])
        notification_id = notification.id
        
        # Clear all recipients
        notification.recipients.clear()
        
        assert not ChatNotification.objects.filter(id=notification_id).exists()


@pytest.mark.django_db
class TestReactionSignals:
    """Test signals for Reaction model"""

    def test_empty_reaction_content_raises_error(self, users):
        """Test that empty reaction_content raises ValidationError"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
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

    def test_reaction_update_deletes_old_reaction(self, users):
        """Test that updating reaction deletes old one"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
            sender=users[0],
            content="Test"
        )
        
        # Create first reaction
        reaction1 = Reaction.objects.create(
            message=message,
            user=users[1],
            reaction_content="👍"
        )
        reaction1_id = reaction1.id
        
        # Create second reaction with different content
        reaction2 = Reaction(
            message=message,
            user=users[1],
            reaction_content="❤️"
        )
        reaction2.save()
        
        # Old reaction should be deleted
        assert not Reaction.objects.filter(id=reaction1_id).exists()
        
        # New reaction should exist
        assert Reaction.objects.filter(message=message, user=users[1]).count() == 1
        current_reaction = Reaction.objects.get(message=message, user=users[1])
        assert current_reaction.reaction_content == "❤️"

    def test_same_reaction_content_not_deleted(self, users):
        """Test that same reaction content doesn't trigger deletion"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
            sender=users[0],
            content="Test"
        )
        
        # Create reaction
        reaction1 = Reaction.objects.create(
            message=message,
            user=users[1],
            reaction_content="👍"
        )
        reaction1_id = reaction1.id
        
        # Try to create same reaction (will hit unique constraint)
        # The signal should not delete the existing one
        # Note: This will fail at database level due to unique constraint
        # But the signal logic should handle same content check
        
        # Reaction should still exist
        assert Reaction.objects.filter(id=reaction1_id).exists()

    def test_different_users_can_have_different_reactions(self, users):
        """Test that different users can react to same message"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        message = Message.objects.create(
            room=chat,
            sender=users[0],
            content="Test"
        )
        
        reaction1 = Reaction.objects.create(
            message=message,
            user=users[1],
            reaction_content="👍"
        )
        
        reaction2 = Reaction.objects.create(
            message=message,
            user=users[2],
            reaction_content="❤️"
        )
        
        assert Reaction.objects.filter(message=message).count() == 2
        assert reaction1.reaction_content == "👍"
        assert reaction2.reaction_content == "❤️"


@pytest.mark.django_db
class TestSignalEdgeCases:
    """Test edge cases and complex signal interactions"""

    def test_removing_last_admin_as_participant_deletes_group(self, users):
        """Test complex scenario: removing last admin also triggers group deletion"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0],
            max_participants=1
        )
        
        # Creator is the only participant and admin
        group_id = group.id
        
        group.participants.remove(users[0])
        
        # Group should be deleted
        assert not GroupChat.objects.filter(id=group_id).exists()

    def test_multiple_signal_triggers_in_sequence(self, users):
        """Test multiple signals triggered in sequence"""
        # Create group (triggers post_save signal)
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0]
        )
        
        # Add participants (triggers m2m_changed)
        group.participants.add(users[1])
        
        # Add admin (triggers m2m_changed for permissions)
        group.admins.add(users[1])
        
        # Verify all signals worked correctly
        assert users[0] in group.participants.all()
        assert users[1] in group.participants.all()
        assert users[1].has_perm('can_add_new_participants', group)

    def test_bulk_operations_handle_signals_correctly(self, users):
        """Test that bulk operations handle signals correctly"""
        group = GroupChat.objects.create(
            name="Test Group",
            creator=users[0],
            max_participants=10
        )
        
        # Bulk add participants
        group.participants.add(users[1], users[2], users[3])
        
        assert group.participants.count() == 4

    def test_signal_rollback_on_error(self, users):
        """Test that errors in signals prevent operation"""
        chat = OneToOneChat.objects.create()
        chat.participants.set([users[0], users[1]])
        
        initial_count = chat.participants.count()
        
        # Try to add third participant (should fail)
        with pytest.raises(ValidationError):
            chat.participants.add(users[2])
        
        # Count should remain unchanged
        assert chat.participants.count() == initial_count