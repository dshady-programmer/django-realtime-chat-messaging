"""
Tests for chat application signals
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from guardian.shortcuts import get_perms, assign_perm

from realtime_chat_messaging.models import OneToOneChat, GroupChat, Channel

User = get_user_model()


class OneToOneChatSignalTest(TestCase):
    """Test signals for OneToOneChat"""

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

    def test_one_to_one_chat_enforces_two_participants(self):
        """Test that one-to-one chat must have exactly 2 participants"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        # Should have 2 participants
        self.assertEqual(chat.participants.count(), 2)

    def test_one_to_one_chat_rejects_three_participants(self):
        """Test that adding a third participant raises ValidationError"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        # Try to add a third participant
        from django.db import transaction
        with self.assertRaises(ValidationError) as context:
            with transaction.atomic(): 
                chat.participants.add(self.user3)
    
        self.assertIn('2 participants', str(context.exception))
        self.assertEqual(chat.participants.count(), 2)

    def test_one_to_one_chat_rejects_single_participant(self):
        """Test that having only 1 participant raises ValidationError"""
        chat = OneToOneChat.objects.create()
        
        
        # Try to add only one participant
        with self.assertRaises(ValidationError) as context:
            chat.participants.add(self.user1)
        
        self.assertIn('2 participants', str(context.exception))

    def test_one_to_one_chat_rejects_removing_participant(self):
        """Test that removing a participant raises ValidationError"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        # Try to remove a participant
        with self.assertRaises(ValidationError) as context:
            chat.participants.remove(self.user1)
        
        self.assertIn('2 participants', str(context.exception))

    def test_one_to_one_chat_validates_on_clear(self):
        """Test that clearing participants raises ValidationError"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        # Try to clear all participants
        with self.assertRaises(ValidationError) as context:
            chat.participants.clear()
        
        self.assertIn("2 participants", str(context.exception))


class GroupChatSignalTest(TestCase):
    """Test signals for GroupChat"""

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

    def test_creator_added_as_participant_on_creation(self):
        """Test that creator is automatically added as participant"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        
        self.assertIn(self.creator, group.participants.all())

    def test_creator_added_as_admin_on_creation(self):
        """Test that creator is automatically added as admin"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        
        self.assertIn(self.creator, group.admins.all())

    def test_creator_gets_add_participants_permission(self):
        """Test that creator gets can_add_new_participants permission"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        
        perms = get_perms(self.creator, group)
        self.assertIn('can_add_new_participants', perms)

    def test_group_deleted_when_no_participants(self):
        """Test that group is deleted when all participants leave"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group_id = group.id
        
        # Remove all participants
        group.participants.clear()
        
        # Group should be deleted
        self.assertFalse(GroupChat.objects.filter(id=group_id).exists())

    def test_group_not_deleted_with_participants(self):
        """Test that group is not deleted when participants remain"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group.participants.add(self.member1)
        group_id = group.id
        
        # Remove creator but member1 remains
        group.participants.remove(self.creator)
        
        # Group should still exist
        self.assertTrue(GroupChat.objects.filter(id=group_id).exists())

    def test_signal_only_fires_on_creation(self):
        """Test that signal only adds creator on creation, not on update"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        
        initial_participant_count = group.participants.count()
        initial_admin_count = group.admins.count()
        
        # Update the group
        group.name = 'Updated Group'
        group.save()
        
        # Counts should remain the same
        self.assertEqual(group.participants.count(), initial_participant_count)
        self.assertEqual(group.admins.count(), initial_admin_count)

    def test_group_deleted_when_last_participant_removed(self):
        """Test group deletion when removing last participant"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group.participants.add(self.member1, self.member2)
        group_id = group.id
        
        # Remove all participants one by one
        group.participants.remove(self.creator)
        group.participants.remove(self.member1)
        
        # Group should still exist with one member
        self.assertTrue(GroupChat.objects.filter(id=group_id).exists())
        
        # Remove last participant
        group.participants.remove(self.member2)
        
        # Group should be deleted now
        self.assertFalse(GroupChat.objects.filter(id=group_id).exists())

    def test_multiple_admins_can_be_added(self):
        """Test that multiple admins can be added to group"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.creator
        )
        group.participants.add(self.member1, self.member2)
        group.admins.add(self.member1, self.member2)
        
        self.assertEqual(group.admins.count(), 3)  # creator + 2 members


class ChannelSignalTest(TestCase):
    """Test signals for Channel"""

    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@example.com',
            password='pass123'
        )
        self.subscriber1 = User.objects.create_user(
            username='subscriber1',
            email='subscriber1@example.com',
            password='pass123'
        )
        self.subscriber2 = User.objects.create_user(
            username='subscriber2',
            email='subscriber2@example.com',
            password='pass123'
        )

    def test_creator_added_as_subscriber_on_creation(self):
        """Test that creator is automatically added as subscriber"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        
        self.assertIn(self.creator, channel.subscribers.all())

    def test_creator_added_as_moderator_on_creation(self):
        """Test that creator is automatically added as moderator"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        
        self.assertIn(self.creator, channel.moderators.all())

    def test_creator_gets_channel_permissions(self):
        """Test that creator gets channel permissions"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        
        perms = get_perms(self.creator, channel)
        self.assertIn('can_add_new_subscribers', perms)
        self.assertIn('can_send_messages', perms)

    def test_channel_deleted_when_no_subscribers(self):
        """Test that channel is deleted when all subscribers leave"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel_id = channel.id
        
        # Remove all subscribers
        channel.subscribers.clear()
        
        # Channel should be deleted
        self.assertFalse(Channel.objects.filter(id=channel_id).exists())

    def test_channel_not_deleted_with_subscribers(self):
        """Test that channel is not deleted when subscribers remain"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel.subscribers.add(self.subscriber1)
        channel_id = channel.id
        
        # Remove creator but subscriber1 remains
        channel.subscribers.remove(self.creator)
        
        # Channel should still exist
        self.assertTrue(Channel.objects.filter(id=channel_id).exists())

    def test_signal_only_fires_on_creation(self):
        """Test that signal only adds creator on creation, not on update"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        
        initial_subscriber_count = channel.subscribers.count()
        initial_moderator_count = channel.moderators.count()
        
        # Update the channel
        channel.name = 'Updated Channel'
        channel.save()
        
        # Counts should remain the same
        self.assertEqual(channel.subscribers.count(), initial_subscriber_count)
        self.assertEqual(channel.moderators.count(), initial_moderator_count)

    def test_channel_deleted_when_last_subscriber_removed(self):
        """Test channel deletion when removing last subscriber"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel.subscribers.add(self.subscriber1, self.subscriber2)
        channel_id = channel.id
        
        # Remove all subscribers one by one
        channel.subscribers.remove(self.creator)
        channel.subscribers.remove(self.subscriber1)
        
        # Channel should still exist with one subscriber
        self.assertTrue(Channel.objects.filter(id=channel_id).exists())
        
        # Remove last subscriber
        channel.subscribers.remove(self.subscriber2)
        
        # Channel should be deleted now
        self.assertFalse(Channel.objects.filter(id=channel_id).exists())

    def test_multiple_moderators_can_be_added(self):
        """Test that multiple moderators can be added to channel"""
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.creator
        )
        channel.subscribers.add(self.subscriber1, self.subscriber2)
        channel.moderators.add(self.subscriber1, self.subscriber2)
        
        self.assertEqual(channel.moderators.count(), 3)  # creator + 2 subscribers


class SignalIntegrationTest(TestCase):
    """Integration tests for multiple signals"""

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

    def test_group_and_channel_signals_independent(self):
        """Test that group and channel signals work independently"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.user1
        )
        
        # Both should have creator as member
        self.assertIn(self.user1, group.participants.all())
        self.assertIn(self.user1, channel.subscribers.all())
        
        # Both should have creator with appropriate role
        self.assertIn(self.user1, group.admins.all())
        self.assertIn(self.user1, channel.moderators.all())

    def test_multiple_groups_for_same_user(self):
        """Test that same user can create multiple groups"""
        group1 = GroupChat.objects.create(
            name='Group 1',
            creator=self.user1
        )
        group2 = GroupChat.objects.create(
            name='Group 2',
            creator=self.user1
        )
        
        # User should be in both groups
        self.assertIn(self.user1, group1.participants.all())
        self.assertIn(self.user1, group2.participants.all())
        
        # User should be admin of both groups
        self.assertIn(self.user1, group1.admins.all())
        self.assertIn(self.user1, group2.admins.all())

    def test_multiple_channels_for_same_user(self):
        """Test that same user can create multiple channels"""
        channel1 = Channel.objects.create(
            name='Channel 1',
            creator=self.user1
        )
        channel2 = Channel.objects.create(
            name='Channel 2',
            creator=self.user1
        )
        
        # User should be in both channels
        self.assertIn(self.user1, channel1.subscribers.all())
        self.assertIn(self.user1, channel2.subscribers.all())
        
        # User should be moderator of both channels
        self.assertIn(self.user1, channel1.moderators.all())
        self.assertIn(self.user1, channel2.moderators.all())

    def test_deletion_cascade_on_empty_rooms(self):
        """Test that empty groups and channels are deleted"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.user1
        )
        
        group_id = group.id
        channel_id = channel.id
        
        # Empty both
        group.participants.clear()
        channel.subscribers.clear()
        
        # Both should be deleted
        self.assertFalse(GroupChat.objects.filter(id=group_id).exists())
        self.assertFalse(Channel.objects.filter(id=channel_id).exists())

    def test_permissions_are_user_specific(self):
        """Test that permissions are assigned to specific users"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        channel = Channel.objects.create(
            name='Test Channel',
            creator=self.user1
        )
        
        # user1 should have permissions
        group_perms = get_perms(self.user1, group)
        channel_perms = get_perms(self.user1, channel)
        
        self.assertIn('can_add_new_participants', group_perms)
        self.assertIn('can_add_new_subscribers', channel_perms)
        self.assertIn('can_send_messages', channel_perms)
        
        # user2 should NOT have permissions
        group_perms_user2 = get_perms(self.user2, group)
        channel_perms_user2 = get_perms(self.user2, channel)
        
        self.assertNotIn('can_add_new_participants', group_perms_user2)
        self.assertNotIn('can_add_new_subscribers', channel_perms_user2)
        self.assertNotIn('can_send_messages', channel_perms_user2)

        # now give user2 permissions
        assign_perm('can_add_new_participants', self.user2, group)
        assign_perm('can_send_messages', self.user2, channel)
        assign_perm('can_add_new_subscribers', self.user2, channel)

        # now get permissions again
        group_perms_user2_updated = get_perms(self.user2, group)
        channel_perms_user2_updated = get_perms(self.user2, channel)
        
        self.assertIn('can_add_new_participants', group_perms_user2_updated)
        self.assertIn('can_add_new_subscribers', channel_perms_user2_updated)
        self.assertIn('can_send_messages', channel_perms_user2_updated)

    def test_one_to_one_chat_not_affected_by_group_channel_signals(self):
        """Test that OneToOneChat is not affected by other signals"""
        chat = OneToOneChat.objects.create()
        chat.participants.add(self.user1, self.user2)
        
        chat_id = chat.id
        
        # Should have exactly 2 participants
        self.assertEqual(chat.participants.count(), 2)
        
        # Chat should not be deleted when we create groups/channels
        GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        Channel.objects.create(
            name='Test Channel',
            creator=self.user1
        )
        
        # Chat should still exist
        self.assertTrue(OneToOneChat.objects.filter(id=chat_id).exists())
        
        # Chat should still have 2 participants
        chat.refresh_from_db()
        self.assertEqual(chat.participants.count(), 2)


class SignalEdgeCaseTest(TestCase):
    """Test edge cases and error conditions"""

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

    def test_creator_cannot_be_removed_if_only_participant(self):
        """Test behavior when trying to remove creator as only participant"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        group_id = group.id
        
        # Try to remove creator (should delete group)
        group.participants.remove(self.user1)
        
        # Group should be deleted
        self.assertFalse(GroupChat.objects.filter(id=group_id).exists())

    def test_adding_participant_after_creation(self):
        """Test adding participants after initial creation"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        
        initial_count = group.participants.count()
        self.assertEqual(initial_count, 1)
        
        # Add new participant
        group.participants.add(self.user2)
        
        # Should have one more participant
        self.assertEqual(group.participants.count(), initial_count + 1)

    def test_permissions_persist_after_updates(self):
        """Test that permissions persist after model updates"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        
        # Update group name
        group.name = 'Updated Group'
        group.save()
        
        # Permissions should still exist
        perms = get_perms(self.user1, group)
        self.assertIn('can_add_new_participants', perms)

    def test_bulk_operations(self):
        """Test bulk add/remove operations"""
        group = GroupChat.objects.create(
            name='Test Group',
            creator=self.user1
        )
        
        users = [
            User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='pass123'
            )
            for i in range(3, 7)
        ]
        
        # Bulk add
        group.participants.add(*users)
        
        # Should have creator + 4 new users
        self.assertEqual(group.participants.count(), 5)
        
        # Bulk remove (but keep creator)
        group.participants.remove(*users)
        
        # Should have only creator
        self.assertEqual(group.participants.count(), 1)


    