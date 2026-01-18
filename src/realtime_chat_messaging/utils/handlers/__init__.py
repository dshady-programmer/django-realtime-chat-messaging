from .handler_mixins import ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin, SessionHandlerMixin


class EventHandler(ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin, SessionHandlerMixin):
    pass