from realtime_chat_messaging.models import ChatNotification

def create_chat_notification(message, type):
    room = message.room
    recipients = None
    if getattr(room, "subscribers"):
        recipients = room.subscribers.all()
    elif getattr(room, "participants"):
        recipients = room.participants.all()

    if recipients is not None:
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
