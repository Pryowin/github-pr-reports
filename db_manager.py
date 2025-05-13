import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional
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
        self._init_db()
        self._migrate_schema()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pr_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_prs INTEGER NOT NULL,
                    avg_age_days REAL NOT NULL,
                    avg_age_days_excluding_oldest REAL NOT NULL,
                    avg_comments REAL NOT NULL,
                    avg_comments_with_comments REAL NOT NULL,
                    approved_prs INTEGER NOT NULL,
                    oldest_pr_age INTEGER NOT NULL,
                    oldest_pr_title TEXT NOT NULL,
                    prs_with_zero_comments INTEGER NOT NULL,
                    UNIQUE(repo_name, date)
                )
            ''')

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

    def save_stats(self, repo_name: str, stats: Dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO pr_stats (
                    repo_name, date, total_prs, avg_age_days,
                    avg_age_days_excluding_oldest, avg_comments,
                    avg_comments_with_comments, approved_prs,
                    oldest_pr_age, oldest_pr_title, prs_with_zero_comments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo_name,
                datetime.now(timezone.utc).strftime('%Y-%m-%d'),
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

    def get_latest_stats(self, repo_name: str) -> Optional[Dict]:
        """Get the most recent stats for a repository."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT date, total_prs, avg_age_days, avg_age_days_excluding_oldest,
                       avg_comments, avg_comments_with_comments, approved_prs,
                       oldest_pr_age, oldest_pr_title, prs_with_zero_comments
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

    def get_stats_before_date(self, repo_name: str, target_date: datetime) -> Optional[Dict]:
        """Get the most recent stats before the target date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT date, total_prs, avg_age_days, avg_age_days_excluding_oldest,
                       avg_comments, avg_comments_with_comments, approved_prs,
                       oldest_pr_age, oldest_pr_title, prs_with_zero_comments
                FROM pr_stats
                WHERE repo_name = ? AND date < ?
                ORDER BY date DESC
                LIMIT 1
            ''', (repo_name, target_date.strftime('%Y-%m-%d')))
            
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

    def get_earliest_stats(self, repo_name: str) -> Optional[Dict]:
        """Get the earliest stats for a repository."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT date, total_prs, avg_age_days, avg_age_days_excluding_oldest,
                       avg_comments, avg_comments_with_comments, approved_prs,
                       oldest_pr_age, oldest_pr_title, prs_with_zero_comments
                FROM pr_stats
                WHERE repo_name = ?
                ORDER BY date ASC
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

    def get_stats_in_date_range(self, repo_name: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all stats for a repository within a date range."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, total_prs, avg_age_days, avg_age_days_excluding_oldest,
                       avg_comments, avg_comments_with_comments, approved_prs,
                       oldest_pr_age, oldest_pr_title, prs_with_zero_comments
                FROM pr_stats
                WHERE repo_name = ? AND date BETWEEN ? AND ?
                ORDER BY date ASC
            """, (repo_name, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
            
            rows = cursor.fetchall()
            if not rows:
                return []
            
            return [{
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
            } for row in rows] 