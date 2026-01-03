def get_settings():
    """
    To avoid circular imports

    Note: There are probably better ways to do this.
    """
    from realtime_chat_messaging.conf import realtime_chat_settings # python caches import after the first import
    return realtime_chat_settings