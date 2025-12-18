from realtime_chat_messaging.models import ChatNotification

def create_chat_notification(message, type, user):
    room = message.room
    recipients = None
    if hasattr(room, "subscribers"):
        recipients = list(room.subscribers.all())
    elif hasattr(room, "participants"):
        recipients = list(room.participants.all())

    if recipients is not None:
        if user in recipients:
            recipients.remove(user)
        notification = ChatNotification.objects.create(message=message, notification_type=type)
        notification.recipients.set(recipients)
    

def update_chat_notification(message_id, user, many=False):
    if many:
        """
            if many == True:
              then message = [id1, id2...]
        """
        notifications = ChatNotification.objects.filter(message__id__in=message_id, recipients=user)
    else:
        notifications = ChatNotification.objects.filter(message__id=message_id, recipients=user)
    if notifications.exists():
        for notification in notifications:
            notification.recipients.remove(user)
