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
        instance.creator