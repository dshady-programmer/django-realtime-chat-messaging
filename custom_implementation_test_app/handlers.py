from realtime_chat_messaging.utils.handlers import EventHandler

# ==================== CUSTOM HANDLER IMPLEMENTATIONS ====================


class CustomEventHandler(EventHandler):
    """Custom event handler combining all mixins"""

    def _create_message(self, data, user):
        """Override to add priority handling"""
        priority = data.get('priority', 'normal')
        
        # Call parent implementation
        result = super()._create_message(data, user)
        
        # Add custom logic
        if priority == 'urgent':
            # Could trigger notifications, etc.
            pass
        
        return result
