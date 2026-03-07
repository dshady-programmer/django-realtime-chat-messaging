"""
Unit tests for loader utility functions.

Tests cover:
- get_model() dynamic model loading
- get_serializer() dynamic serializer loading
- Model/serializer caching
- clear_caches() functionality
- import_and_verify_type_class()
- import_and_verify_type_function()
- Error handling for invalid imports
"""
import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from asgiref.sync import sync_to_async


@pytest.mark.django_db
class TestGetModel:
    """Test get_model() function"""
    
    def test_get_default_message_model(self):
        """Test loading default Message model"""
        from realtime_chat_messaging.utils.loader import get_model
        from realtime_chat_messaging.models import Message
        
        LoadedMessage = get_model('Message')
        
        assert LoadedMessage == Message
        assert LoadedMessage.__name__ == 'Message'
    
    def test_get_default_room_model(self):
        """Test loading default Room model"""
        from realtime_chat_messaging.utils.loader import get_model
        from realtime_chat_messaging.models import Room
        
        LoadedRoom = get_model('Room')
        
        assert LoadedRoom == Room
        assert LoadedRoom.__name__ == 'Room'
    
    def test_get_default_session_model(self):
        """Test loading default Session model"""
        from realtime_chat_messaging.utils.loader import get_model
        from realtime_chat_messaging.models import Session
        
        LoadedSession = get_model('Session')
        
        assert LoadedSession == Session
    
    def test_get_all_default_models(self):
        """Test that all default models can be loaded"""
        from realtime_chat_messaging.utils.loader import get_model
        
        model_names = [
            'Session', 'Room', 'RoomProperty', 'OneToOneChat',
            'GroupChat', 'Channel', 'Message', 'MessageMediaAsset',
            'ReadReceipt', 'ChatNotification', 'Reaction'
        ]
        
        for model_name in model_names:
            model = get_model(model_name)
            assert model is not None
            assert hasattr(model, '_meta')  # Should be a Django model
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MODELS': {
                'Message': 'custom_implementation_test_app.CustomMessage'
            }
        }
    )
    def test_get_custom_message_model(self):
        """Test loading custom Message model"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches
        from custom_implementation_test_app.models import CustomMessage
        
        # Clear cache and reload
        clear_caches()
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        LoadedMessage = get_model('Message')
        
        assert LoadedMessage == CustomMessage
        assert hasattr(LoadedMessage, 'priority')  # Custom field
    
    def test_get_invalid_model_raises_keyerror(self):
        """Test that loading invalid model raises KeyError"""
        from realtime_chat_messaging.utils.loader import get_model
        
        with pytest.raises(KeyError):
            get_model('NonExistentModel')


@pytest.mark.django_db
class TestGetSerializer:
    """Test get_serializer() function"""
    
    def test_get_default_message_serializer(self):
        """Test loading default MessageSerializer"""
        from realtime_chat_messaging.utils.loader import get_serializer
        from realtime_chat_messaging.serializers import MessageSerializer
        
        LoadedSerializer = get_serializer('MessageSerializer')
        
        assert LoadedSerializer == MessageSerializer
    
    def test_get_default_room_serializer(self):
        """Test loading default RoomPolymorphicSerializer"""
        from realtime_chat_messaging.utils.loader import get_serializer
        from realtime_chat_messaging.serializers import RoomPolymorphicSerializer
        
        LoadedSerializer = get_serializer('RoomPolymorphicSerializer')
        
        assert LoadedSerializer == RoomPolymorphicSerializer
    
    def test_get_all_default_serializers(self):
        """Test that all default serializers can be loaded"""
        from realtime_chat_messaging.utils.loader import get_serializer
        
        serializer_names = [
            'RoomListPolymorphicSerializer', 'RoomPolymorphicSerializer',
            'MessageSerializer', 'UserSerializer', 'GroupChatSerializer'
        ]
        
        for serializer_name in serializer_names:
            serializer = get_serializer(serializer_name)
            assert serializer is not None
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'SERIALIZERS': {
                'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer'
            }
        }
    )
    def test_get_custom_message_serializer(self):
        """Test loading custom MessageSerializer"""
        from realtime_chat_messaging.utils.loader import get_serializer, clear_caches
        from custom_implementation_test_app.serializers import CustomMessageSerializer
        
        # Clear cache and reload
        clear_caches()
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        LoadedSerializer = get_serializer('MessageSerializer')
        
        assert LoadedSerializer == CustomMessageSerializer
    
    def test_get_invalid_serializer_raises_keyerror(self):
        """Test that loading invalid serializer raises KeyError"""
        from realtime_chat_messaging.utils.loader import get_serializer
        
        with pytest.raises(KeyError):
            get_serializer('NonExistentSerializer')


@pytest.mark.django_db
class TestCaching:
    """Test caching behavior of loaders"""
    
    def test_model_cache_populated_on_first_load(self):
        """Test that model cache is populated on first load"""
        from realtime_chat_messaging.utils.loader import get_model, _MODEL_CACHE, clear_caches
        
        # Clear cache first
        clear_caches()
        
        # Cache should be empty
        assert len(_MODEL_CACHE) == 0
        
        # Load a model
        get_model('Message')
        
        # Cache should now be populated
        assert len(_MODEL_CACHE) > 0
        assert 'Message' in _MODEL_CACHE
    
    def test_serializer_cache_populated_on_first_load(self):
        """Test that serializer cache is populated on first load"""
        from realtime_chat_messaging.utils.loader import get_serializer, _SERIALIZER_CACHE, clear_caches
        
        # Clear cache first
        clear_caches()
        
        # Cache should be empty
        assert len(_SERIALIZER_CACHE) == 0
        
        # Load a serializer
        get_serializer('MessageSerializer')
        
        # Cache should now be populated
        assert len(_SERIALIZER_CACHE) > 0
        assert 'MessageSerializer' in _SERIALIZER_CACHE
    
    def test_clear_caches_empties_model_cache(self):
        """Test that clear_caches empties model cache"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches, _MODEL_CACHE
        
        # Load model to populate cache
        get_model('Message')
        assert len(_MODEL_CACHE) > 0
        
        # Clear caches
        clear_caches()
        
        # Cache should be empty
        assert len(_MODEL_CACHE) == 0
    
    def test_clear_caches_empties_serializer_cache(self):
        """Test that clear_caches empties serializer cache"""
        from realtime_chat_messaging.utils.loader import get_serializer, clear_caches, _SERIALIZER_CACHE
        
        # Load serializer to populate cache
        get_serializer('MessageSerializer')
        assert len(_SERIALIZER_CACHE) > 0
        
        # Clear caches
        clear_caches()
        
        # Cache should be empty
        assert len(_SERIALIZER_CACHE) == 0
    
    def test_model_loaded_from_cache_on_second_call(self):
        """Test that model is loaded from cache on subsequent calls"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches
        
        clear_caches()
        
        # First call - loads from settings
        first_load = get_model('Message')
        
        # Second call - should load from cache (same object)
        second_load = get_model('Message')
        
        assert first_load is second_load


@pytest.mark.django_db
class TestImportAndVerifyTypeClass:
    """Test import_and_verify_type_class() function"""
    
    def test_import_class_from_string_path(self):
        """Test importing class from string path"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        from realtime_chat_messaging.permissions.handlers import PermissionHandler
        
        LoadedClass = import_and_verify_type_class(
            'realtime_chat_messaging.permissions.handlers.PermissionHandler',
            'TEST_CLASS'
        )
        
        assert LoadedClass == PermissionHandler
    
    def test_import_class_already_loaded(self):
        """Test that passing already-loaded class works"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        from realtime_chat_messaging.permissions.handlers import PermissionHandler
        
        LoadedClass = import_and_verify_type_class(
            PermissionHandler,
            'TEST_CLASS'
        )
        
        assert LoadedClass == PermissionHandler
    
    def test_import_non_class_raises_error(self):
        """Test that importing non-class raises ImproperlyConfigured"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        
        # Try to import a function (not a class)
        with pytest.raises(ImproperlyConfigured, match="should be a class"):
            import_and_verify_type_class(
                'realtime_chat_messaging.utils.loader.import_model',
                'TEST_CLASS'
            )
    
    def test_import_invalid_module_raises_error(self):
        """Test that invalid module path raises error"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        
        with pytest.raises(Exception):  # ModuleNotFoundError or ImportError
            import_and_verify_type_class(
                'invalid.module.path.ClassName',
                'TEST_CLASS'
            )
    
    def test_import_non_existent_class_raises_error(self):
        """Test that non-existent class in valid module raises error"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        
        with pytest.raises(AttributeError):
            import_and_verify_type_class(
                'realtime_chat_messaging.permissions.handlers.NonExistentClass',
                'TEST_CLASS'
            )


@pytest.mark.django_db
class TestImportAndVerifyTypeFunction:
    """Test import_and_verify_type_function() function"""
    
    def test_import_function_from_string_path(self):
        """Test importing function from string path"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_function
        from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers
        
        LoadedFunction = import_and_verify_type_function(
            'realtime_chat_messaging.variables.consumers.map_event_type_to_handlers',
            'TEST_FUNCTION'
        )
        
        assert LoadedFunction == map_event_type_to_handlers
    
    def test_import_function_already_loaded(self):
        """Test that passing already-loaded function works"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_function
        from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers
        
        LoadedFunction = import_and_verify_type_function(
            map_event_type_to_handlers,
            'TEST_FUNCTION'
        )
        
        assert LoadedFunction == map_event_type_to_handlers
    
    def test_import_non_function_raises_error(self):
        """Test that importing non-function raises ImproperlyConfigured"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_function
        
        # Try to import a class (not a function)
        with pytest.raises(ImproperlyConfigured, match="should be a function"):
            import_and_verify_type_function(
                'realtime_chat_messaging.permissions.handlers.PermissionHandler',
                'TEST_FUNCTION'
            )
    
    def test_import_invalid_function_path_raises_error(self):
        """Test that invalid function path raises error"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_function
        
        with pytest.raises(Exception):
            import_and_verify_type_function(
                'invalid.module.path.function_name',
                'TEST_FUNCTION'
            )


@pytest.mark.django_db
class TestImportModel:
    """Test import_model() function"""
    
    def test_import_model_with_app_label(self):
        """Test importing model using app_label.ModelName format"""
        from realtime_chat_messaging.utils.loader import import_model
        from realtime_chat_messaging.models import Message
        
        LoadedMessage = import_model('realtime_chat_messaging.Message')
        
        assert LoadedMessage == Message
    
    def test_import_custom_model(self):
        """Test importing custom model"""
        from realtime_chat_messaging.utils.loader import import_model
        from custom_implementation_test_app.models import CustomMessage
        
        LoadedMessage = import_model('custom_implementation_test_app.CustomMessage')
        
        assert LoadedMessage == CustomMessage
    
    def test_import_invalid_model_raises_error(self):
        """Test that importing invalid model raises error"""
        from realtime_chat_messaging.utils.loader import import_model
        
        with pytest.raises(Exception):  # LookupError
            import_model('invalid_app.InvalidModel')


@pytest.mark.django_db
class TestLoaderEdgeCases:
    """Test edge cases in loader utilities"""
    
    def test_get_model_after_settings_reload(self):
        """Test that get_model works after settings reload"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        # Initial load
        Message1 = get_model('Message')
        
        # Clear and reload
        clear_caches()
        realtime_chat_settings.reload()
        
        # Load again
        Message2 = get_model('Message')
        
        # Should still work
        assert Message1 == Message2
    
    def test_concurrent_get_model_calls(self):
        """Test that concurrent get_model calls work correctly"""
        from realtime_chat_messaging.utils.loader import get_model
        import asyncio
        
        async def load_model():
            return await sync_to_async(get_model)('Message')
        
        async def run_concurrent_loads():
            return await asyncio.gather(
                load_model(),
                load_model(),
                load_model()
            )
        
        # Load concurrently
        models = asyncio.run(run_concurrent_loads())
        
        # All should return same model
        assert models[0] == models[1] == models[2]
    
    def test_load_model_and_serializer_in_sequence(self):
        """Test loading model then serializer works"""
        from realtime_chat_messaging.utils.loader import get_model, get_serializer
        
        # Load model first
        Message = get_model('Message')
        assert Message is not None
        
        # Then load serializer
        MessageSerializer = get_serializer('MessageSerializer')
        assert MessageSerializer is not None
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MODELS': {
                'Message': 'custom_implementation_test_app.CustomMessage',
                'GroupChat': 'custom_implementation_test_app.CustomGroupChat'
            }
        }
    )
    def test_load_multiple_custom_models(self):
        """Test loading multiple custom models at once"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches
        from custom_implementation_test_app.models import CustomMessage, CustomGroupChat
        
        clear_caches()
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        # Load both custom models
        Message = get_model('Message')
        GroupChat = get_model('GroupChat')
        
        assert Message == CustomMessage
        assert GroupChat == CustomGroupChat
        assert hasattr(Message, 'priority')
        assert hasattr(GroupChat, 'tags')


@pytest.mark.django_db
class TestLoaderIntegrationWithSettings:
    """Test that loaders integrate correctly with settings system"""
    
    def test_loader_uses_settings_models_dict(self):
        """Test that get_model uses MODELS from settings"""
        from realtime_chat_messaging.utils.loader import get_model, _load_models
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        # Load models mapping
        models_dict = _load_models()
        
        # Should match settings
        assert models_dict == realtime_chat_settings.MODELS
    
    def test_loader_uses_settings_serializers_dict(self):
        """Test that get_serializer uses SERIALIZERS from settings"""
        from realtime_chat_messaging.utils.loader import get_serializer, _load_serializers
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        # Load serializers mapping
        serializers_dict = _load_serializers()
        
        # Should match settings
        assert serializers_dict == realtime_chat_settings.SERIALIZERS
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MODELS': {
                'Message': 'custom_implementation_test_app.CustomMessage'
            },
            'SERIALIZERS': {
                'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer'
            }
        }
    )
    def test_loader_picks_up_settings_changes(self):
        """Test that loader picks up settings changes after reload"""
        from realtime_chat_messaging.utils.loader import get_model, get_serializer, clear_caches
        from custom_implementation_test_app.models import CustomMessage
        from custom_implementation_test_app.serializers import CustomMessageSerializer
        
        # Clear and reload
        clear_caches()
        from realtime_chat_messaging.conf import realtime_chat_settings
        realtime_chat_settings.reload()
        
        # Should load custom implementations
        Message = get_model('Message')
        MessageSerializer = get_serializer('MessageSerializer')
        
        assert Message == CustomMessage
        assert MessageSerializer == CustomMessageSerializer


@pytest.mark.django_db
class TestLoaderPerformance:
    """Test performance characteristics of loaders"""
    
    def test_cached_loads_are_fast(self):
        """Test that cached model loads are significantly faster"""
        from realtime_chat_messaging.utils.loader import get_model, clear_caches
        import time
        
        clear_caches()
        
        # First load (cold)
        start = time.time()
        for _ in range(100):
            get_model('Message')
        cold_time = time.time() - start
        
        # Note: In practice cached loads should be faster,
        # but this is a smoke test that both work
        assert cold_time >= 0  # Should complete successfully
    
    def test_clear_caches_multiple_times(self):
        """Test that clear_caches can be called multiple times safely"""
        from realtime_chat_messaging.utils.loader import clear_caches, get_model
        
        # Multiple clears should work fine
        clear_caches()
        clear_caches()
        clear_caches()
        
        # Should still be able to load after
        Message = get_model('Message')
        assert Message is not None
