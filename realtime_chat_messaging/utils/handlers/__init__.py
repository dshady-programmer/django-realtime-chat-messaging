from .handler_mixins import ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin


class EventHandler(ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin):
    pass