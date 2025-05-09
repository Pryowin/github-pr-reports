import sqlite3
from datetime import datetime, timezone
from typing import Dict
from dataclasses import dataclass

@dataclass
class PRStats:
    total_prs: int
    avg_age_days: float
    avg_comments: float
    approved_prs: int

class DatabaseManager:
    def __init__(self, db_path: str = 'pr_stats.db'):
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pr_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_prs INTEGER NOT NULL,
                    avg_age_days REAL NOT NULL,
                    avg_comments REAL NOT NULL,
                    approved_prs INTEGER NOT NULL,
                    UNIQUE(repo_name, date)
                )
            ''')
            conn.commit()

    def save_stats(self, repo_name: str, stats: PRStats):
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pr_stats 
                (repo_name, date, total_prs, avg_age_days, avg_comments, approved_prs)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                repo_name,
                current_date,
                stats.total_prs,
                stats.avg_age_days,
                stats.avg_comments,
                stats.approved_prs
            ))
            conn.commit()

    def get_latest_stats(self, repo_name: str) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT date, total_prs, avg_age_days, avg_comments, approved_prs
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
                    'approved_prs': row[4]
                }
            return None 