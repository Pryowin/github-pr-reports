import sqlite3
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class PRStats:
    total_prs: int
    avg_age_days: float
    avg_age_days_excluding_oldest: float
    avg_comments: float
    avg_comments_with_comments: float
    approved_prs: int
    oldest_pr_age: int
    oldest_pr_title: str
    prs_with_zero_comments: int

class DatabaseManager:
    def __init__(self, db_path: str = 'pr_stats.db'):
        self.db_path = db_path
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pr_stats (
                    repo_name TEXT,
                    date TEXT,
                    total_prs INTEGER,
                    avg_age_days REAL,
                    avg_age_days_excluding_oldest REAL,
                    avg_comments REAL,
                    avg_comments_with_comments REAL,
                    approved_prs INTEGER,
                    oldest_pr_age INTEGER,
                    oldest_pr_title TEXT,
                    prs_with_zero_comments INTEGER,
                    PRIMARY KEY (repo_name, date)
                )
            ''')
            conn.commit()

    def _migrate_schema(self):
        """Add any missing columns to the database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get current columns
            cursor.execute("PRAGMA table_info(pr_stats)")
            columns = {row[1] for row in cursor.fetchall()}
            
            # Add missing columns
            if 'oldest_pr_age' not in columns:
                cursor.execute('ALTER TABLE pr_stats ADD COLUMN oldest_pr_age INTEGER DEFAULT 0')
            if 'oldest_pr_title' not in columns:
                cursor.execute('ALTER TABLE pr_stats ADD COLUMN oldest_pr_title TEXT DEFAULT ""')
            if 'avg_age_days_excluding_oldest' not in columns:
                cursor.execute('ALTER TABLE pr_stats ADD COLUMN avg_age_days_excluding_oldest REAL DEFAULT 0')
            if 'prs_with_zero_comments' not in columns:
                cursor.execute('ALTER TABLE pr_stats ADD COLUMN prs_with_zero_comments INTEGER DEFAULT 0')
            if 'avg_comments_with_comments' not in columns:
                cursor.execute('ALTER TABLE pr_stats ADD COLUMN avg_comments_with_comments REAL DEFAULT 0')
            
            conn.commit()

    def save_stats(self, repo_name: str, stats: PRStats):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pr_stats 
                (repo_name, date, total_prs, avg_age_days, avg_age_days_excluding_oldest, avg_comments, avg_comments_with_comments, approved_prs, oldest_pr_age, oldest_pr_title, prs_with_zero_comments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo_name,
                datetime.now().strftime('%Y-%m-%d'),
                stats.total_prs,
                stats.avg_age_days,
                stats.avg_age_days_excluding_oldest,
                stats.avg_comments,
                stats.avg_comments_with_comments,
                stats.approved_prs,
                stats.oldest_pr_age,
                stats.oldest_pr_title,
                stats.prs_with_zero_comments
            ))
            conn.commit()

    def get_latest_stats(self, repo_name: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, total_prs, avg_age_days, avg_age_days_excluding_oldest, avg_comments, avg_comments_with_comments, approved_prs, oldest_pr_age, oldest_pr_title, prs_with_zero_comments
                FROM pr_stats
                WHERE repo_name = ?
                ORDER BY date DESC
                LIMIT 1
            ''', (repo_name,))
            row = cursor.fetchone()
            if row:
                return {
                    'date': row[0],
                    'total_prs': row[1],
                    'avg_age_days': row[2],
                    'avg_age_days_excluding_oldest': row[3],
                    'avg_comments': row[4],
                    'avg_comments_with_comments': row[5],
                    'approved_prs': row[6],
                    'oldest_pr_age': row[7],
                    'oldest_pr_title': row[8],
                    'prs_with_zero_comments': row[9]
                }
            return None 