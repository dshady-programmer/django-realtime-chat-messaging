from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.signals import setting_changed

from .defaults import get_defaults

SETTINGS_NAMESPACE = "REALTIME_CHAT_MESSAGING"


class Settings:
    def __init__(self):
        self.DEFAULTS = get_defaults()
        self._user_settings = None

    def reload(self):
        self._user_settings = None

    @property
    def user_settings(self):
        if self._user_settings is None:
            self._user_settings = getattr(settings, SETTINGS_NAMESPACE, {})
        return self._user_settings

    def __getattr__(self, name):
        if name not in self.DEFAULTS:
            raise AttributeError(f"Invalid setting: {name}")

        val = self.user_settings.get(name, self.DEFAULTS[name])

        # update the class instance.
        setattr(self, name, val)

        return val



realtime_chat_settings = Settings()

def _reload_settings(**kwargs):
    if kwargs.get("setting") == SETTINGS_NAMESPACE:
        realtime_chat_settings.reload()


setting_changed.connect(_reload_settings)

# def validate():
#     if not isinstance(realtime_chat_settings.SERIALIZERS, dict):
#         raise ImproperlyConfigured("SERIALIZER configuration must be a dictionary")
    

