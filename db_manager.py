import sqlite3
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass

@dataclass
class PRStats:
    total_prs: int
    avg_age_days: float
    avg_comments: float
    approved_prs: int
    oldest_pr_age: int
    oldest_pr_title: str

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
                    avg_comments REAL,
                    approved_prs INTEGER,
                    oldest_pr_age INTEGER,
                    oldest_pr_title TEXT,
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
            
            conn.commit()

    def save_stats(self, repo_name: str, stats: PRStats):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pr_stats 
                (repo_name, date, total_prs, avg_age_days, avg_comments, approved_prs, oldest_pr_age, oldest_pr_title)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                repo_name,
                datetime.now().strftime('%Y-%m-%d'),
                stats.total_prs,
                stats.avg_age_days,
                stats.avg_comments,
                stats.approved_prs,
                stats.oldest_pr_age,
                stats.oldest_pr_title
            ))
            conn.commit()

    def get_latest_stats(self, repo_name: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, total_prs, avg_age_days, avg_comments, approved_prs, oldest_pr_age, oldest_pr_title
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
                    'avg_comments': row[3],
                    'approved_prs': row[4],
                    'oldest_pr_age': row[5],
                    'oldest_pr_title': row[6]
                }
            return None 