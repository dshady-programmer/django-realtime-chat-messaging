from django.apps import AppConfig
from realtime_chat_messaging.conf import realtime_chat_settings
_ = realtime_chat_settings.MODELS # load defined models into default settings object

class RealtimeChatMessagingConfig(AppConfig):
    name = 'realtime_chat_messaging'

    def ready(self):
        from . import signals
        return super().ready()