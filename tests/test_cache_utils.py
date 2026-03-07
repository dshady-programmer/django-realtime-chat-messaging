"""
Unit tests for cache utility functions.

Tests cover:
- fetch_user_groups
- update_user_groups  
- add_group_to_user_groups
- remove_group_from_user_groups
- Concurrent cache operations
- Cache persistence and invalidation
"""
import pytest
import asyncio
from django.core.cache import cache
from django.contrib.auth import get_user_model
from realtime_chat_messaging.utils.cache_utils import (
    fetch_user_groups,
    update_user_groups,
    add_group_to_user_groups,
    remove_group_from_user_groups
)

User = get_user_model()


@pytest.fixture
def users(create_users):
    """Create test users"""
    return create_users(5)


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear cache before each test"""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.asyncio
@pytest.mark.django_db
class TestFetchUserGroups:
    """Test fetch_user_groups function"""
    
    async def test_fetch_empty_groups(self, users):
        """Test fetching groups when user has no groups cached"""
        groups = await fetch_user_groups(users[0].id)
        
        assert groups == []
        assert isinstance(groups, list)
    
    async def test_fetch_existing_groups(self, users):
        """Test fetching groups when user has groups cached"""
        # Set groups in cache
        await update_user_groups(users[0].id, ['group-1', 'group-2', 'group-3'])
        
        # Fetch groups
        groups = await fetch_user_groups(users[0].id)
        
        assert groups == ['group-1', 'group-2', 'group-3']
        assert len(groups) == 3
    
    async def test_fetch_returns_list(self, users):
        """Test that fetch always returns a list"""
        # Empty case
        groups1 = await fetch_user_groups(users[0].id)
        assert isinstance(groups1, list)
        
        # Non-empty case
        await update_user_groups(users[1].id, ['group-1'])
        groups2 = await fetch_user_groups(users[1].id)
        assert isinstance(groups2, list)
    
    async def test_fetch_different_users_isolated(self, users):
        """Test that different users have isolated group caches"""
        await update_user_groups(users[0].id, ['group-A'])
        await update_user_groups(users[1].id, ['group-B'])
        
        groups0 = await fetch_user_groups(users[0].id)
        groups1 = await fetch_user_groups(users[1].id)
        
        assert groups0 == ['group-A']
        assert groups1 == ['group-B']
        assert groups0 != groups1


@pytest.mark.asyncio
@pytest.mark.django_db
class TestUpdateUserGroups:
    """Test update_user_groups function"""
    
    async def test_update_empty_to_groups(self, users):
        """Test updating from empty to having groups"""
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == ['group-1', 'group-2']
    
    async def test_update_replaces_existing(self, users):
        """Test that update replaces existing groups"""
        # Set initial groups
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        
        # Update with new groups
        await update_user_groups(users[0].id, ['group-3', 'group-4'])
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == ['group-3', 'group-4']
        assert 'group-1' not in groups
        assert 'group-2' not in groups
    
    async def test_update_with_empty_list(self, users):
        """Test updating to empty list"""
        # Set initial groups
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        
        # Update to empty
        await update_user_groups(users[0].id, [])
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == []
    
    async def test_update_persists_across_fetches(self, users):
        """Test that updates persist across multiple fetches"""
        await update_user_groups(users[0].id, ['group-1'])
        
        # Fetch multiple times
        groups1 = await fetch_user_groups(users[0].id)
        groups2 = await fetch_user_groups(users[0].id)
        groups3 = await fetch_user_groups(users[0].id)
        
        assert groups1 == groups2 == groups3 == ['group-1']


@pytest.mark.asyncio
@pytest.mark.django_db
class TestAddGroupToUserGroups:
    """Test add_group_to_user_groups function"""
    
    async def test_add_to_empty_groups(self, users):
        """Test adding group when user has no groups"""
        await add_group_to_user_groups(users[0].id, 'group-1')
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == ['group-1']
    
    async def test_add_to_existing_groups(self, users):
        """Test adding group when user has existing groups"""
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        await add_group_to_user_groups(users[0].id, 'group-3')
        
        groups = await fetch_user_groups(users[0].id)
        assert 'group-1' in groups
        assert 'group-2' in groups
        assert 'group-3' in groups
        assert len(groups) == 3
    
    async def test_add_duplicate_group(self, users):
        """Test that adding duplicate group doesn't create duplicates"""
        await update_user_groups(users[0].id, ['group-1'])
        await add_group_to_user_groups(users[0].id, 'group-1')
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == ['group-1']
        assert groups.count('group-1') == 1
    
    async def test_add_multiple_groups_sequentially(self, users):
        """Test adding multiple groups one by one"""
        await add_group_to_user_groups(users[0].id, 'group-1')
        await add_group_to_user_groups(users[0].id, 'group-2')
        await add_group_to_user_groups(users[0].id, 'group-3')
        
        groups = await fetch_user_groups(users[0].id)
        assert len(groups) == 3
        assert all(g in groups for g in ['group-1', 'group-2', 'group-3'])


@pytest.mark.asyncio
@pytest.mark.django_db
class TestRemoveGroupFromUserGroups:
    """Test remove_group_from_user_groups function"""
    
    async def test_remove_from_existing_groups(self, users):
        """Test removing group from existing groups"""
        await update_user_groups(users[0].id, ['group-1', 'group-2', 'group-3'])
        await remove_group_from_user_groups(users[0].id, 'group-2')
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == ['group-1', 'group-3']
        assert 'group-2' not in groups
    
    async def test_remove_non_existent_group(self, users):
        """Test removing group that doesn't exist"""
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        await remove_group_from_user_groups(users[0].id, 'group-3')
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == ['group-1', 'group-2']
    
    async def test_remove_from_empty_groups(self, users):
        """Test removing from empty groups doesn't error"""
        await remove_group_from_user_groups(users[0].id, 'group-1')
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == []
    
    async def test_remove_all_groups_sequentially(self, users):
        """Test removing all groups one by one"""
        await update_user_groups(users[0].id, ['group-1', 'group-2', 'group-3'])
        
        await remove_group_from_user_groups(users[0].id, 'group-1')
        await remove_group_from_user_groups(users[0].id, 'group-2')
        await remove_group_from_user_groups(users[0].id, 'group-3')
        
        groups = await fetch_user_groups(users[0].id)
        assert groups == []


@pytest.mark.asyncio
@pytest.mark.django_db
class TestConcurrentCacheOperations:
    """Test concurrent cache operations"""
    
    async def test_concurrent_adds_same_user(self, users):
        """Test concurrent add operations for same user"""
        # Add 5 groups concurrently
        await asyncio.gather(
            add_group_to_user_groups(users[0].id, 'group-1'),
            add_group_to_user_groups(users[0].id, 'group-2'),
            add_group_to_user_groups(users[0].id, 'group-3'),
            add_group_to_user_groups(users[0].id, 'group-4'),
            add_group_to_user_groups(users[0].id, 'group-5')
        )
        
        groups = await fetch_user_groups(users[0].id)
        
        # All groups should be added
        assert len(groups) == 5
        for i in range(1, 6):
            assert f'group-{i}' in groups
    
    async def test_concurrent_remove_same_user(self, users):
        """Test concurrent remove operations for same user"""
        # Setup
        await update_user_groups(users[0].id, ['group-1', 'group-2', 'group-3', 'group-4', 'group-5'])
        
        # Remove 3 groups concurrently
        await asyncio.gather(
            remove_group_from_user_groups(users[0].id, 'group-2'),
            remove_group_from_user_groups(users[0].id, 'group-4'),
            remove_group_from_user_groups(users[0].id, 'group-5')
        )
        
        groups = await fetch_user_groups(users[0].id)
        
        # Remaining groups should be 1 and 3
        assert set(groups) == {'group-1', 'group-3'}
    
    async def test_concurrent_add_remove_same_user(self, users):
        """Test concurrent add and remove operations"""
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        
        # Concurrent add and remove
        await asyncio.gather(
            add_group_to_user_groups(users[0].id, 'group-3'),
            add_group_to_user_groups(users[0].id, 'group-4'),
            remove_group_from_user_groups(users[0].id, 'group-1'),
            remove_group_from_user_groups(users[0].id, 'group-2')
        )
        
        groups = await fetch_user_groups(users[0].id)
        
        # Should have group-3 and group-4
        assert 'group-3' in groups
        assert 'group-4' in groups
    
    async def test_concurrent_operations_different_users(self, users):
        """Test concurrent operations on different users don't interfere"""
        # Each user gets different groups concurrently
        await asyncio.gather(
            update_user_groups(users[0].id, ['user0-group']),
            update_user_groups(users[1].id, ['user1-group']),
            update_user_groups(users[2].id, ['user2-group']),
            update_user_groups(users[3].id, ['user3-group'])
        )
        
        # Fetch all
        results = await asyncio.gather(
            fetch_user_groups(users[0].id),
            fetch_user_groups(users[1].id),
            fetch_user_groups(users[2].id),
            fetch_user_groups(users[3].id)
        )
        
        # Each user should have their own groups
        assert results[0] == ['user0-group']
        assert results[1] == ['user1-group']
        assert results[2] == ['user2-group']
        assert results[3] == ['user3-group']


@pytest.mark.asyncio
@pytest.mark.django_db
class TestCacheEdgeCases:
    """Test edge cases in cache operations"""
    
    async def test_special_characters_in_group_names(self, users):
        """Test that group names with special characters work"""
        special_groups = [
            'group-with-dashes',
            'group_with_underscores',
            'group:with:colons',
            'group.with.dots',
            'group{with}braces'
        ]
        
        await update_user_groups(users[0].id, special_groups)
        
        groups = await fetch_user_groups(users[0].id)
        assert set(groups) == set(special_groups)
    
    async def test_unicode_group_names(self, users):
        """Test that unicode group names work"""
        unicode_groups = ['group-测试', 'group-🎉', 'group-привет']
        
        await update_user_groups(users[0].id, unicode_groups)
        
        groups = await fetch_user_groups(users[0].id)
        assert set(groups) == set(unicode_groups)
    
    async def test_very_long_group_list(self, users):
        """Test handling very long list of groups"""
        # Create 100 groups
        many_groups = [f'group-{i}' for i in range(100)]
        
        await update_user_groups(users[0].id, many_groups)
        
        groups = await fetch_user_groups(users[0].id)
        assert len(groups) == 100
        assert set(groups) == set(many_groups)
    
    async def test_add_then_fetch_immediately(self, users):
        """Test that add is immediately reflected in fetch"""
        await add_group_to_user_groups(users[0].id, 'group-1')
        
        # Immediate fetch
        groups = await fetch_user_groups(users[0].id)
        
        assert 'group-1' in groups
    
    async def test_remove_then_fetch_immediately(self, users):
        """Test that remove is immediately reflected in fetch"""
        await update_user_groups(users[0].id, ['group-1', 'group-2'])
        await remove_group_from_user_groups(users[0].id, 'group-1')
        
        # Immediate fetch
        groups = await fetch_user_groups(users[0].id)
        
        assert 'group-1' not in groups
        assert 'group-2' in groups


@pytest.mark.asyncio
@pytest.mark.django_db
class TestCacheKeyFormat:
    """Test cache key format and isolation"""
    
    async def test_cache_keys_isolated_by_user(self, users):
        """Test that cache keys are isolated by user ID"""
        # Set same group name for different users
        await update_user_groups(users[0].id, ['shared-group'])
        await update_user_groups(users[1].id, ['shared-group'])
        
        # Each user should have their own cache entry
        groups0 = await fetch_user_groups(users[0].id)
        groups1 = await fetch_user_groups(users[1].id)
        
        assert groups0 == ['shared-group']
        assert groups1 == ['shared-group']
        
        # Remove for one user
        await remove_group_from_user_groups(users[0].id, 'shared-group')
        
        # Should only affect user 0
        groups0_after = await fetch_user_groups(users[0].id)
        groups1_after = await fetch_user_groups(users[1].id)
        
        assert groups0_after == []
        assert groups1_after == ['shared-group']
    
    async def test_user_id_types(self, users):
        """Test that both int and str user IDs work"""
        # Use int ID
        await update_user_groups(users[0].id, ['group-1'])
        
        # Use str ID
        await update_user_groups(str(users[1].id), ['group-2'])
        
        # Both should work
        groups0 = await fetch_user_groups(users[0].id)
        groups1 = await fetch_user_groups(str(users[1].id))
        
        assert groups0 == ['group-1']
        assert groups1 == ['group-2']
