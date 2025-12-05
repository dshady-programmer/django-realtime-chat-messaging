from django.dispatch import receiver 
from django.db.models.signals import m2m_changed, post_save
from django.core.exceptions import ValidationError

from .models import OneToOneChat, GroupChat, Channel


@receiver(m2m_changed, sender=OneToOneChat.participants.through)
def enforce_two_participants_on_one_to_one_chat(sender, instance, action, pk_set, *args, **kwargs):
    if action == "post_add" or action == "post_remove":
        if instance.participants.count() != 2:
            raise ValidationError("A one to one chat can only have 2 participants")
        

@receiver(post_save, sender=GroupChat)
@receiver(post_save, sender=Channel)
def add_creator_as_participant_and_admin(sender, instance, created, *args, **kwargs):
    if created:
        if sender == GroupChat:
            instance.participants.add(instance.creator)
            instance.admins.add(instance.creator)
        else:
            instance.subscribers.add(instance.creator)
            instance.moderators.add(instance.creator)


@receiver(m2m_changed, sender=GroupChat.participants.through)
@receiver(m2m_changed, sender=Channel.subscribers.through)
def delete_channels_and_groups_with_no_participants(sender, instance, action, pk_set, **kwargs):
    if action == "post_remove" or action == "post_clear":
        if (hasattr(instance, "participants") and instance.participants.count() < 1) or (hasattr(instance, "subscribers") and instance.subscribers.count() < 1):
            instance.delete()



    