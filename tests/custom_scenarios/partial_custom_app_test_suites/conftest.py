"""
Pytest configuration for Scenario 1: Custom Message Only
"""
import pytest
from django.contrib.auth import get_user_model
from partial_custom_app.models import CustomMessage, CustomGroupChat
from realtime_chat_messaging.utils.cache_utils import add_group_to_user_groups
from realtime_chat_messaging.consumers import GROUP_STRING
from asgiref.sync import async_to_sync
from tests.conftest import *


User = get_user_model()



@pytest.fixture
def create_custom_message(db):
    """Factory for creating custom messages"""
    def _create_message(room, sender, content='Test message', priority='normal', **kwargs):
        return CustomMessage.objects.create(
            room=room,
            sender=sender,
            content=content,
            priority=priority,
            **kwargs
        )
    return _create_message




@pytest.fixture
def message_factory(create_custom_message):
    """Factory for creating multiple messages"""
    def _create_messages(room, sender, count=10, **kwargs):
        messages = []
        for i in range(count):
            msg = create_custom_message(
                room=room,
                sender=sender,
                content=f"Message {i}",
                **kwargs
            )
            messages.append(msg)
        return messages
    return _create_messages


@pytest.fixture(autouse=True)
async def clear_cache_and_channels(db):
    """Clear cache and channel layers before each test"""
    from django.core.cache import cache
    from channels.layers import get_channel_layer
    
    cache.clear()
    
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.flush()
    
    yield
    
    cache.clear()
    if channel_layer:
        await channel_layer.flush()


@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(10)

@pytest.fixture
def one_to_one_chat(users, register_room_with_user, create_one_to_one_chat):
    """Create a one-to-one chat"""
    room = create_one_to_one_chat(users[0], users[1])
    async_to_sync(register_room_with_user)(users[0].id, room.id)
    async_to_sync(register_room_with_user)(users[1].id, room.id)
    return room


@pytest.fixture
def register_room_with_user():
    async def _register_room(user_id, room_id):
        group = GROUP_STRING.format(group_id=room_id)
        await add_group_to_user_groups(user_id, group)
    return _register_room


@pytest.fixture
def add_users_to_room_channel_group(register_room_with_user):
    async def _register(room_id, users=[]):
        for user in users:
            await register_room_with_user(user.id, str(room_id))
    return _register


@pytest.fixture
def create_custom_group(db):
    """Factory for creating custom group chats"""
    def _create_group(creator, name='Test Group', department='general', **kwargs):
        group = CustomGroupChat.objects.create(
            name=name,
            creator=creator,
            department=department,
            **kwargs
        )
        return group
    return _create_group
