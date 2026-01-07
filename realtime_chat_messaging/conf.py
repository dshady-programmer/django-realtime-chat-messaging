from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.signals import setting_changed

from .defaults import DEFAULTS

SETTINGS_NAMESPACE = "REALTIME_CHAT_MESSAGING"


class Settings:
    def __init__(self):
        self._user_settings = None

    def reload(self):
        self._user_settings = None

    @property
    def user_settings(self):
        if self._user_settings is None:
            self._user_settings = getattr(settings, SETTINGS_NAMESPACE, {})
            validate_and_update(self._user_settings)
        return self._user_settings

    def __getattr__(self, name):
        if name not in DEFAULTS:
            raise AttributeError(f"Invalid setting: {name}")

        val = self.user_settings.get(name, DEFAULTS[name])

        # update the class instance.
        setattr(self, name, val)

        return val



realtime_chat_settings = Settings()

def _reload_settings(**kwargs):
    if kwargs.get("setting") == SETTINGS_NAMESPACE:
        realtime_chat_settings.reload()


setting_changed.connect(_reload_settings)

def _validate_dict_keys(key, value):
    VALID_KEYS = DEFAULTS[key].keys()
    if type(value) != dict:
        raise ImproperlyConfigured(f"{key} configuration must be a dictionary")
    for nested_key, _ in value.items():
        if nested_key not in VALID_KEYS:
            raise ImproperlyConfigured(f"{key} key '{nested_key}' not in valid {key.lower()} keys")



def validate_and_update(user_settings):
    for k, v in user_settings.items():
        if k in ["SERIALIZERS", "MODELS"]:
            _validate_dict_keys(k, v)
            user_settings[k] = {**DEFAULTS[k], **v}

        elif k not in [
                "EVENT_MAPPER", "EXCEPTION_HANDLER_CLASS", "MESSAGE_SOFT_DELETE",
                "PERMISSION_HANDLER_CLASS", "EVENT_HANDLER_CLASS", "ENABLE_NOTIFICATION"
            ]:
            raise ImproperlyConfigured(f"Invalid setting '{k}'")


    

