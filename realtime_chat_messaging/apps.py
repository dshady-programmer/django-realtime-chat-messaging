from django.apps import AppConfig


class RealtimeChatMessagingConfig(AppConfig):
    name = 'realtime_chat_messaging'

    def ready(self):
        from . import signals
        return super().ready()