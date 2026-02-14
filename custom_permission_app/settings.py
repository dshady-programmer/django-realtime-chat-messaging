"""
Settings for Scenario 3: Custom Permissions Only

This settings file demonstrates overriding only the permission handler
while keeping all models and serializers as defaults.
"""
from tests.settings import *

# Add custom app to INSTALLED_APPS
INSTALLED_APPS = INSTALLED_APPS + [
    'scenario_3_custom_permissions_only.custom_permissions_app',
]

# Override only permission handler
REALTIME_CHAT_MESSAGING = {
    'PERMISSION_HANDLER_CLASS': 'custom_permissions_app.permissions.CustomPermissionHandler',
}
