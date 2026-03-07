"""
Main event handler combining all handler mixins.

This module provides the EventHandler class, which aggregates all chat
functionality from specialized handler mixins. The handler is responsible
for executing business logic triggered by WebSocket events.

The EventHandler is configurable via the EVENT_HANDLER_CLASS setting,
allowing custom implementations to override specific functionality.

Handler Categories:
    - ChatNotificationHandlerMixin: Notification management
    - MessageHandlerMixin: Message CRUD, reactions, read receipts
    - RoomHandlerMixin: Room CRUD, member management
    - SessionHandlerMixin: Session tracking and cleanup
"""



from .handler_mixins import ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin, SessionHandlerMixin


class EventHandler(ChatNotificationHandlerMixin, MessageHandlerMixin, RoomHandlerMixin, SessionHandlerMixin):
    """
        Aggregate event handler for all chat operations.

        Combines specialized handler mixins to provide a complete interface for
        processing WebSocket events. Each mixin handles a specific domain:

        - ChatNotificationHandlerMixin: get/group notifications
        - MessageHandlerMixin: send, modify, acknowledge, react, read receipts
        - RoomHandlerMixin: create, list, retrieve, update, add/remove members
        - SessionHandlerMixin: register, update, get active/expired sessions

        This class can be subclassed to override specific handler methods without
        reimplementing the entire handler. Override EVENT_HANDLER_CLASS in
        settings to use a custom implementation.

        Example:
            Custom handler with modified message creation::

                class CustomEventHandler(EventHandler):
                    async def create_message(self, data, user):
                        # Add custom validation
                        if "spam" in data.get("content", "").lower():
                            raise ValidationError("Spam detected")
                        return await super().create_message(data, user)

                # settings.py
                REALTIME_CHAT_MESSAGING = {
                    'EVENT_HANDLER_CLASS': 'myapp.handlers.CustomEventHandler',
                }
    """    
    @staticmethod
    def reload_variables():
        """
            Reload cached class variables from settings.

            This method clears and reloads all handler mixin variables when
            settings change, ensuring consistency across the application.

            Note:
                Primarily used for test cases with @override_settings decorator.
                In production, handlers are loaded once at startup and cached.
        """

        ChatNotificationHandlerMixin._reload_variables()
        MessageHandlerMixin._reload_variables()
        RoomHandlerMixin._reload_variables()
        SessionHandlerMixin._reload_variables()