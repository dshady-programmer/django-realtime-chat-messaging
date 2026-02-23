"""
Cache utilities for managing user group memberships in real-time chat.

This module provides async-safe cache operations for storing and retrieving
user channel group memberships. Group memberships are cached to enable quick
session restoration when users reconnect, ensuring they are automatically
re-subscribed to all relevant chat rooms.

The cache stores group memberships as JSON-serialized lists with no expiration,
allowing persistent tracking of user subscriptions across application restarts.
"""

from django.core.cache import cache
from django.contrib.auth import get_user_model
import json
from asgiref.sync import sync_to_async
User = get_user_model()

@sync_to_async
def fetch_user_groups(user_id: str):
    """
        Retrieve all cached group memberships for a user.

        This function fetches the list of channel groups (chat rooms) that a user
        is currently subscribed to. The cached groups are used during connection
        setup to restore the user's channel subscriptions.

        Args:
            user_id (str): The unique identifier of the user.

        Returns:
            list[str]: List of group names the user is subscribed to. Returns an
                empty list if no cached groups are found.

        Example:
            >>> groups = await fetch_user_groups("123")
            >>> print(groups)
            ['group-45', 'group-67', 'user-123']

        Note:
            This function is async-safe and can be called from asynchronous
            consumers without blocking the event loop.
    """
    key = f"user:{user_id}:groups"
    value = cache.get(key)
    if value:
        groups = json.loads(value)
        return groups
    return []


@sync_to_async
def update_user_groups(user_id: str, groups: list):

    """
        Replace all cached group memberships for a user.

        This function completely overwrites the user's cached group list with the
        provided list. It is typically used during initial connection setup or
        when performing bulk group membership updates.

        Args:
            user_id (str): The unique identifier of the user.
            groups (list[str]): Complete list of group names to cache.

        Returns:
            None

        Example:
            >>> await update_user_groups("123", ["group-45", "group-67", "user-123"])

        Note:
            The cache entry has no expiration timeout, ensuring group memberships
            persist across application restarts. This is intentional to support
            session restoration.
    """
    key = f"user:{user_id}:groups"
    cache.set(key, json.dumps(groups), timeout=None)
    return None


@sync_to_async
def add_group_to_user_groups(user_id: str, group: str):
    """
        Add a single group to a user's cached group memberships.

        This function appends a new group to the user's existing cached group list,
        creating a new list if none exists. Duplicate groups are automatically
        prevented.

        Args:
            user_id (str): The unique identifier of the user.
            group (str): The group name to add to the user's memberships.

        Returns:
            None

        Example:
            >>> await add_group_to_user_groups("123", "group-89")

        Note:
            This function is idempotent - calling it multiple times with the same
            group will not create duplicates. It is typically called when a user
            joins a room or is added to a group chat.
    """

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
    """
        Remove a single group from a user's cached group memberships.

        This function removes a group from the user's existing cached group list.
        If the group is not present in the list, no error is raised.

        Args:
            user_id (str): The unique identifier of the user.
            group (str): The group name to remove from the user's memberships.

        Returns:
            None

        Example:
            >>> await remove_group_from_user_groups("123", "group-45")

        Note:
            This function is idempotent - calling it multiple times with the same
            group will not raise errors. It is typically called when a user leaves
            a room or is removed from a group chat.
    """
    key = f"user:{user_id}:groups"
    value = cache.get(key)
    if not value:
        groups = []
    else:
        groups = json.loads(value)
    if group in groups:
        groups.remove(group)
    cache.set(key, json.dumps(groups), timeout=None)
    


