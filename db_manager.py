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
        """Initialize the database manager."""
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate_schema()

    def __del__(self):
        """Close the database connection when the object is destroyed."""
        if hasattr(self, 'conn'):
            self.conn.close()

    def _create_tables(self):
        """Create the necessary database tables if they don't exist."""
        cursor = self.conn.cursor()
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
        self.conn.commit()

    def _migrate_schema(self):
        """Migrate the database schema if needed."""
        cursor = self.conn.cursor()
        
        # Check if avg_comments_with_comments column exists
        cursor.execute("PRAGMA table_info(pr_stats)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Add missing columns
        if 'avg_age_days_excluding_oldest' not in columns:
            cursor.execute('ALTER TABLE pr_stats ADD COLUMN avg_age_days_excluding_oldest REAL DEFAULT 0')
        if 'avg_comments_with_comments' not in columns:
            cursor.execute('ALTER TABLE pr_stats ADD COLUMN avg_comments_with_comments REAL DEFAULT 0')
        if 'oldest_pr_age' not in columns:
            cursor.execute('ALTER TABLE pr_stats ADD COLUMN oldest_pr_age INTEGER DEFAULT 0')
        if 'oldest_pr_title' not in columns:
            cursor.execute('ALTER TABLE pr_stats ADD COLUMN oldest_pr_title TEXT DEFAULT ""')
        if 'prs_with_zero_comments' not in columns:
            cursor.execute('ALTER TABLE pr_stats ADD COLUMN prs_with_zero_comments INTEGER DEFAULT 0')
        
        self.conn.commit()

    def save_stats(self, repo_name: str, stats: PRStats, date: str = None) -> None:
        """Save PR statistics to the database."""
        if date is None:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO pr_stats (
                repo_name, date, total_prs, avg_age_days, 
                avg_age_days_excluding_oldest, avg_comments, 
                avg_comments_with_comments, approved_prs, 
                oldest_pr_age, oldest_pr_title, prs_with_zero_comments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            repo_name, date, stats.total_prs, stats.avg_age_days,
            stats.avg_age_days_excluding_oldest, stats.avg_comments,
            stats.avg_comments_with_comments, stats.approved_prs,
            stats.oldest_pr_age, stats.oldest_pr_title, stats.prs_with_zero_comments
        ))
        self.conn.commit()

    def get_latest_stats(self, repo_name: str) -> Optional[Dict]:
        """Get the latest statistics for a repository."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT repo_name, date, total_prs, avg_age_days, 
                   avg_age_days_excluding_oldest, avg_comments, 
                   avg_comments_with_comments, approved_prs, 
                   oldest_pr_age, oldest_pr_title, prs_with_zero_comments
            FROM pr_stats 
            WHERE repo_name = ? 
            ORDER BY date DESC 
            LIMIT 1
        """, (repo_name,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            'date': row[1],
            'total_prs': float(row[2]),
            'avg_age_days': float(row[3]),
            'avg_age_days_excluding_oldest': float(row[4]),
            'avg_comments': float(row[5]),
            'avg_comments_with_comments': float(row[6]),
            'approved_prs': float(row[7]),
            'oldest_pr_age': float(row[8]),
            'oldest_pr_title': row[9],
            'prs_with_zero_comments': float(row[10])
        }

    def get_stats_before_date(self, repo_name: str, target_date: datetime) -> Optional[Dict]:
        """Get the most recent stats before the target date."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT repo_name, date, total_prs, avg_age_days, 
                   avg_age_days_excluding_oldest, avg_comments, 
                   avg_comments_with_comments, approved_prs, 
                   oldest_pr_age, oldest_pr_title, prs_with_zero_comments
            FROM pr_stats
            WHERE repo_name = ? AND date < ?
            ORDER BY date DESC
            LIMIT 1
        """, (repo_name, target_date.strftime('%Y-%m-%d')))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            'date': row[1],
            'total_prs': float(row[2]),
            'avg_age_days': float(row[3]),
            'avg_age_days_excluding_oldest': float(row[4]),
            'avg_comments': float(row[5]),
            'avg_comments_with_comments': float(row[6]),
            'approved_prs': float(row[7]),
            'oldest_pr_age': float(row[8]),
            'oldest_pr_title': row[9],
            'prs_with_zero_comments': float(row[10])
        }

    def get_earliest_stats(self, repo_name: str) -> Optional[Dict]:
        """Get the earliest stats for a repository."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT repo_name, date, total_prs, avg_age_days, 
                   avg_age_days_excluding_oldest, avg_comments, 
                   avg_comments_with_comments, approved_prs, 
                   oldest_pr_age, oldest_pr_title, prs_with_zero_comments
            FROM pr_stats
            WHERE repo_name = ?
            ORDER BY date ASC
            LIMIT 1
        """, (repo_name,))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            'date': row[1],
            'total_prs': float(row[2]),
            'avg_age_days': float(row[3]),
            'avg_age_days_excluding_oldest': float(row[4]),
            'avg_comments': float(row[5]),
            'avg_comments_with_comments': float(row[6]),
            'approved_prs': float(row[7]),
            'oldest_pr_age': float(row[8]),
            'oldest_pr_title': row[9],
            'prs_with_zero_comments': float(row[10])
        }

    def get_stats_in_date_range(self, repo_name: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get all stats for a repository within a date range."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT repo_name, date, total_prs, avg_age_days, 
                   avg_age_days_excluding_oldest, avg_comments, 
                   avg_comments_with_comments, approved_prs, 
                   oldest_pr_age, oldest_pr_title, prs_with_zero_comments
            FROM pr_stats 
            WHERE repo_name = ? 
            AND date BETWEEN ? AND ?
            ORDER BY date ASC
        """, (repo_name, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        
        rows = cursor.fetchall()
        stats_list = []
        for row in rows:
            stats = {
                'date': row[1],
                'total_prs': float(row[2]),
                'avg_age_days': float(row[3]),
                'avg_age_days_excluding_oldest': float(row[4]),
                'avg_comments': float(row[5]),
                'avg_comments_with_comments': float(row[6]),
                'approved_prs': float(row[7]),
                'oldest_pr_age': float(row[8]),
                'oldest_pr_title': row[9],
                'prs_with_zero_comments': float(row[10])
            }
            stats_list.append(stats)
        return stats_list

    def get_stats_for_date(self, repo_name: str, date: str) -> Optional[Dict]:
        """Get stats for a specific repository and date."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT repo_name, date, total_prs, avg_age_days, 
                   avg_age_days_excluding_oldest, avg_comments, 
                   avg_comments_with_comments, approved_prs, 
                   oldest_pr_age, oldest_pr_title, prs_with_zero_comments
            FROM pr_stats 
            WHERE repo_name = ? 
            AND date = ?
        """, (repo_name, date))
        
        row = cursor.fetchone()
        if not row:
            return None
            
        return {
            'date': row[1],
            'total_prs': float(row[2]),
            'avg_age_days': float(row[3]),
            'avg_age_days_excluding_oldest': float(row[4]),
            'avg_comments': float(row[5]),
            'avg_comments_with_comments': float(row[6]),
            'approved_prs': float(row[7]),
            'oldest_pr_age': float(row[8]),
            'oldest_pr_title': row[9],
            'prs_with_zero_comments': float(row[10])
        } 