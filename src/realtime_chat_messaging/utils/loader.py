import importlib
import inspect
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from channels.db import database_sync_to_async
from django.apps import apps
from django.db import models

def import_and_verify_type_class(klass, klass_repr, class_instance=None):
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
    if type(func) == str:
        module_path, func_name = func.rsplit('.', 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    
    if not inspect.isfunction(func) and not isinstance(func, database_sync_to_async):
        raise ImproperlyConfigured(f"{func_repr} should be a function")
    return func

def import_model(model_str):
    return apps.get_model(model_str)



from realtime_chat_messaging.conf import realtime_chat_settings
from operator import itemgetter


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
    _MODEL_CACHE.clear()
    _SERIALIZER_CACHE.clear()



def _load_models():
    if not _MODEL_CACHE:
        _MODEL_CACHE.update(realtime_chat_settings.MODELS)
    return _MODEL_CACHE
def _load_serializers():
    if not _SERIALIZER_CACHE:
        _SERIALIZER_CACHE.update(realtime_chat_settings.SERIALIZERS)
    return _SERIALIZER_CACHE


def get_model(name: str) -> models.Model:
    map_model_name = _load_models()
    model = map_model_name[name] # raises error if not present
    return import_model(model)




def get_serializer(name: str) -> serializers.Serializer:
    map_serializer_name = _load_serializers()
    serializer = map_serializer_name[name]
    return import_and_verify_type_class(serializer, name, serializers.Serializer.__class__)



