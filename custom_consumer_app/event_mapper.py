"""
Custom Event Mapper for CustomChatConsumer

This maps event types to handler methods in the custom consumer.
Extends the default event mapper to include custom events:
- message.pin
- message.flag
- message.analytics
"""
from realtime_chat_messaging.variables.consumers import map_event_type_to_handlers as default_mapper


def custom_event_mapper(consumer):
    """
    Custom event mapper that extends default mapper with custom events.
    
    Args:
        consumer: The consumer instance (CustomChatConsumer)
    
    Returns:
        dict: Mapping of event types to handler methods
    """
    # Get default mappings
    event_map = default_mapper(consumer)
    
    # Add custom event handlers
    custom_events = {
        'message.pin': consumer.message_pin,
        'message.flag': consumer.message_flag,
        'message.analytics': consumer.message_analytics,
    }
    
    # Merge with defaults
    event_map.update(custom_events)
    
    return event_map