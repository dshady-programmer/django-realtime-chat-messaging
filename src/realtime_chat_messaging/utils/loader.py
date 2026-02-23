"""
Dynamic loading utilities for configurable models and serializers.

This module provides runtime import and validation mechanisms that enable
the chat messaging system to work with custom user-defined models and
serializers. It supports lazy loading, type validation, and caching.

The loader system allows projects to override default implementations by
specifying custom classes in settings, making the package highly extensible
and adaptable to different project requirements.
"""




import importlib
import inspect
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from channels.db import database_sync_to_async
from django.apps import apps
from django.db import models

def import_and_verify_type_class(klass, klass_repr, class_instance=None):

    """
        Dynamically import and validate a class from a string path or object.

        This function accepts either a class object or a dotted import path string,
        imports the class if necessary, and validates that it meets the expected
        type constraints.

        Args:
            klass (str | type): Either a dotted import path (e.g.,
                'myapp.serializers.CustomSerializer') or a class object.
            klass_repr (str): Human-readable name for the class, used in error
                messages (e.g., 'MESSAGE_SERIALIZER').
            class_instance (type, optional): Expected parent class or interface
                that the imported class should be an instance of. If provided,
                validates that klass is an instance of this type.

        Returns:
            type: The validated class object.

        Raises:
            ImproperlyConfigured: If the import path is invalid, the imported
                object is not a class, or it doesn't match the expected type.

        Example:
            Using a string path::

                SerializerClass = import_and_verify_type_class(
                    'myapp.serializers.MessageSerializer',
                    'MESSAGE_SERIALIZER',
                    serializers.Serializer.__class__
                )

            Using a class object::

                SerializerClass = import_and_verify_type_class(
                    MessageSerializer,
                    'MESSAGE_SERIALIZER'
                )

        Note:
            When passing a class instance validator, the function checks isinstance
            rather than issubclass, which is useful for validating serializer
            metaclasses.
    """

    if type(klass) == str:
        module_path, klass_name = klass.rsplit('.', 1)
        module = importlib.import_module(module_path)
        klass = getattr(module, klass_name)
    
    
    if not inspect.isclass(klass):
        raise ImproperlyConfigured(f"{klass_repr} should be a class")
    if class_instance and not isinstance(klass, class_instance):
        raise ImproperlyConfigured(f"{klass_repr} should be an instance of {class_instance.__name__}")
    return klass

def import_and_verify_type_function(func, func_repr):

    """
        Dynamically import and validate a function from a string path or object.

        This function accepts either a function object or a dotted import path
        string, imports the function if necessary, and validates that it is
        actually a callable function.

        Args:
            func (str | callable): Either a dotted import path (e.g.,
                'myapp.utils.custom_handler') or a function object.
            func_repr (str): Human-readable name for the function, used in error
                messages (e.g., 'EVENT_MAPPER').

        Returns:
            callable: The validated function object.

        Raises:
            ImproperlyConfigured: If the import path is invalid or the imported
                object is not a function.

        Example:
            Using a string path::

                handler = import_and_verify_type_function(
                    'myapp.handlers.event_mapper',
                    'EVENT_MAPPER'
                )
                result = handler(consumer)

            Using a function object::

                handler = import_and_verify_type_function(
                    event_mapper_function,
                    'EVENT_MAPPER'
                )

        Note:
            This function also accepts database_sync_to_async wrapped functions,
            which are common in Django Channels applications for async-safe
            database operations.
    """

    if type(func) == str:
        module_path, func_name = func.rsplit('.', 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    
    if not inspect.isfunction(func) and not isinstance(func, database_sync_to_async):
        raise ImproperlyConfigured(f"{func_repr} should be a function")
    return func

def import_model(model_str):
    """
    Import a Django model from an app label and model name string.

    No difference with calling apps.get_model() directly


    Args:
        model_str (str): Model reference in 'app_label.ModelName' format
            (e.g., 'realtime_chat_messaging.Message').

    Returns:
        type: The Django model class.

    Raises:
        LookupError: If the app or model doesn't exist.

    Example::

        Message = import_model('realtime_chat_messaging.Message')
        messages = Message.objects.all()

    Note:
        This function delegates to Django's app registry, which handles
        caching and validation internally.
    """    
    return apps.get_model(model_str)



from realtime_chat_messaging.conf import realtime_chat_settings


# Configurable models that can be overridden in settings:

# Models

# "Session",
# "Message", 
# "Room", 
# "GroupChat", 
# "Channel",
# "OneToOneChat",
# "MessageMediaAsset",
# "ReadReceipt",
# "ChatNotification",
# "Reaction"



# Configurable serializers that can be overridden in settings:
# Serializers

# "UserSerializer",
# "OneToOneChatListSerializer",
# "GroupChatListSerializer",
# "ChannelListSerializer",
# "OneToOneChatSerializer",
# "GroupChatSerializer",
# "ChannelSerializer",
# "ReadReceiptSerializer",
# "ReactionSerializer",
# "MessageMediaAssetSerializer",
# "MessageSerializer",
# "ChatNotificationSerializer",
# "RoomListPolymorphicSerializer",
# "RoomPolymorphicSerializer",


_MODEL_CACHE = {}
_SERIALIZER_CACHE = {}

def clear_caches():

    """
        Clear all cached model and serializer references.

        This function is primarily used in testing to ensure a clean state between
        test runs, especially when dynamically changing settings or swapping
        implementations.

        Example::

            # In test teardown
            def tearDown(self):
                clear_caches()
                super().tearDown()

        Note:
            This does not affect Django's internal model registry or DRF's
            serializer metaclass caches, only the package's internal caches.
    """
    _MODEL_CACHE.clear()
    _SERIALIZER_CACHE.clear()



def _load_models():
    """
        Load and cache model configuration from settings.

        This internal function performs lazy initialization of the model cache,
        loading model references from settings only when first needed.

        Returns:
            dict: Mapping of model names to their import paths.

        Note:
            This is an internal function and should not be called directly.
            Use get_model() instead for retrieving specific models.
    """
    if not _MODEL_CACHE:
        _MODEL_CACHE.update(realtime_chat_settings.MODELS)
    return _MODEL_CACHE

def _load_serializers():
    """
        Load and cache serializer configuration from settings.

        This internal function performs lazy initialization of the serializer
        cache, loading serializer references from settings only when first needed.

        Returns:
            dict: Mapping of serializer names to their import paths or classes.

        Note:
            This is an internal function and should not be called directly.
            Use get_serializer() instead for retrieving specific serializers.
    """    
    if not _SERIALIZER_CACHE:
        _SERIALIZER_CACHE.update(realtime_chat_settings.SERIALIZERS)
    return _SERIALIZER_CACHE


def get_model(name: str) -> models.Model:
    """
        Retrieve a configured model class by name.

        This function looks up the model's import path from settings, imports it,
        and returns the model class. Model references are cached after first load
        for performance.

        Args:
            name (str): The model name as defined in the MODELS setting
                (e.g., 'Message', 'Room', 'Session').

        Returns:
            type: The Django model class.

        Raises:
            KeyError: If the model name is not defined in settings.
            LookupError: If the model's import path is invalid.

        Example::

            Message = get_model('Message')
            message = Message.objects.create(
                room=room,
                sender=user,
                content="Hello"
            )

        Note:
            This function enables the package to work with custom user-defined
            models by looking them up from the MODELS configuration dictionary
            in settings.
    """
    map_model_name = _load_models()
    model = map_model_name[name] # raises error if not present
    return import_model(model)




def get_serializer(name: str) -> serializers.Serializer:
    """
        Retrieve a configured serializer class by name.

        This function looks up the serializer's import path or class from settings,
        imports and validates it, and returns the serializer class. Serializer
        references are cached after first load for performance.

        Args:
            name (str): The serializer name as defined in the SERIALIZERS setting
                (e.g., 'MessageSerializer', 'RoomPolymorphicSerializer').

        Returns:
            type: The DRF serializer class.

        Raises:
            KeyError: If the serializer name is not defined in settings.
            ImproperlyConfigured: If the imported object is not a valid DRF
                serializer class.

        Example::

            MessageSerializer = get_serializer('MessageSerializer')
            serializer = MessageSerializer(message)
            return serializer.data

        Note:
            This function validates that the retrieved class is actually a DRF
            serializer by checking its metaclass, ensuring type safety when
            users provide custom serializers.
    """
    map_serializer_name = _load_serializers()
    serializer = map_serializer_name[name]
    return import_and_verify_type_class(serializer, name, serializers.Serializer.__class__)



