from realtime_chat_messaging.utils.cache_utils import add_group_to_user_groups
from realtime_chat_messaging.consumers import GROUP_STRING
from asgiref.sync import async_to_sync
from ...conftest import * 

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