


def parse_to_dict(argIterable: list | tuple | set):
    return_dict = {}
    for entry in argIterable:
        # works for classes and functions 
        return_dict[entry.__name__] = entry
    return return_dict


def get_defaults():
    from .variables.serializers import (
        UserSerializer, 
        OneToOneChatListSerializer,
        GroupChatListSerializer,
        ChannelListSerializer,
        RoomListPolymorphicSerializer,
        OneToOneChatSerializer,
        GroupChatSerializer,
        ChannelSerializer,
        RoomPolymorphicSerializer,
        ReadReceiptSerializer,
        ReactionSerializer,
        MessageMediaAssetSerializer,
        MessageSerializer,
        ChatNotificationSerializer
    )
    from .variables.models import (
        Room, 
        OneToOneChat,
        GroupChat,
        Channel,
        Message,
        ReadReceipt,
        ChatNotification,
        Reaction,
        MessageMediaAsset
    )
    from .variables.permissions.helpers import (
        have_room_permission,
        have_message_permission,
        is_message_sender,
        have_room_permissions_to_add_or_remove_members,
        have_send_message_permission,
        have_admin_privileges
    )
    from .variables.utils.event_handlers import (
        get_and_group_chat_notifications,
        create_message,
        react_to_message,
        message_acknowledged,
        modify_message,
        create_read_receipt,
        create_room,
        list_rooms,
        retreive_room,
        add_members_to_room,
        remove_members_from_room,
        leave_room,
        join_room,
        retreive_messages,
        modify_room
    )
    from .variables.utils.exception_handlers import ExceptionHandler
    from .variables.consumers import map_event_type_to_handlers

    return {
        "SERIALIZERS": parse_to_dict(
            (
                UserSerializer, 
                OneToOneChatListSerializer,
                GroupChatListSerializer,
                ChannelListSerializer,
                RoomListPolymorphicSerializer,
                OneToOneChatSerializer,
                GroupChatSerializer,
                ChannelSerializer,
                RoomPolymorphicSerializer,
                ReadReceiptSerializer,
                ReactionSerializer,
                MessageMediaAssetSerializer,
                MessageSerializer,
                ChatNotificationSerializer
            )
        ),
        "MODELS": parse_to_dict(
            (
                Room, 
                OneToOneChat,
                GroupChat,
                Channel,
                Message,
                ReadReceipt,
                ChatNotification,
                Reaction,
                MessageMediaAsset
            )
        ),
        "PERMISSIONS": parse_to_dict(
            (
                have_room_permission,
                have_message_permission,
                is_message_sender,
                have_room_permissions_to_add_or_remove_members,
                have_send_message_permission,
                have_admin_privileges
            )
        ),
        "EVENT_MAPPER": map_event_type_to_handlers,
        "EVENT_HANDLERS": parse_to_dict(
            (
                get_and_group_chat_notifications,
                create_message,
                react_to_message,
                message_acknowledged,
                modify_message,
                create_read_receipt,
                create_room,
                list_rooms,
                retreive_room,
                add_members_to_room,
                remove_members_from_room,
                leave_room,
                join_room,
                retreive_messages,
                modify_room
            )
        ),
        "EXCEPTION_HANDLER_CLASS": ExceptionHandler,
        "MESSAGE_SOFT_DELETE": False

    }