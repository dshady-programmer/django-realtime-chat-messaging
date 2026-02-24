"""
Event routing configuration for WebSocket consumers.

This module defines the mapping between client event types and consumer
handler methods. The mapper function is called in the consumer's receive()
method to route incoming events to the appropriate handlers.

Customization:
    Override EVENT_MAPPER in settings to add custom events, remove events,
    or modify routing logic::

        # myapp/event_mapper.py
        def custom_event_mapper(consumer):
            base_events = map_event_type_to_handlers(consumer)
            # Add custom event
            base_events["custom.event"] = consumer.receive_custom_event
            # Remove event (block from being exposed)
            del base_events["room.delete"]
            return base_events

        # settings.py
        REALTIME_CHAT_MESSAGING = {
            'EVENT_MAPPER': 'myapp.event_mapper.custom_event_mapper',
        }
"""







"""
    Map client event types to consumer handler methods.

    This function creates a dictionary mapping event type strings to their
    corresponding handler methods on the consumer instance. The consumer's
    receive() method uses this mapping to route incoming events.

    Args:
        consumer: The WebSocket consumer instance.

    Returns:
        dict[str, callable]: Mapping of event types to handler methods.

    Event Categories:
        Message events:
            - message.send: Send new message
            - message.acknowledged: Mark message as delivered
            - message.read: Mark message as read
            - message.react: Add/remove reaction
            - message.typing: Typing indicator
            - message.modify: Edit or delete message

        Room events:
            - room.create: Create new room
            - room.list: Get all user's rooms
            - room.info: Get room details
            - room.messages: Get paginated messages
            - room.join: Join a room
            - room.leave: Leave a room
            - room.add_members: Add users to room
            - room.remove_members: Remove users from room
            - room.modify: Update room settings or manage admins/moderators

        Session events:
            - session.heartbeat: Keep session alive

    Example:
        Custom mapper that adds an event and removes another::

            def my_mapper(consumer):
                events = map_event_type_to_handlers(consumer)
                events["message.pin"] = consumer.receive_pin_message
                del events["room.modify"]  # Block this event
                return events

    Note:
        The returned dictionary can be mutated to customize behavior without
        modifying the package source code.
"""
map_event_type_to_handlers = lambda consumer:  {
            "message.send": consumer.receive_message_send_event,
            "message.acknowledged": consumer.receive_message_acknowledged_event,
            "message.read": consumer.receive_message_read_event,
            "message.react": consumer.receive_message_reaction_event, 
            "message.typing": consumer.receive_message_typing_event,
            "message.modify": consumer.receive_message_modify_event,
            "room.create": consumer.receive_room_create_event,
            "room.list": consumer.receive_get_rooms,
            "room.info": consumer.receive_get_room_info,
            "room.add_members": consumer.receive_add_members_to_room,
            "room.remove_members": consumer.receive_remove_members_from_room,
            "room.messages": consumer.receive_message_list,
            "room.join": consumer.receive_join_room_event,
            "room.leave": consumer.receive_leave_room_event,
            "room.modify": consumer.receive_modify_room_event, # add or remove admins/moderators (for the user),  change name/description/preferences,
            "session.heartbeat": consumer.receive_update_session_heartbeat

        }


