#!/usr/bin/env python3

import os
from datetime import datetime, timezone
import yaml
from github import Github, Auth
from typing import Dict, List, Any, Union
from dataclasses import dataclass
from statistics import mean
from db_manager import DatabaseManager, PRStats

@dataclass
class PRStats:
    total_prs: int
    avg_age_days: float
    avg_comments: float
    approved_prs: int
    oldest_pr_age: int
    oldest_pr_title: str

class PRReporter:
    def __init__(self, config: Union[str, Dict], github_client=None):
        if isinstance(config, str):
            with open(config, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config
        
        if github_client is None:
            auth = Auth.Token(self.config['github']['auth_token'])
            self.github = Github(auth=auth)
        else:
            self.github = github_client
            
        self.org = self.github.get_organization(self.config['github']['org'])
        self.db = DatabaseManager()

    def get_repo_stats(self, repo_name: str) -> PRStats:
        repo = self.org.get_repo(repo_name)
        prs = list(repo.get_pulls(state='open'))
        
        if not prs:
            stats = PRStats(0, 0, 0, 0, 0, "")
            self.db.save_stats(repo_name, stats)
            return stats

        ages = []
        comments = []
        approved = 0
        oldest_pr_age = 0
        oldest_pr_title = ""

        for pr in prs:
            # Calculate age in days
            created_at = pr.created_at
            now = datetime.now(timezone.utc)
            age_days = (now - created_at).days
            ages.append(age_days)
            
            # Track oldest PR
            if age_days > oldest_pr_age:
                oldest_pr_age = age_days
                oldest_pr_title = pr.title
            
            # Get number of comments
            comments.append(pr.comments)
            
            # Check if PR is approved
            reviews = pr.get_reviews()
            if any(review.state == 'APPROVED' for review in reviews):
                approved += 1

        stats = PRStats(
            total_prs=len(prs),
            avg_age_days=mean(ages) if ages else 0,
            avg_comments=mean(comments) if comments else 0,
            approved_prs=approved,
            oldest_pr_age=oldest_pr_age,
            oldest_pr_title=oldest_pr_title
        )
        self.db.save_stats(repo_name, stats)
        return stats

    def generate_report(self) -> Dict[str, PRStats]:
        report = {}
        for repo_name in self.config['github']['repos']:
            report[repo_name] = self.get_repo_stats(repo_name)
        return report

def main():
    config_path = os.getenv('CONFIG_PATH', 'config.yaml')
    reporter = PRReporter(config_path)
    report = reporter.generate_report()

    print("\nGitHub PR Report")
    print("=" * 50)
    
    for repo_name, stats in report.items():
        print(f"\nRepository: {repo_name}")
        print(f"Total Open PRs: {stats.total_prs}")
        print(f"Average PR Age: {stats.avg_age_days:.1f} days")
        print(f"Average Comments per PR: {stats.avg_comments:.1f}")
        print(f"Approved PRs: {stats.approved_prs}")
        if stats.oldest_pr_age > 0:
            print(f"Oldest PR: {stats.oldest_pr_title} ({stats.oldest_pr_age} days old)")

        # Show previous stats if available
        prev_stats = reporter.db.get_latest_stats(repo_name)
        if prev_stats and prev_stats['date'] != datetime.now(timezone.utc).strftime('%Y-%m-%d'):
            print("\nPrevious Stats (from {})".format(prev_stats['date']))
            print(f"Total Open PRs: {prev_stats['total_prs']}")
            print(f"Average PR Age: {prev_stats['avg_age_days']:.1f} days")
            print(f"Average Comments per PR: {prev_stats['avg_comments']:.1f}")
            print(f"Approved PRs: {prev_stats['approved_prs']}")
            if prev_stats['oldest_pr_age'] > 0:
                print(f"Oldest PR: {prev_stats['oldest_pr_title']} ({prev_stats['oldest_pr_age']} days old)")

if __name__ == "__main__":
    main() 