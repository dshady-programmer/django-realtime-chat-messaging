"""
Django signal handlers for maintaining data integrity in the chat system.

This module defines signal receivers that enforce business rules, manage
permissions, and maintain referential integrity across the chat models.
Signals handle automatic relationship management, validation, and cleanup.
"""

from django.dispatch import receiver 
from django.db.models.signals import m2m_changed, post_save, pre_save, pre_delete
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm,remove_perm
from .models import Room, OneToOneChat, GroupChat, Channel, ChatNotification,Reaction
from django.contrib.auth import get_user_model
User = get_user_model()


@receiver(pre_save, sender=Room)
@receiver(pre_save, sender=OneToOneChat)
@receiver(pre_save, sender=GroupChat)
@receiver(pre_save, sender=Channel)
def create_room_property(sender, instance, *args, **kwargs):
    """
        Automatically create a RoomProperty instance if one doesn't exist.

        Ensures every room has an associated property object before saving.
    """    
    from realtime_chat_messaging.utils.loader import get_model
    RoomProperty = get_model("RoomProperty")
    if not hasattr(instance, 'property') or not instance.property:
        room_property = RoomProperty.objects.create()
        instance.property = room_property




@receiver(pre_delete, sender=User)
def cleanup_one_to_one_chat_when_user_is_deleted(sender, instance, *args, **kwargs):
    """
        Track when a user is about to be deleted so it their OneToOneChat can be cleaned up

        Note: Not the ideal solution and would be improved in the next release

    """
    from realtime_chat_messaging.utils.loader import get_model
    LoadedOneToOneChat = get_model('OneToOneChat')
    if LoadedOneToOneChat == OneToOneChat:
        # Only perform cleanup if the loaded OneToOneChat model is the default one, 
        # otherwise we delegate that responsibility to theuser of custom models
        LoadedOneToOneChat.objects.filter(participants=instance).delete()



@receiver(m2m_changed, sender=OneToOneChat.participants.through)
def enforce_two_participants_on_one_to_one_chat(sender, instance, action, pk_set, *args, **kwargs):
    """
        Enforce exactly 2 participants in OneToOneChat rooms.

        Validates that:
        - OneToOneChat always has exactly 2 participants (no more, no less)
        - Duplicate OneToOneChat rooms between the same 2 users cannot be created
        - When a participants is less than 2 on removal delete the chat
        Raises:
            ValidationError: If participant count != 2 or chat already exists.
    """    
    
    if sender != OneToOneChat.participants.through:
        return
    if action == "post_add" or action == "post_remove" or action == "post_clear":
        if instance.participants.count() != 2:
            raise ValidationError("A one to one chat can only have 2 participants")
    elif action == "pre_add": 
        pks = list(pk_set)
        if len(pks) == 2:
            u = OneToOneChat.objects.filter(participants__id=pks[0]).filter(participants__id=pks[1])
            if u.exists():
                raise ValidationError("Chat already exists")

@receiver(post_save, sender=GroupChat)
@receiver(post_save, sender=Channel)
def add_creator_as_participant_and_admin(sender, instance, created, *args, **kwargs):
    """
        Automatically add room creator as member with admin/moderator permissions.

        On GroupChat creation:
        - Adds creator as participant and admin
        - Grants add/remove participant permissions

        On Channel creation:
        - Adds creator as subscriber and moderator
        - Grants add/remove subscriber and send message permissions
    """    
    if sender not in [GroupChat, Channel]:
        return
    if created:
        if sender == GroupChat:
            instance.participants.add(instance.creator)
            instance.admins.add(instance.creator)
            assign_perm("can_add_new_participants", instance.creator, instance)
            assign_perm("can_remove_participants", instance.creator, instance)
        else:
            instance.subscribers.add(instance.creator)
            instance.moderators.add(instance.creator)
            assign_perm("can_add_new_subscribers", instance.creator, instance)
            assign_perm("can_remove_subscribers", instance.creator, instance)
            assign_perm("can_send_messages", instance.creator, instance)


@receiver(m2m_changed, sender=GroupChat.participants.through)
@receiver(m2m_changed, sender=Channel.subscribers.through)
def delete_channels_and_groups_with_no_participants_and_max_participants_enforcement(sender, instance, action, pk_set, **kwargs):
    """
        Delete empty rooms and enforce maximum member limits.

        Automatically deletes GroupChat/Channel when last member leaves.
        Prevents adding members beyond max_participants/max_subscribers limit.

        Raises:
            ValidationError: If adding members would exceed the maximum.
    """
    if sender not in [GroupChat.participants.through, Channel.subscribers.through]:
        return
    if action == "post_remove" or action == "post_clear":
        if (hasattr(instance, "participants") and instance.participants.count() < 1) or (hasattr(instance, "subscribers") and instance.subscribers.count() < 1):
            instance.delete()
    elif action == "pre_add":

        if sender == GroupChat.participants.through:
            if (instance.participants.count() + len(pk_set)) > instance.max_participants:
                raise ValidationError("Maximum number of group participants exceeded")
        else:
            if (instance.subscribers.count() + len(pk_set)) > instance.max_subscribers:
                raise ValidationError("Maximum number of channel subscribers exceeded")



@receiver(m2m_changed, sender=GroupChat.admins.through)
@receiver(m2m_changed, sender=Channel.moderators.through)
def add_permissions_to_admin_and_moderators(sender, instance, action, pk_set, **kwargs):
    """
        Automatically manage permissions when admins/moderators are added or removed.

        For GroupChat admins:
        - Grants: can_add_new_participants, can_remove_participants

        For Channel moderators:
        - Grants: can_add_new_subscribers, can_remove_subscribers, can_send_messages

        Permissions are automatically revoked when admin/moderator status is removed.
    """
    if sender not in [GroupChat.admins.through, Channel.moderators.through]:
        return
    if action == "pre_remove" or action == "pre_clear":
        users = User.objects.filter(pk__in=list(pk_set))
        for user in users:
            if sender == GroupChat.admins.through:
                remove_perm('can_add_new_participants', user, instance)
                remove_perm('can_remove_participants', user, instance)
            else:
                remove_perm('can_add_new_subscribers', user, instance)
                remove_perm('can_remove_subscribers', user, instance)
                remove_perm('can_send_messages', user, instance)

    if action == "pre_add":
        users = User.objects.filter(pk__in=list(pk_set))
        for user in users:
            if sender == GroupChat.admins.through:
                assign_perm('can_add_new_participants', user, instance)
                assign_perm('can_remove_participants', user, instance)
            else:
                assign_perm('can_add_new_subscribers', user, instance)
                assign_perm('can_remove_subscribers', user, instance)
                assign_perm('can_send_messages', user, instance)




"""
delete chatnotification when recipients length is 0
"""
@receiver(m2m_changed, sender=ChatNotification.recipients.through)
def delete_channels_and_groups_with_no_participants(sender, instance, action, pk_set, **kwargs):
    """
        Delete ChatNotification when all recipients have been removed.

        Automatically cleans up notifications that no longer have any recipients.
    """    
    if action == "post_remove" or action == "post_clear":
        if instance.recipients.count() < 1:
            instance.delete()



"""update message reaction"""
@receiver(pre_save, sender=Reaction)
def overwrite_message_reaction(sender, instance, *args, **kwargs):

    """
        Replace existing reaction when user reacts to the same message again.

        Ensures each user can only have one reaction per message. If a user
        changes their reaction, the old one is automatically deleted.

        Raises:
            ValidationError: If reaction_content is empty.
    """
    if not instance.reaction_content:
        raise ValidationError("reaction_content can't be empty")
    r = Reaction.objects.filter(user=instance.user, message=instance.message)
    if r.exists() and r.first().reaction_content != instance.reaction_content:
        r.delete()

        


    