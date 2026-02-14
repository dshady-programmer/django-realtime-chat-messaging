from tests.settings import *

"""
Settings for Scenario 3: Custom Permissions Only

This settings file demonstrates overriding only the permission handler
while keeping all models and serializers as defaults.
"""

# Override only permission handler
REALTIME_CHAT_MESSAGING = {
    'PERMISSION_HANDLER_CLASS': 'custom_permission_app.permissions.CustomPermissionHandler',
}
