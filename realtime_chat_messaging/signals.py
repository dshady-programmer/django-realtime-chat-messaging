from django.dispatch import receiver 
from django.db.models.signals import m2m_changed, post_save
from django.core.exceptions import ValidationError
from guardian.shortcuts import assign_perm
from .models import OneToOneChat, GroupChat, Channel, ChatNotification


@receiver(m2m_changed, sender=OneToOneChat.participants.through)
def enforce_two_participants_on_one_to_one_chat(sender, instance, action, pk_set, *args, **kwargs):
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
def delete_channels_and_groups_with_no_participants(sender, instance, action, pk_set, **kwargs):
    if action == "post_remove" or action == "post_clear":
        if (hasattr(instance, "participants") and instance.participants.count() < 1) or (hasattr(instance, "subscribers") and instance.subscribers.count() < 1):
            instance.delete()
    elif action == "pre_add":
        if sender == GroupChat.participants.through:
            if instance.participants.count() + len(pk_set) > instance.max_participants:
                raise ValidationError("Maximum number of group participants exceeded")
        else:
            if instance.subscribers.count + len(pk_set) > instance.max_subscribers:
                raise ValidationError("Maximum number of channel subscribers exceeded")



"""
delete chatnotification when recipients length is 0
"""
@receiver(m2m_changed, sender=ChatNotification.recipients.through)
@receiver(m2m_changed, sender=ChatNotification.recipients.through)
def delete_channels_and_groups_with_no_participants(sender, instance, action, pk_set, **kwargs):
    if action == "post_remove" or action == "post_clear":
        if instance.recipients.count() < 1:
            instance.delete()





    