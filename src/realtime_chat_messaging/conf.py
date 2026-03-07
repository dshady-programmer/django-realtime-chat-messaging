"""
Configuration management for the real-time chat messaging system.

This module provides a lazy-loading settings object that merges user-defined
settings with package defaults, validates configuration, and handles runtime
setting changes. It implements a pattern similar to Django REST Framework's
settings management.

The settings system supports:
- Lazy evaluation (settings loaded only when accessed)
- User overrides via REALTIME_CHAT_MESSAGING in Django settings
- Validation of nested dictionary structures (SERIALIZERS, MODELS)
- Hot reloading when settings change during testing
- Automatic registration of model paths in Django settings

Key Components:
    - Settings: Main configuration class with lazy loading
    - realtime_chat_settings: Global settings instance
    - Validation functions: Ensure configuration integrity
    - Signal handlers: React to setting changes in tests
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.signals import setting_changed

from .defaults import DEFAULTS

SETTINGS_NAMESPACE = "REALTIME_CHAT_MESSAGING"
"""
The Django settings key where user configuration is stored.

User settings should be defined in Django's settings.py as a dictionary:
    REALTIME_CHAT_MESSAGING = {
        'MESSAGE_SOFT_DELETE': True,
        'SERIALIZERS': {'MessageSerializer': 'myapp.CustomMessageSerializer'},
        ...
    }
"""

class Settings:
    """
        Lazy settings container that merges user settings with defaults.

        This class implements a proxy pattern where settings are loaded only when
        first accessed, then cached for subsequent lookups. It automatically merges
        user-defined settings from Django's settings module with package defaults.

        The class supports hot reloading during tests via Django's setting_changed
        signal, ensuring that test setting overrides are properly applied.

        Attributes:
            _user_settings (dict | None): Cached user settings from Django config.

        Example:
            >>> from realtime_chat_messaging.conf import realtime_chat_settings
            >>> threshold = realtime_chat_settings.INACTIVITY_THRESHOLD
            >>> print(threshold)
            60
    """
    def __init__(self):
        """
            Initialize the settings container.

            Creates an empty settings object. User settings are not loaded until
            first access to enable lazy evaluation.
        """
        self._user_settings = None

    def reload(self):
        """
            Clear all cached settings and reload from Django settings.

            This method is called when Django's setting_changed signal is received,
            typically during test runs when settings are temporarily overridden.
            It clears all cached values to ensure fresh settings are loaded on the
            next access.

            The reload also clears internal loader caches for models and serializers,
            and reloads EventHandler variables to ensure consistency across the
            entire system.

            Note:
                This is primarily used during testing. In production, settings are
                loaded once and cached for the lifetime of the process.
        """
        self._user_settings = None
        for key in DEFAULTS:
            self.__dict__.pop(key, None)
        # clear loader caches... it's the entrypoint to loading model and serializer settings.
        from realtime_chat_messaging.utils import loader
        from realtime_chat_messaging.utils.handlers import EventHandler
        loader.clear_caches()
        EventHandler.reload_variables()



    @property
    def user_settings(self):
        """
            Lazily load and cache user settings from Django configuration.

            This property retrieves settings from Django's settings module under
            the REALTIME_CHAT_MESSAGING key, validates and merges them with
            defaults, then caches the result for future access.

            Returns:
                dict: Validated and merged user settings.

            Note:
                Validation occurs only on first access. Subsequent accesses return
                the cached dictionary without re-validation.
        """
        if self._user_settings is None:
            self._user_settings = getattr(settings, SETTINGS_NAMESPACE, {})
            validate_and_update(self._user_settings)
        return self._user_settings

    def __getattr__(self, name):
        """
            Retrieve a setting value with fallback to defaults.

            This method is called when accessing settings attributes (e.g.,
            settings.INACTIVITY_THRESHOLD). It first checks user settings, falls
            back to defaults if not found, then caches the resolved value on the
            instance to avoid repeated lookups.

            Args:
                name (str): The setting name to retrieve.

            Returns:
                The setting value (type varies by setting).

            Raises:
                AttributeError: If the setting name is not defined in DEFAULTS.

            Example:
                >>> settings = Settings()
                >>> settings.MESSAGE_SOFT_DELETE  # Returns False (default)
                False
        """
        if name not in DEFAULTS:
            raise AttributeError(f"Invalid setting: {name}")
        val = self.user_settings.get(name, DEFAULTS[name])
        # update the class instance.
        # Cache resolved value to avoid repeated lookup
        setattr(self, name, val)

        return val



realtime_chat_settings = Settings()
"""
Global settings instance for the real-time chat messaging system.

This is the primary interface for accessing configuration throughout the
package. Import this instance rather than creating new Settings objects.

Example:
    >>> from realtime_chat_messaging.conf import realtime_chat_settings
    >>> serializer_class = realtime_chat_settings.SERIALIZERS['MessageSerializer']
"""



def _reload_settings(**kwargs):
    """
    Signal handler for Django's setting_changed signal.

    This function is called whenever Django settings are modified during test
    runs (e.g., with @override_settings decorator). It triggers a reload of
    the realtime_chat_settings object to ensure tests see updated configuration.

    Args:
        **kwargs: Signal arguments. Only processes if 'setting' matches
            SETTINGS_NAMESPACE.

    Note:
        This is connected to Django's setting_changed signal and should not
        be called directly.
    """
    if kwargs.get("setting") == SETTINGS_NAMESPACE:
        print("Reloading realtime chat messaging settings...")
        realtime_chat_settings.reload()


setting_changed.connect(_reload_settings)

def _validate_dict_keys(key, value):
    """
        Validate that dictionary setting keys match expected defaults.

        This internal function ensures that when users override SERIALIZERS or
        MODELS settings, they only provide keys that exist in the default
        configuration. This prevents typos and configuration errors.

        Args:
            key (str): The setting name being validated (e.g., 'SERIALIZERS').
            value (dict): The user-provided configuration dictionary.

        Raises:
            ImproperlyConfigured: If value is not a dict or contains invalid keys.

        Example:
            Valid::

                {'MessageSerializer': 'myapp.CustomSerializer'}

            Invalid (raises ImproperlyConfigured)::

                {'MessageSerializerTypo': 'myapp.CustomSerializer'}
    """
    VALID_KEYS = DEFAULTS[key].keys()
    if type(value) != dict:
        raise ImproperlyConfigured(f"{key} configuration must be a dictionary")
    for nested_key, _ in value.items():
        if nested_key not in VALID_KEYS:
            raise ImproperlyConfigured(f"{key} key '{nested_key}' not in valid {key.lower()} keys")

        



def validate_and_update(user_settings):
    """
        Validate user settings and merge with defaults.

        This function performs comprehensive validation of user-provided settings,
        ensures dictionary settings (SERIALIZERS, MODELS) are properly merged with
        defaults, and registers model paths in Django settings for external access.

        Validation Rules:
            - SERIALIZERS and MODELS must be dictionaries
            - Dictionary keys must exist in DEFAULTS
            - All setting names must be valid (exist in DEFAULTS)
            - Dictionary settings are merged (user overrides + defaults)

        Args:
            user_settings (dict): User-provided settings from Django config.

        Raises:
            ImproperlyConfigured: If any validation rule is violated.

        Side Effects:
            - Modifies user_settings dict in-place to add default values
            - Registers model paths in Django settings with
            REALTIME_CHAT_MESSAGING_<MODEL>_MODEL format

        Example:
            User provides::

                {'SERIALIZERS': {'MessageSerializer': 'myapp.CustomSerializer'}}

            After validation, user_settings contains::

                {
                    'SERIALIZERS': {
                        'MessageSerializer': 'myapp.CustomSerializer',
                        'RoomSerializer': 'realtime_chat_messaging.serializers.RoomSerializer',
                        ... (all other defaults)
                    }
                }
    """
    for k, v in user_settings.items():
        if k in ["SERIALIZERS", "MODELS"]:
            _validate_dict_keys(k, v)
            user_settings[k] = {**DEFAULTS[k], **v}

        elif k not in DEFAULTS:
            raise ImproperlyConfigured(f"Invalid setting '{k}'")
    update_settings_with_models(user_settings.get('MODELS') or DEFAULTS['MODELS'])
    


    


def update_settings_with_models(models):
    """
        Register model paths in Django settings for external access.

        This function creates individual Django settings entries for each model
        in the format REALTIME_CHAT_MESSAGING_<MODEL>_MODEL. This allows other
        parts of Django (like migrations, admin, or external packages) to
        reference the models without importing the chat package directly.

        Args:
            models (dict): Dictionary mapping model names to import paths.

        Example:
            Given::

                models = {'Message': 'realtime_chat_messaging.Message'}

            Creates Django setting::

                settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL = 'realtime_chat_messaging.Message'

        Note:
            These settings are used by Django's swappable model system and by
            any code that needs to dynamically import models based on configuration.
    """
    for k, v in models.items():
        setattr(settings, f"{SETTINGS_NAMESPACE}_{k.upper()}_MODEL", v)
        