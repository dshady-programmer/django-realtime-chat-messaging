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

(
    _Session,
    _Message, 
    _Room, 
    _GroupChat, 
    _Channel,
    _OneToOneChat,
    _MessageMediaAsset,
    _ReadReceipt,
    _ChatNotification,
    _Reaction,

) = itemgetter(
    "Session",
    "Message", 
    "Room", 
    "GroupChat", 
    "Channel",
    "OneToOneChat",
    "MessageMediaAsset",
    "ReadReceipt",
    "ChatNotification",
    "Reaction"
)(realtime_chat_settings.MODELS)

(
    _UserSerializer,
    _OneToOneChatListSerializer,
    _GroupChatListSerializer,
    _ChannelListSerializer,
    _OneToOneChatSerializer,
    _GroupChatSerializer,
    _ChannelSerializer,
    _ReadReceiptSerializer,
    _ReactionSerializer,
    _MessageMediaAssetSerializer,
    _MessageSerializer,
    _ChatNotificationSerializer,
    _RoomListPolymorphicSerializer,
    _RoomPolymorphicSerializer
 )  = itemgetter(
        "UserSerializer",
        "OneToOneChatListSerializer",
        "GroupChatListSerializer",
        "ChannelListSerializer",
        "OneToOneChatSerializer",
        "GroupChatSerializer",
        "ChannelSerializer",
        "ReadReceiptSerializer",
        "ReactionSerializer",
        "MessageMediaAssetSerializer",
        "MessageSerializer",
        "ChatNotificationSerializer",
        "RoomListPolymorphicSerializer",
        "RoomPolymorphicSerializer",
    )(realtime_chat_settings.SERIALIZERS)

def get_model(name: str) -> models.Model:
    map_model_name = {
        "Session": _Session,
        "Message": _Message, 
        "Room": _Room, 
        "GroupChat": _GroupChat, 
        "Channel": _Channel,
        "OneToOneChat": _OneToOneChat,
        "MessageMediaAsset": _MessageMediaAsset,
        "ReadReceipt": _ReadReceipt,
        "ChatNotification": _ChatNotification,
        "Reaction": _Reaction
    }
    model = map_model_name[name] # raises error if not present
    return import_model(model)




def get_serializer(name: str) -> serializers.Serializer:
    map_serializer_name = {
        "UserSerializer": _UserSerializer,
        "OneToOneChatListSerializer": _OneToOneChatListSerializer,
        "GroupChatListSerializer": _GroupChatListSerializer,
        "ChannelListSerializer": _ChannelListSerializer,
        "OneToOneChatSerializer": _OneToOneChatSerializer,
        "GroupChatSerializer": _GroupChatSerializer,
        "ChannelSerializer": _ChannelSerializer,
        "ReadReceiptSerializer": _ReadReceiptSerializer,
        "ReactionSerializer": _ReactionSerializer,
        "MessageMediaAssetSerializer": _MessageMediaAssetSerializer,
        "MessageSerializer": _MessageSerializer,
        "ChatNotificationSerializer": _ChatNotificationSerializer,
        "RoomListPolymorphicSerializer": _RoomListPolymorphicSerializer,
        "RoomPolymorphicSerializer": _RoomPolymorphicSerializer,
    }
    serializer = map_serializer_name[name]
    return import_and_verify_type_class(serializer, name, serializers.Serializer.__class__)



