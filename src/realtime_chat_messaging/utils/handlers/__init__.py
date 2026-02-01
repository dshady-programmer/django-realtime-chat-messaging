from .handler_mixins import ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin, SessionHandlerMixin


class EventHandler(ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin, SessionHandlerMixin):
    
    @staticmethod
    def reload_variables():
        """
        reload variables allows all class variables to be reloaded when settings is changed

        Note: this is added only for effectively running test cases when using settings_override()
        """

        ChatNotificationHandlerMixin._reload_variables()
        MessageHandlerMixin._reload_variables()
        RoomHandlerMixin._reload_variables()
        SessionHandlerMixin._reload_variables()