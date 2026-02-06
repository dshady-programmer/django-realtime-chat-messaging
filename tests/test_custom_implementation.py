"""
Tests for custom model, serializer, handler, and permission implementations.
This tests the dynamic loading system and ensures swappable components work correctly.
"""
import pytest
from django.test import override_settings

from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from realtime_chat_messaging.consumers import ChatMessagingConsumer
from django.contrib.auth import get_user_model


from realtime_chat_messaging.permissions.handlers import PermissionHandler
from realtime_chat_messaging.model_mixins import (
    AbstractMessage, AbstractGroupChat, AbstractSession
)

User = get_user_model()

from custom_implementation_test_app.models import CustomGroupChat, CustomMessage, CustomSession
from custom_implementation_test_app.serializers import CustomMessageSerializer
from custom_implementation_test_app.permissions import CustomPermissionHandler
from custom_implementation_test_app.handlers import CustomEventHandler






# ==================== TESTS ====================

@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(5)


@pytest.mark.django_db
class TestCustomModelLoading:
    """Test that custom models can be loaded and used"""
    
    def test_custom_model_registration(self):
        """Test that custom models are registered in Django"""
        from django.apps import apps
        
        # Check if custom models are registered
        # Note: This test assumes you've added these to a test app
        assert CustomMessage is not None
        assert CustomGroupChat is not None
        assert CustomSession is not None
    
    def test_custom_model_has_additional_fields(self):
        """Test that custom models have additional fields"""
        # CustomMessage
        assert hasattr(CustomMessage, 'priority')
        assert hasattr(CustomMessage, 'metadata')
        

        
        # CustomGroupChat
        assert hasattr(CustomGroupChat, 'tags')
        
        # CustomSession
        assert hasattr(CustomSession, 'device_type')
        assert hasattr(CustomSession, 'ip_address')
    
    def test_custom_model_inherits_from_abstract(self):
        """Test that custom models properly inherit from abstract models"""
        assert issubclass(CustomMessage, AbstractMessage)
        assert issubclass(CustomGroupChat, AbstractGroupChat)
        assert issubclass(CustomSession, AbstractSession)
    
    def test_custom_model_swappable_attribute(self):
        """Test that custom models have swappable meta attribute"""
        assert hasattr(CustomMessage._meta, 'swappable')
        assert hasattr(CustomGroupChat._meta, 'swappable')
        assert hasattr(CustomSession._meta, 'swappable')


@pytest.mark.django_db
class TestModelSwapping:
    """Test dynamic model loading with get_model"""
    
    def test_default_model_loading(self):
        """Test that default models load correctly"""
        from realtime_chat_messaging.utils.loader import get_model
        
        Message = get_model("Message")
        Room = get_model("Room")
        GroupChat = get_model("GroupChat")
        
        assert Message is not None
        assert Room is not None
        assert GroupChat is not None
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MODELS': {
                'Message': 'custom_implementation_test_app.CustomMessage',
            }
        }
    )
    def test_custom_message_model_loading(self):
        """Test loading custom Message model"""
        from realtime_chat_messaging.utils.loader import get_model
        Message = get_model("Message")
        # Should load CustomMessage
        assert Message == CustomMessage
        assert hasattr(Message, 'priority')
        assert hasattr(Message, 'metadata')



@pytest.mark.django_db
class TestSerializerSwapping:
    """Test dynamic serializer loading with get_serializer"""
    
    def test_default_serializer_loading(self):
        """Test that default serializers load correctly"""
        from realtime_chat_messaging.utils.loader import get_serializer
        
        MessageSerializer = get_serializer("MessageSerializer")
        GroupChatSerializer = get_serializer("GroupChatSerializer")
        
        assert MessageSerializer is not None
        assert GroupChatSerializer is not None
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'SERIALIZERS': {
                'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer',
            }
        }
    )
    def test_custom_serializer_loading(self):
        """Test loading custom serializer"""


        from realtime_chat_messaging.utils.loader import get_serializer
        
        MessageSerializer = get_serializer("MessageSerializer")
        
        # Should load CustomMessageSerializer
        assert MessageSerializer == CustomMessageSerializer
    


@pytest.mark.django_db
class TestHandlerSwapping:
    """Test dynamic handler loading"""
    
    def test_default_handler_loading(self):
        """Test that default event handler loads"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        HandlerClass = import_and_verify_type_class(
            realtime_chat_settings.EVENT_HANDLER_CLASS,
            "EVENT_HANDLER_CLASS"
        )
        
        handler = HandlerClass()
        assert hasattr(handler, 'create_message')
        assert hasattr(handler, 'create_room')
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'EVENT_HANDLER_CLASS': 'tests.test_custom_implementation.CustomEventHandler'
        }
    )
    def test_custom_handler_loading(self):
        """Test loading custom event handler"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        
        HandlerClass = import_and_verify_type_class(
            realtime_chat_settings.EVENT_HANDLER_CLASS,
            "EVENT_HANDLER_CLASS"
        )
       
        
        handler = HandlerClass()
        assert handler is not None
        assert hasattr(handler, 'create_message')
        
        
        
    
    def test_handler_has_required_methods(self):
        """Test that handler implements required interface"""
        handler = CustomEventHandler()
        
        required_methods = [
            '_create_message', '_create_room', '_list_rooms',
            '_retreive_room', '_add_members_to_room', '_remove_members_from_room',
            '_leave_room', '_join_room', '_modify_room'
        ]
        
        for method in required_methods:
            assert hasattr(handler, method)


@pytest.mark.django_db  
class TestPermissionHandlerSwapping:
    """Test dynamic permission handler loading"""
    
    def test_default_permission_handler(self):
        """Test default permission handler"""
        handler = PermissionHandler()
        assert handler is not None
        assert hasattr(handler, 'have_room_permission')
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'PERMISSION_HANDLER_CLASS': 'tests.test_custom_implementation.CustomPermissionHandler'
        }
    )
    def test_custom_permission_handler_loading(self):
        """Test loading custom permission handler"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        
        HandlerClass = import_and_verify_type_class(
            realtime_chat_settings.PERMISSION_HANDLER_CLASS,
            "PERMISSION_HANDLER_CLASS"
        )
        
        handler = HandlerClass()
        assert handler is not None
        assert hasattr(handler, 'have_room_permission')
        
        
        
    
    @pytest.mark.asyncio
    async def test_custom_permission_handler_logic(self, users, create_one_to_one_chat):
        """Test that custom permission logic works"""
        from realtime_chat_messaging.models import Room
        
        # Create a room
        chat = await database_sync_to_async(create_one_to_one_chat)(users[0], users[1])
        
        # Test with custom handler
        handler = CustomPermissionHandler()
        has_perm, room = await handler.have_room_permission(users[0], str(chat.id))
        
        assert has_perm is True
        assert room.id == chat.id


@pytest.mark.django_db
class TestEventMapperSwapping:
    """Test custom event mapper functionality"""
    
    def test_default_event_mapper(self):
        """Test that default event mapper works"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_function
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        mapper_func = import_and_verify_type_function(
            realtime_chat_settings.EVENT_MAPPER,
            "EVENT_MAPPER"
        )
        
        assert mapper_func is not None
        assert callable(mapper_func)
    
    def test_event_mapper_returns_dict(self):
        """Test that event mapper returns a dictionary"""
        from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers
        from realtime_chat_messaging.consumers import ChatMessagingConsumer

        consumer = ChatMessagingConsumer()
        mapping = map_event_type_to_handlers(consumer)
        
        assert isinstance(mapping, dict)
        assert len(mapping) > 0


@pytest.mark.django_db
class TestExceptionHandlerSwapping:
    """Test custom exception handler functionality"""
    
    def test_default_exception_handler(self):
        """Test default exception handler"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        from realtime_chat_messaging.conf import realtime_chat_settings
        
        HandlerClass = import_and_verify_type_class(
            realtime_chat_settings.EXCEPTION_HANDLER_CLASS,
            "EXCEPTION_HANDLER_CLASS"
        )
        
        assert HandlerClass is not None
        assert hasattr(HandlerClass, 'exception_handler_decorator')
    
    @pytest.mark.asyncio
    async def test_exception_handler_catches_errors(self, users):
        """Test that exception handler properly catches errors in consumers"""
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = users[0]
        
        await communicator.connect()
        await communicator.receive_json_from()
        
        # Trigger an error
        await communicator.send_json_to({
            'event_type': 'room.info',
            'data': {
                'room_id': 'definitely-not-a-valid-uuid'
            }
        })
        
        response = await communicator.receive_json_from()
        
        # Should receive formatted error response
        assert 'error' in response
        assert 'code' in response['error']
        assert 'detail' in response['error']
        
        await communicator.disconnect()


@pytest.mark.django_db
class TestLoaderUtilities:
    """Test loader utility functions"""
    
    def test_import_and_verify_type_class(self):
        """Test import_and_verify_type_class utility"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        
        # Valid class import
        PermHandler = import_and_verify_type_class(
            "realtime_chat_messaging.permissions.handlers.PermissionHandler",
            "PERMISSION_HANDLER_CLASS"
        )
        
        assert PermHandler is not None
        assert PermHandler == PermissionHandler
    
    def test_import_and_verify_type_function(self):
        """Test import_and_verify_type_function utility"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_function
        
        # Valid function import
        mapper = import_and_verify_type_function(
            "realtime_chat_messaging.variables.consumers.map_event_type_to_handlers",
            "EVENT_MAPPER"
        )
        
        assert mapper is not None
        assert callable(mapper)
    
    def test_import_invalid_path_raises_error(self):
        """Test that invalid import paths raise appropriate errors"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        
        with pytest.raises(Exception):
            import_and_verify_type_class(
                "invalid.module.path.ClassName",
                "TEST_CLASS"
            )
    
    def test_import_non_existent_attribute_raises_error(self):
        """Test that non-existent attributes raise errors"""
        from realtime_chat_messaging.utils.loader import import_and_verify_type_class
        
        with pytest.raises(Exception):
            import_and_verify_type_class(
                "realtime_chat_messaging.permissions.handlers.NonExistentClass",
                "TEST_CLASS"
            )

    



@pytest.mark.django_db
class TestPartialOverrides:
    """Test that partial setting overrides merge with defaults"""
    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'MODELS': {
                'Message': 'custom_implementation_test_app.CustomMessage',
                # Other models should use defaults
            }
        }
    )
    def test_partial_model_override(self):
        """Test that overriding one model doesn't affect others"""
        from realtime_chat_messaging.utils.loader import get_model
        
        # Custom model
        Message = get_model("Message")
        
        # Default models should still work
        Room = get_model("Room")
        GroupChat = get_model("GroupChat")
        
        assert Message == CustomMessage
        assert Room.__name__ == 'Room'
        assert GroupChat.__name__ == 'GroupChat'
        
        
        

    
    @override_settings(
        REALTIME_CHAT_MESSAGING={
            'SERIALIZERS': {
                'MessageSerializer': 'custom_implementation_test_app.serializers.CustomMessageSerializer',
                # Other serializers should use defaults
            }
        }
    )
    def test_partial_serializer_override(self):
        """Test that overriding one serializer doesn't affect others"""
       
        from realtime_chat_messaging.utils.loader import get_serializer
        # Custom serializer
        MessageSer = get_serializer("MessageSerializer")

        
        # Default serializers should still work
        RoomSer = get_serializer("RoomPolymorphicSerializer")
        
        assert MessageSer == CustomMessageSerializer
        assert RoomSer.__name__ == 'RoomPolymorphicSerializer'
        
        
        



@pytest.mark.django_db
class TestValidateAndUpdate:
    """Test validate_and_update function"""
    
    def test_validate_merges_serializers_with_defaults(self):
        """Test that SERIALIZERS are merged with defaults"""
        from realtime_chat_messaging.conf import validate_and_update
        from realtime_chat_messaging.defaults import DEFAULTS
        
        user_settings = {
            'SERIALIZERS': {
                'MessageSerializer': 'custom.MessageSerializer'
            }
        }
        
        validate_and_update(user_settings)
        
        # Should have custom + all defaults
        assert 'MessageSerializer' in user_settings['SERIALIZERS']
        assert user_settings['SERIALIZERS']['MessageSerializer'] == 'custom.MessageSerializer'
        
        # Should have other defaults
        default_serializers = DEFAULTS['SERIALIZERS']
        for key in default_serializers:
            if key != 'MessageSerializer':
                assert key in user_settings['SERIALIZERS']
    
    def test_validate_merges_models_with_defaults(self):
        """Test that MODELS are merged with defaults"""
        from realtime_chat_messaging.conf import validate_and_update
        from realtime_chat_messaging.defaults import DEFAULTS
        
        user_settings = {
            'MODELS': {
                'Message': 'custom.Message'
            }
        }
        
        validate_and_update(user_settings)
        
        # Should have custom + all defaults
        assert 'Message' in user_settings['MODELS']
        assert user_settings['MODELS']['Message'] == 'custom.Message'
        
        # Should have other defaults
        default_models = DEFAULTS['MODELS']
        for key in default_models:
            if key != 'Message':
                assert key in user_settings['MODELS']
    
    def test_validate_updates_django_settings(self):
        """Test that validate_and_update updates Django settings"""
        from realtime_chat_messaging.conf import validate_and_update
        from django.conf import settings
        
        user_settings = {
            'MODELS': {
                'Message': 'custom.Message'
            }
        }
        
        validate_and_update(user_settings)
        
        # Should set Django setting
        assert hasattr(settings, 'REALTIME_CHAT_MESSAGING_MESSAGE_MODEL')
        assert settings.REALTIME_CHAT_MESSAGING_MESSAGE_MODEL == 'custom.Message'