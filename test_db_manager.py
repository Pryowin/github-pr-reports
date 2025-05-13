import pytest
import os
from datetime import datetime, timezone
from db_manager import DatabaseManager, PRStats
import sqlite3

@pytest.fixture
def db_manager():
    # Use a test database file
    test_db_path = 'test_pr_stats.db'
    manager = DatabaseManager(test_db_path)
    yield manager
    # Clean up after tests
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

def test_create_tables(db_manager):
    # Verify the table exists by trying to insert data
    stats = PRStats(
        total_prs=5,
        avg_age_days=2.5,
        avg_age_days_excluding_oldest=2.0,
        avg_comments=3.0,
        avg_comments_with_comments=4.0,
        approved_prs=2,
        oldest_pr_age=10,
        oldest_pr_title="Test PR",
        prs_with_zero_comments=1
    )
    db_manager.save_stats('test-repo', stats)
    
    # Verify we can retrieve the data
    result = db_manager.get_latest_stats('test-repo')
    assert result is not None
    assert result['total_prs'] == 5
    assert result['avg_age_days'] == 2.5
    assert result['avg_age_days_excluding_oldest'] == 2.0
    assert result['avg_comments'] == 3.0
    assert result['avg_comments_with_comments'] == 4.0
    assert result['approved_prs'] == 2
    assert result['oldest_pr_age'] == 10
    assert result['oldest_pr_title'] == "Test PR"
    assert result['prs_with_zero_comments'] == 1

def test_save_and_get_stats(db_manager):
    # Create test data
    stats = PRStats(
        total_prs=5,
        avg_age_days=2.5,
        avg_age_days_excluding_oldest=2.0,
        avg_comments=3.0,
        avg_comments_with_comments=4.0,
        approved_prs=2,
        oldest_pr_age=10,
        oldest_pr_title="Test PR",
        prs_with_zero_comments=1
    )
    
    # Save stats
    db_manager.save_stats('test-repo', stats)
    
    # Retrieve stats
    result = db_manager.get_latest_stats('test-repo')
    
    # Verify the data
    assert result is not None
    assert result['total_prs'] == 5
    assert result['avg_age_days'] == 2.5
    assert result['avg_age_days_excluding_oldest'] == 2.0
    assert result['avg_comments'] == 3.0
    assert result['avg_comments_with_comments'] == 4.0
    assert result['approved_prs'] == 2
    assert result['oldest_pr_age'] == 10
    assert result['oldest_pr_title'] == "Test PR"
    assert result['prs_with_zero_comments'] == 1

def test_update_existing_stats(db_manager):
    repo_name = 'test-repo'
    
    # Save initial stats
    initial_stats = PRStats(
        total_prs=5,
        avg_age_days=2.5,
        avg_age_days_excluding_oldest=2.0,
        avg_comments=3.0,
        avg_comments_with_comments=4.0,
        approved_prs=2,
        oldest_pr_age=10,
        oldest_pr_title="Test PR",
        prs_with_zero_comments=1
    )
    db_manager.save_stats(repo_name, initial_stats)
    
    # Update stats
    updated_stats = PRStats(
        total_prs=6,
        avg_age_days=3.0,
        avg_age_days_excluding_oldest=2.5,
        avg_comments=4.0,
        avg_comments_with_comments=5.0,
        approved_prs=3,
        oldest_pr_age=15,
        oldest_pr_title="Updated PR",
        prs_with_zero_comments=2
    )
    db_manager.save_stats(repo_name, updated_stats)
    
    # Verify the update
    result = db_manager.get_latest_stats(repo_name)
    assert result is not None
    assert result['total_prs'] == 6
    assert result['avg_age_days'] == 3.0
    assert result['avg_age_days_excluding_oldest'] == 2.5
    assert result['avg_comments'] == 4.0
    assert result['avg_comments_with_comments'] == 5.0
    assert result['approved_prs'] == 3
    assert result['oldest_pr_age'] == 15
    assert result['oldest_pr_title'] == "Updated PR"
    assert result['prs_with_zero_comments'] == 2

def test_schema_migration(db_manager):
    # Create a table with old schema
    with sqlite3.connect(db_manager.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DROP TABLE IF EXISTS pr_stats
        ''')
        cursor.execute('''
            CREATE TABLE pr_stats (
                repo_name TEXT,
                date TEXT,
                total_prs INTEGER,
                avg_age_days REAL,
                avg_comments REAL,
                approved_prs INTEGER,
                PRIMARY KEY (repo_name, date)
            )
        ''')
        conn.commit()

    # Insert data with old schema
    with sqlite3.connect(db_manager.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO pr_stats 
            (repo_name, date, total_prs, avg_age_days, avg_comments, approved_prs)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('test-repo', '2024-03-20', 5, 2.5, 3.0, 2))
        conn.commit()

    # Run migration
    db_manager._migrate_schema()

    # Verify new columns exist and have default values
    with sqlite3.connect(db_manager.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT repo_name, date, total_prs, avg_age_days, avg_age_days_excluding_oldest,
                   avg_comments, avg_comments_with_comments, approved_prs, oldest_pr_age,
                   oldest_pr_title, prs_with_zero_comments
            FROM pr_stats 
            WHERE repo_name = 'test-repo'
        ''')
        row = cursor.fetchone()
        assert row is not None
        assert len(row) == 11  # Should now have 11 columns
        assert row[4] == 0  # avg_age_days_excluding_oldest default value
        assert row[6] == 0.0  # avg_comments_with_comments default value
        assert row[8] == 0  # oldest_pr_age default value
        assert row[9] == ""  # oldest_pr_title default value
        assert row[10] == 0  # prs_with_zero_comments default value

def test_get_nonexistent_stats(db_manager):
    result = db_manager.get_latest_stats('nonexistent-repo')
    assert result is None

def test_get_stats_for_date():
    db = DatabaseManager()
    
    # Create test data
    test_stats = PRStats(
        total_prs=5,
        avg_age_days=7.2,
        avg_age_days_excluding_oldest=5.1,
        avg_comments=3.4,
        avg_comments_with_comments=4.2,
        approved_prs=1,
        oldest_pr_age=15,
        oldest_pr_title='Test PR',
        prs_with_zero_comments=2
    )
    
    # Save stats for a specific date
    test_date = '2024-03-21'
    db.save_stats('test-repo', test_stats, test_date)
    
    # Get stats for that date
    stats = db.get_stats_for_date('test-repo', test_date)
    assert stats is not None
    assert stats['total_prs'] == 5
    assert stats['avg_age_days'] == 7.2
    assert stats['avg_comments'] == 3.4
    assert stats['approved_prs'] == 1
    
    # Test with non-existent date
    stats = db.get_stats_for_date('test-repo', '2024-03-22')
    assert stats is None
    
    # Test with non-existent repo
    stats = db.get_stats_for_date('nonexistent-repo', test_date)
    assert stats is None 