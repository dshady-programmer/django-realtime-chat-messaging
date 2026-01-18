from django.core.cache import cache
from django.contrib.auth import get_user_model
import json
from asgiref.sync import sync_to_async
User = get_user_model()

@sync_to_async
def fetch_user_groups(user_id: str):
    key = f"user:{user_id}:groups"
    value = cache.get(key)
    if value:
        groups = json.loads(value)
        return groups
    return []


@sync_to_async
def update_user_groups(user_id: str, groups: list):
    key = f"user:{user_id}:groups"
    cache.set(key, json.dumps(groups), timeout=None)
    return None


@sync_to_async
def add_group_to_user_groups(user_id: str, group: str):
    key = f"user:{user_id}:groups"
    value = cache.get(key)
    if not value:
        groups = []
    else:
        groups = json.loads(value)
    if group not in groups:
        groups.append(group)
    cache.set(key, json.dumps(groups), timeout=None)
    
@sync_to_async
def remove_group_from_user_groups(user_id: str, group: str):
    key = f"user:{user_id}:groups"
    value = cache.get(key)
    if not value:
        groups = []
    else:
        groups = json.loads(value)
    if group in groups:
        groups.remove(group)
    cache.set(key, json.dumps(groups), timeout=None)
    


