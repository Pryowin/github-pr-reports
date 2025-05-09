import pytest
import os
from datetime import datetime, timezone
from db_manager import DatabaseManager, PRStats

@pytest.fixture
def db_manager():
    # Use a test database file
    db_path = 'test_pr_stats.db'
    manager = DatabaseManager(db_path)
    yield manager
    # Clean up after tests
    if os.path.exists(db_path):
        os.remove(db_path)

def test_create_tables(db_manager):
    # Verify the table exists by trying to insert data
    stats = PRStats(total_prs=5, avg_age_days=2.5, avg_comments=3.0, approved_prs=2)
    db_manager.save_stats('test-repo', stats)
    
    # If we get here without an error, the table was created successfully
    assert True

def test_save_and_get_stats(db_manager):
    # Create test data
    stats = PRStats(total_prs=5, avg_age_days=2.5, avg_comments=3.0, approved_prs=2)
    repo_name = 'test-repo'
    
    # Save stats
    db_manager.save_stats(repo_name, stats)
    
    # Get latest stats
    retrieved_stats = db_manager.get_latest_stats(repo_name)
    
    # Verify the data
    assert retrieved_stats is not None
    assert retrieved_stats['total_prs'] == stats.total_prs
    assert retrieved_stats['avg_age_days'] == stats.avg_age_days
    assert retrieved_stats['avg_comments'] == stats.avg_comments
    assert retrieved_stats['approved_prs'] == stats.approved_prs
    assert retrieved_stats['date'] == datetime.now(timezone.utc).strftime('%Y-%m-%d')

def test_update_existing_stats(db_manager):
    repo_name = 'test-repo'
    
    # Save initial stats
    initial_stats = PRStats(total_prs=5, avg_age_days=2.5, avg_comments=3.0, approved_prs=2)
    db_manager.save_stats(repo_name, initial_stats)
    
    # Save updated stats for the same repo and date
    updated_stats = PRStats(total_prs=6, avg_age_days=3.0, avg_comments=4.0, approved_prs=3)
    db_manager.save_stats(repo_name, updated_stats)
    
    # Get latest stats
    retrieved_stats = db_manager.get_latest_stats(repo_name)
    
    # Verify the updated data
    assert retrieved_stats is not None
    assert retrieved_stats['total_prs'] == updated_stats.total_prs
    assert retrieved_stats['avg_age_days'] == updated_stats.avg_age_days
    assert retrieved_stats['avg_comments'] == updated_stats.avg_comments
    assert retrieved_stats['approved_prs'] == updated_stats.approved_prs

def test_get_nonexistent_stats(db_manager):
    # Try to get stats for a repo that doesn't exist
    retrieved_stats = db_manager.get_latest_stats('nonexistent-repo')
    assert retrieved_stats is None 