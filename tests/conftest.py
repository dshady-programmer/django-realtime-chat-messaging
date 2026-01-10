"""
Pytest configuration file for realtime_chat_messaging tests.

This file contains shared fixtures, configurations, and setup
for all test modules in the test suite.
"""

import pytest
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from asgiref.sync import async_to_sync
import pytest_asyncio


User = get_user_model()


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom settings"""
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )


# # Django settings for tests
# @pytest.fixture(scope='session')
# def django_db_setup(django_db_setup, django_db_blocker):
#     """Override Django database setup for tests"""
#     with django_db_blocker.unblock():
#         from django.conf import settings



# Clear cache before each test
@pytest.fixture(autouse=True)
def clear_cache(db):
    """Clear cache before each test"""
    cache.clear()


# Clear channel layers
@pytest.fixture(autouse=True)
def clear_channel_layers():
    """Clear channel layers before each test"""
    channel_layer = get_channel_layer()
    if hasattr(channel_layer, 'flush'):
        async_to_sync(channel_layer.flush)()
    yield
    if hasattr(channel_layer, 'flush'):
        async_to_sync(channel_layer.flush)()


# Shared user fixtures
@pytest.fixture
def user(db):
    """Create a single test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.fixture
def admin_user(db):
    """Create an admin user"""
    return User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123'
    )


@pytest.fixture
def create_users(db):
    """Factory fixture for creating multiple users"""
    def _create_users(count):
        users = []
        for i in range(count):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            users.append(user)
        return users
    return _create_users


# WebSocket communicator fixtures
@pytest.fixture
def websocket_communicator():
    """Factory fixture for creating WebSocket communicators"""
    from realtime_chat_messaging.consumers import ChatMessagingConsumer
    
    async def _create_communicator(user):
        communicator = WebsocketCommunicator(
            ChatMessagingConsumer.as_asgi(),
            "/messaging/"
        )
        communicator.scope['user'] = user
        return communicator
    
    return _create_communicator


# Model factories
@pytest.fixture
def create_one_to_one_chat(db):
    """Factory fixture for creating one-to-one chats"""
    from realtime_chat_messaging.models import OneToOneChat
    
    def _create_chat(user1, user2):
        chat = OneToOneChat.objects.create()
        chat.participants.set([user1, user2])
        return chat
    
    return _create_chat


@pytest.fixture
def create_group_chat(db):
    """Factory fixture for creating group chats"""
    from realtime_chat_messaging.models import GroupChat
    
    def _create_group(creator, name="Test Group", **kwargs):
        return GroupChat.objects.create(
            name=name,
            creator=creator,
            **kwargs
        )
    
    return _create_group


@pytest.fixture
def create_channel(db):
    """Factory fixture for creating channels"""
    from realtime_chat_messaging.models import Channel
    
    def _create_channel(creator, name="Test Channel", **kwargs):
        return Channel.objects.create(
            name=name,
            creator=creator,
            **kwargs
        )
    
    return _create_channel


@pytest.fixture
def create_message(db):
    """Factory fixture for creating messages"""
    from realtime_chat_messaging.models import Message
    
    def _create_message(room, sender, content="Test message", **kwargs):
        return Message.objects.create(
            room=room,
            sender=sender,
            content=content,
            **kwargs
        )
    
    return _create_message


# Helper fixtures
@pytest.fixture
def assert_message_broadcast():
    """Helper fixture for asserting message broadcasts"""
    async def _assert_broadcast(communicators, expected_event_type, expected_data_subset=None):
        """
        Assert that all communicators receive a broadcast with expected data.
        
        Args:
            communicators: List of WebSocket communicators
            expected_event_type: Expected event type in response
            expected_data_subset: Optional dict of expected data keys/values
        """
        responses = []
        for comm in communicators:
            response = await comm.receive_json_from()
            responses.append(response)
            assert response['eventType'] == expected_event_type
            
            if expected_data_subset:
                for key, value in expected_data_subset.items():
                    assert response['data'][key] == value
        
        return responses
    
    return _assert_broadcast


@pytest.fixture
def create_notification(db):
    """Factory fixture for creating chat notifications"""
    from realtime_chat_messaging.models import ChatNotification
    
    def _create_notification(message, notification_type='NEW_MESSAGE', recipients=None):
        notification = ChatNotification.objects.create(
            message=message,
            notification_type=notification_type
        )
        if recipients:
            notification.recipients.set(recipients)
        return notification
    
    return _create_notification


@pytest.fixture(
    params=[
        ("<script>alert('xss')</script>", "alert('xss')"),
        ("<p>Hello<script>alert(1)</script></p>", "<p>Helloalert(1)</p>"),
        ('<p onclick="alert(1)">Click me</p>', "<p>Click me</p>"),
        ('<a href="javascript:alert(1)">link</a>', "<a>link</a>"),
        ('<a href="JaVaScRiPt:alert(1)">link</a>', "<a>link</a>"),
        ('<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==">x</a>', "<a>x</a>"),
        ('<img src="x" onerror="alert(1)">', ""),
        ('<svg onload="alert(1)"></svg>', ""),
        ('<p style="background:url(javascript:alert(1))">Test</p>', "<p>Test</p>"),
        ('<!--<script>alert(1)</script>-->', ""),
        ('<scr<script>ipt>alert(1)</scr</script>ipt>', "ipt&gt;alert(1)ipt&gt;"),
        ('<ul><li>Item<script>alert(1)</script></li></ul>', "<ul><li>Itemalert(1)</li></ul>"),
        ('<iframe src="https://evil.com"></iframe>', ""),
        ('<a href="https://example.com" onclick="alert(1)" class="x">ok</a>',
         '<a href="https://example.com" class="x">ok</a>'),
        ('<p id="test" class="safe">hello</p>', '<p id="test" class="safe">hello</p>'),
        ('&lt;script&gt;alert(1)&lt;/script&gt;', '&lt;script&gt;alert(1)&lt;/script&gt;'),
        ('<p onclick="alert(1)"><a href="javascript:alert(2)">x</a><script>alert(3)</script></p>',
         '<p><a>x</a>alert(3)</p>'),
        ('<a href="https://example.com" target="_blank">go</a>',
         '<a href="https://example.com" target="_blank">go</a>'),
        ('<p data-test="x" aria-label="y">hi</p>', '<p>hi</p>'),
        ('Hello<br><script>alert(1)</script>World', 'Hello<br>alert(1)World'),
    ]
)
def html_payload(request):
    content, expected = request.param
    return content, expected




# Async helper fixtures
@pytest.fixture
def async_db_operations():
    """Helper for async database operations"""
    from channels.db import database_sync_to_async
    
    class AsyncDBHelper:
        @staticmethod
        def to_async(func):
            return database_sync_to_async(func)
        
        @staticmethod
        async def create_and_save(model_class, **kwargs):
            return await database_sync_to_async(model_class.objects.create)(**kwargs)
        
        @staticmethod
        async def add_to_many_to_many(instance, field_name, *objects):
            field = getattr(instance, field_name)
            return await database_sync_to_async(field.add)(*objects)
        
        @staticmethod
        async def remove_from_many_to_many(instance, field_name, *objects):
            field = getattr(instance, field_name)
            return await database_sync_to_async(field.remove)(*objects)
    
    return AsyncDBHelper()


# Performance monitoring fixtures
@pytest.fixture
def performance_monitor():
    """Monitor test performance"""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return PerformanceMonitor()


# Cleanup fixtures
@pytest.fixture
def cleanup_rooms():
    """Cleanup fixture to remove all rooms after test"""
    yield
    
    from realtime_chat_messaging.models import Room
    Room.objects.all().delete()


@pytest.fixture
def cleanup_messages():
    """Cleanup fixture to remove all messages after test"""
    yield
    
    from realtime_chat_messaging.models import Message
    Message.objects.all().delete()




# Parametrize helpers
@pytest.fixture
def room_types():
    """Fixture providing all room types for parametrized tests"""
    return ['OneToOneChat', 'GroupChat', 'Channel']


@pytest.fixture
def notification_types():
    """Fixture providing all notification types"""
    return ['NEW_MESSAGE', 'REPLY', 'REACTION']


@pytest.fixture
def media_types():
    """Fixture providing all media types"""
    return ['image', 'video', 'audio', 'file']


# Test data generators
@pytest.fixture
def generate_test_data():
    """Generate various test data"""
    import string
    import random
    
    class TestDataGenerator:
        @staticmethod
        def random_string(length=10):
            return ''.join(random.choices(string.ascii_letters, k=length))
        
        @staticmethod
        def random_email():
            return f"{TestDataGenerator.random_string()}@example.com"
        
        @staticmethod
        def random_username():
            return f"user_{TestDataGenerator.random_string(8)}"
        
        @staticmethod
        def random_message_content():
            words = ['hello', 'test', 'message', 'world', 'python', 'django']
            return ' '.join(random.choices(words, k=random.randint(3, 10)))
    
    return TestDataGenerator()


# Coverage helpers
@pytest.fixture(autouse=True)
def reset_sequences(django_db_reset_sequences):
    """Reset database sequences for each test"""
    pass


# Logging configuration for tests
@pytest.fixture(autouse=True)
def configure_test_logging(caplog):
    """Configure logging for tests"""
    import logging
    caplog.set_level(logging.INFO)


# Environment setup
@pytest.fixture(scope='session', autouse=True)
def setup_test_environment():
    """Setup test environment"""
    import os
    os.environ['TESTING'] = 'True'
    yield
    del os.environ['TESTING']