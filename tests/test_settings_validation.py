"""
Unit tests for settings validation and configuration.

Tests cover:
- Settings validation and merging with defaults
- Invalid configuration detection
- Django settings updates for swappable models
- Settings reload behavior
- Partial override merging
"""
import pytest
from django.test import override_settings
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings as django_settings


@pytest.mark.django_db
class TestSettingsValidation:
    """Test settings validation in validate_and_update"""
    
    def test_valid_model_override(self):
        """Test that valid model override is accepted"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {
                'Message': 'custom_app.CustomMessage'
            }
        }
        
        # Should not raise
        validate_and_update(user_settings)
        
        assert 'Message' in user_settings['MODELS']
        assert user_settings['MODELS']['Message'] == 'custom_app.CustomMessage'
    
    def test_valid_serializer_override(self):
        """Test that valid serializer override is accepted"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'SERIALIZERS': {
                'MessageSerializer': 'custom_app.serializers.CustomMessageSerializer'
            }
        }
        
        # Should not raise
        validate_and_update(user_settings)
        
        assert 'MessageSerializer' in user_settings['SERIALIZERS']
    
    def test_invalid_model_key_raises_error(self):
        """Test that invalid model key raises ImproperlyConfigured"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {
                'InvalidModel': 'custom_app.InvalidModel'
            }
        }
        
        with pytest.raises(ImproperlyConfigured):
            validate_and_update(user_settings)
    
    def test_invalid_serializer_key_raises_error(self):
        """Test that invalid serializer key raises ImproperlyConfigured"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'SERIALIZERS': {
                'InvalidSerializer': 'custom_app.InvalidSerializer'
            }
        }
        
        with pytest.raises(ImproperlyConfigured):
            validate_and_update(user_settings)
    
    def test_invalid_top_level_key_raises_error(self):
        """Test that invalid top-level setting key raises ImproperlyConfigured"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'INVALID_SETTING': 'value'
        }
        
        with pytest.raises(ImproperlyConfigured):
            validate_and_update(user_settings)
    
    def test_models_must_be_dict(self):
        """Test that MODELS must be a dictionary"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': ['not', 'a', 'dict']
        }
        
        with pytest.raises(ImproperlyConfigured, match="must be a dictionary"):
            validate_and_update(user_settings)
    
    def test_serializers_must_be_dict(self):
        """Test that SERIALIZERS must be a dictionary"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'SERIALIZERS': 'not a dict'
        }
        
        with pytest.raises(ImproperlyConfigured, match="must be a dictionary"):
            validate_and_update(user_settings)


@pytest.mark.django_db
class TestSettingsMerging:
    """Test that user settings merge with defaults correctly"""
    
    def test_partial_model_override_merges_with_defaults(self):
        """Test that overriding one model preserves defaults for others"""
        from realtime_chat_messaging.conf import validate_and_update
        from realtime_chat_messaging.defaults import DEFAULTS
        
        user_settings = {
            'MODELS': {
                'Message': 'custom_app.CustomMessage'
            }
        }
        
        validate_and_update(user_settings)
        
        # Custom model should be present
        assert user_settings['MODELS']['Message'] == 'custom_app.CustomMessage'
        
        # All default models should still be present
        default_models = DEFAULTS['MODELS']
        for model_name in default_models:
            assert model_name in user_settings['MODELS']
            
            # Only Message should be custom
            if model_name == 'Message':
                assert user_settings['MODELS'][model_name] == 'custom_app.CustomMessage'
            else:
                assert user_settings['MODELS'][model_name] == default_models[model_name]
    
    def test_partial_serializer_override_merges_with_defaults(self):
        """Test that overriding one serializer preserves defaults for others"""
        from realtime_chat_messaging.conf import validate_and_update
        from realtime_chat_messaging.defaults import DEFAULTS
        
        user_settings = {
            'SERIALIZERS': {
                'MessageSerializer': 'custom_app.CustomMessageSerializer'
            }
        }
        
        validate_and_update(user_settings)
        
        # Custom serializer should be present
        assert user_settings['SERIALIZERS']['MessageSerializer'] == 'custom_app.CustomMessageSerializer'
        
        # All default serializers should still be present
        default_serializers = DEFAULTS['SERIALIZERS']
        for serializer_name in default_serializers:
            assert serializer_name in user_settings['SERIALIZERS']
    
    def test_multiple_model_overrides_merge_correctly(self):
        """Test that multiple model overrides work together"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {
                'Message': 'custom_app.CustomMessage',
                'GroupChat': 'custom_app.CustomGroupChat',
                'Session': 'custom_app.CustomSession'
            }
        }
        
        validate_and_update(user_settings)
        
        # All custom models should be present
        assert user_settings['MODELS']['Message'] == 'custom_app.CustomMessage'
        assert user_settings['MODELS']['GroupChat'] == 'custom_app.CustomGroupChat'
        assert user_settings['MODELS']['Session'] == 'custom_app.CustomSession'
        
        # Default models should still be present
        assert 'Room' in user_settings['MODELS']
        assert 'OneToOneChat' in user_settings['MODELS']
    
    def test_empty_models_dict_gets_all_defaults(self):
        """Test that empty MODELS dict gets populated with all defaults"""
        from realtime_chat_messaging.conf import validate_and_update
        from realtime_chat_messaging.defaults import DEFAULTS
        
        user_settings = {
            'MODELS': {}
        }
        
        validate_and_update(user_settings)
        
        # Should have all defaults
        for model_name, model_path in DEFAULTS['MODELS'].items():
            assert user_settings['MODELS'][model_name] == model_path


@pytest.mark.django_db
class TestDjangoSettingsUpdate:
    """Test that validate_and_update updates Django settings"""
    
    def test_django_setting_created_for_message_model(self):
        """Test that REALTIME_CHAT_MESSAGING_MESSAGE_MODEL is created"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {
                'Message': 'custom_app.CustomMessage'
            }
        }
        
        validate_and_update(user_settings)
        
        # Django setting should be created
        assert hasattr(django_settings, 'REALTIME_CHAT_MESSAGING_MESSAGE_MODEL')
        assert django_settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL == 'custom_app.CustomMessage'
    
    def test_django_settings_created_for_all_models(self):
        """Test that Django settings are created for all model overrides"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {
                'Message': 'app.CustomMessage',
                'GroupChat': 'app.CustomGroupChat',
                'Session': 'app.CustomSession'
            }
        }
        
        validate_and_update(user_settings)
        
        # All Django settings should be created
        assert django_settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL == 'app.CustomMessage'
        assert django_settings.REALTIME_CHAT_MESSAGING_GROUPCHAT_MODEL == 'app.CustomGroupChat'
        assert django_settings.REALTIME_CHAT_MESSAGING_SESSION_MODEL == 'app.CustomSession'
    
    def test_django_setting_naming_convention(self):
        """Test that Django settings follow REALTIME_CHAT_MESSAGING_{MODEL}_MODEL pattern"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {
                'OneToOneChat': 'app.CustomOneToOneChat'
            }
        }
        
        validate_and_update(user_settings)
        
        # Should follow naming convention
        assert hasattr(django_settings, 'REALTIME_CHAT_MESSAGING_ONETOONECHAT_MODEL')
        assert django_settings.REALTIME_CHAT_MESSAGING_ONETOONECHAT_MODEL == 'app.CustomOneToOneChat'


@pytest.mark.django_db
class TestSettingsClass:
    """Test the Settings class behavior"""
    
    def test_settings_lazy_loading(self):
        """Test that settings are loaded lazily"""
        from realtime_chat_messaging.conf import Settings
        
        settings = Settings()
        
        # user_settings should be None initially
        assert settings._user_settings is None
        
        # Accessing user_settings should load them
        _ = settings.user_settings
        
        # Now should be loaded
        assert settings._user_settings is not None
    
    def test_settings_reload(self):
        """Test that reload clears cached settings"""
        from realtime_chat_messaging.conf import Settings
        
        settings = Settings()
        
        # Load settings
        _ = settings.user_settings
        assert settings._user_settings is not None
        
        # Reload
        settings.reload()
        
        # Should be cleared
        assert settings._user_settings is None
    
    def test_settings_getattr_returns_defaults(self):
        """Test that accessing settings returns defaults"""
        from realtime_chat_messaging.conf import realtime_chat_settings
        from realtime_chat_messaging.defaults import DEFAULTS
        
        # Should return defaults
        assert realtime_chat_settings.MESSAGE_SOFT_DELETE == DEFAULTS['MESSAGE_SOFT_DELETE']
        assert realtime_chat_settings.ENABLE_NOTIFICATION == DEFAULTS['ENABLE_NOTIFICATION']
        assert realtime_chat_settings.INACTIVITY_THRESHOLD == DEFAULTS['INACTIVITY_THRESHOLD']
    
    def test_settings_getattr_invalid_key_raises(self):
        """Test that accessing invalid setting raises AttributeError"""
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        with pytest.raises(AttributeError, match="Invalid setting"):
            _ = realtime_chat_settings.INVALID_SETTING
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MESSAGE_SOFT_DELETE': True,
            'ENABLE_NOTIFICATION': False
        }
    )
    def test_settings_override_respected(self):
        """Test that Django settings override are respected"""
        from realtime_chat_messaging.conf import Settings
        
        # Create new instance to reload settings
        settings = Settings()
        settings.reload()
        
        # Should use overridden values
        assert settings.MESSAGE_SOFT_DELETE is True
        assert settings.ENABLE_NOTIFICATION is False


@pytest.mark.django_db
class TestSettingsValidationEdgeCases:
    """Test edge cases in settings validation"""
    
    def test_empty_settings_dict(self):
        """Test that empty settings dict is valid"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {}
        
        # Should not raise
        validate_and_update(user_settings)
    
    def test_none_settings_handled_gracefully(self):
        """Test that None in settings doesn't break validation"""
        from realtime_chat_messaging.conf import Settings
        
        # Should handle gracefully
        settings = Settings()
        _ = settings.user_settings  # Should not raise
    
    def test_mixed_valid_and_invalid_keys_raises(self):
        """Test that mix of valid and invalid keys raises error"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'MODELS': {'Message': 'app.CustomMessage'},  # Valid
            'INVALID_KEY': 'value'  # Invalid
        }
        
        with pytest.raises(ImproperlyConfigured):
            validate_and_update(user_settings)
    
    def test_valid_handler_settings(self):
        """Test that valid handler settings are accepted"""
        from realtime_chat_messaging.conf import validate_and_update
        
        user_settings = {
            'EVENT_HANDLER_CLASS': 'custom_app.CustomEventHandler',
            'PERMISSION_HANDLER_CLASS': 'custom_app.CustomPermissionHandler',
            'EXCEPTION_HANDLER_CLASS': 'custom_app.CustomExceptionHandler',
            'EVENT_MAPPER': 'custom_app.custom_event_mapper'
        }
        
        # Should not raise
        validate_and_update(user_settings)
        
        assert user_settings['EVENT_HANDLER_CLASS'] == 'custom_app.CustomEventHandler'
        assert user_settings['PERMISSION_HANDLER_CLASS'] == 'custom_app.CustomPermissionHandler'


@pytest.mark.django_db  
class TestSettingsReload:
    """Test settings reload behavior"""
    
    def test_settings_reload_on_django_setting_change(self):
        """Test that settings reload when Django setting changes"""
        from realtime_chat_messaging.conf import realtime_chat_settings
        from django.test.signals import setting_changed
        
        # Get initial value
        initial_soft_delete = realtime_chat_settings.MESSAGE_SOFT_DELETE
        
        # Trigger setting change
        setting_changed.send(
            sender=None,
            setting='REALTIME_CHAT_MESSAGING',
            value={'MESSAGE_SOFT_DELETE': not initial_soft_delete},
            enter=True
        )
        
        # Settings should be reloaded (internal state cleared)
        assert realtime_chat_settings._user_settings == {}
    
    def test_reload_only_on_correct_setting(self):
        """Test that reload only happens for REALTIME_CHAT_MESSAGING setting"""
        from realtime_chat_messaging.conf import realtime_chat_settings
        from django.test.signals import setting_changed
        
        # Load settings
        _ = realtime_chat_settings.user_settings
        assert realtime_chat_settings._user_settings is not None
        
        # Trigger change for different setting
        setting_changed.send(
            sender=None,
            setting='SOME_OTHER_SETTING',
            value='value',
            enter=True
        )
        
        # Should NOT reload
        assert realtime_chat_settings._user_settings is not None


@pytest.mark.django_db
class TestSettingsIntegration:
    """Test settings integration with the rest of the system"""
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MODELS': {
                'Message': 'custom_implementation_test_app.CustomMessage'
            }
        }
    )
    def test_custom_model_setting_loads_in_get_model(self):
        """Test that custom model setting is used by get_model"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches
        from custom_implementation_test_app.models import CustomMessage
        
        # Clear caches to force reload
        clear_caches()
        
        # Reload settings
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        # get_model should return CustomMessage
        Message = get_model('Message')
        
        assert Message == CustomMessage
        assert hasattr(Message, 'priority')  # Custom field
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'SERIALIZERS': {
                'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer'
            }
        }
    )
    def test_custom_serializer_setting_loads_in_get_serializer(self):
        """Test that custom serializer setting is used by get_serializer"""
        from realtime_chat_messaging.utils.loader import get_serializer, clear_caches
        from custom_implementation_test_app.serializers import CustomMessageSerializer
        
        # Clear caches
        clear_caches()
        
        # Reload settings
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        # get_serializer should return CustomMessageSerializer
        MessageSerializer = get_serializer('MessageSerializer')
        
        assert MessageSerializer == CustomMessageSerializer


@pytest.mark.django_db
class TestDefaultSettings:
    """Test that default settings are correct"""
    
    def test_default_models_exist(self):
        """Test that all default models are defined"""
        from realtime_chat_messaging.defaults import DEFAULTS
        
        expected_models = [
            'Session', 'Room', 'RoomProperty', 'OneToOneChat', 
            'GroupChat', 'Channel', 'Message', 'MessageMediaAsset',
            'ReadReceipt', 'ChatNotification', 'Reaction'
        ]
        
        for model_name in expected_models:
            assert model_name in DEFAULTS['MODELS']
            assert isinstance(DEFAULTS['MODELS'][model_name], str)
            assert '.' in DEFAULTS['MODELS'][model_name]  # Should be a path
    
    def test_default_serializers_exist(self):
        """Test that all default serializers are defined"""
        from realtime_chat_messaging.defaults import DEFAULTS
        
        expected_serializers = [
            'RoomListPolymorphicSerializer', 'RoomPolymorphicSerializer',
            'RoomPropertySerializer', 'ReactionSerializer',
            'MessageMediaAssetSerializer', 'MessageSerializer',
            'ChatNotificationSerializer', 'UserSerializer',
            'OneToOneChatListSerializer', 'GroupChatListSerializer',
            'ChannelListSerializer', 'OneToOneChatSerializer',
            'GroupChatSerializer', 'ChannelSerializer',
            'ReadReceiptSerializer'
        ]
        
        for serializer_name in expected_serializers:
            assert serializer_name in DEFAULTS['SERIALIZERS']
            assert isinstance(DEFAULTS['SERIALIZERS'][serializer_name], str)
    
    def test_default_handler_classes_exist(self):
        """Test that default handler classes are defined"""
        from realtime_chat_messaging.defaults import DEFAULTS
        
        assert 'PERMISSION_HANDLER_CLASS' in DEFAULTS
        assert 'EVENT_MAPPER' in DEFAULTS
        assert 'EVENT_HANDLER_CLASS' in DEFAULTS
        assert 'EXCEPTION_HANDLER_CLASS' in DEFAULTS
    
    def test_default_boolean_settings(self):
        """Test that default boolean settings are defined"""
        from realtime_chat_messaging.defaults import DEFAULTS
        
        assert 'MESSAGE_SOFT_DELETE' in DEFAULTS
        assert isinstance(DEFAULTS['MESSAGE_SOFT_DELETE'], bool)
        
        assert 'ENABLE_NOTIFICATION' in DEFAULTS
        assert isinstance(DEFAULTS['ENABLE_NOTIFICATION'], bool)
    
    def test_default_inactivity_threshold(self):
        """Test that INACTIVITY_THRESHOLD has sensible default"""
        from realtime_chat_messaging.defaults import DEFAULTS
        
        assert 'INACTIVITY_THRESHOLD' in DEFAULTS
        assert isinstance(DEFAULTS['INACTIVITY_THRESHOLD'], int)
        assert DEFAULTS['INACTIVITY_THRESHOLD'] > 0  # Should be positive
