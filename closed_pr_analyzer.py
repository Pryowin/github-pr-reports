#!/usr/bin/env python3

import os
import argparse
from datetime import datetime, timezone, timedelta
import yaml
from github import Github, Auth
from typing import Dict, List, Any, Union
from statistics import mean, stdev
import sys

class ClosedPRAnalyzer:
    def __init__(self, config: Union[str, Dict], days: int = 28, user_login: str = None, debug: bool = False, github_client=None):
        if isinstance(config, str):
            with open(config, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config
        
        self.days = days
        self.user_login = user_login
        self.debug = debug
        
        if github_client is None:
            auth = Auth.Token(self.config['github']['auth_token'])
            self.github = Github(auth=auth)
        else:
            self.github = github_client
            
        self.org = self.github.get_organization(self.config['github']['org'])

    def _print_progress(self, message: str):
        """Print a progress message and flush to ensure immediate display."""
        print(message, end='', flush=True)

    def analyze_repo(self, repo_name: str) -> Dict:
        """Analyze closed PRs for a repository."""
        self._print_progress(f"\nAnalyzing {repo_name}... ")
        
        repo = self.org.get_repo(repo_name)
        
        # Calculate the date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=self.days)
        
        # Get all closed PRs in the date range
        prs = list(repo.get_pulls(state='closed', sort='updated', direction='desc'))
        closed_prs = []
        user_closed_prs = []
        
        if self.debug:
            print(f"\nDetailed PR Information for {repo_name}:")
            print("-" * 80)
            print(f"{'PR #':<6} {'Opened':<20} {'Closed':<20} {'Days Open':<10} {'Author Login':<30}")
            print("-" * 80)
        
        for pr in prs:
            # Skip PRs that were closed before our start date
            if pr.closed_at < start_date:
                break
                
            # Calculate how long the PR was open
            age_days = (pr.closed_at - pr.created_at).total_seconds() / (24 * 3600)
            closed_prs.append(age_days)
            
            if self.debug:
                # Handle potential None values
                pr_number = pr.number if pr.number is not None else 'N/A'
                created_at = pr.created_at.strftime('%Y-%m-%d %H:%M') if pr.created_at is not None else 'N/A'
                closed_at = pr.closed_at.strftime('%Y-%m-%d %H:%M') if pr.closed_at is not None else 'N/A'
                author_login = pr.user.login if pr.user and pr.user.login is not None else 'N/A'
                
                print(f"{pr_number:<6} {created_at:<20} {closed_at:<20} "
                      f"{age_days:.1f} days    {author_login:<30}")
            
            # If user email is specified, check if this PR was created by that user
            if self.user_login and pr.user and pr.user.login == self.user_login:
                user_closed_prs.append(age_days)
        
        if not closed_prs:
            self._print_progress("No closed PRs found in the specified period.\n")
            return {
                'repo_name': repo_name,
                'total_closed': 0,
                'avg_days_open': 0,
                'std_dev_days': 0,
                'user_total_closed': 0,
                'user_avg_days_open': 0,
                'user_std_dev_days': 0
            }
        
        self._print_progress(f"Found {len(closed_prs)} closed PRs.\n")
        
        result = {
            'repo_name': repo_name,
            'total_closed': len(closed_prs),
            'avg_days_open': mean(closed_prs),
            'std_dev_days': stdev(closed_prs) if len(closed_prs) > 1 else 0,
            'user_total_closed': len(user_closed_prs),
            'user_avg_days_open': mean(user_closed_prs) if user_closed_prs else 0,
            'user_std_dev_days': stdev(user_closed_prs) if len(user_closed_prs) > 1 else 0
        }
        
        return result

    def generate_report(self) -> Dict[str, Dict]:
        """Generate a report for all repositories."""
        report = {}
        total_repos = len(self.config['github']['repos'])
        
        for i, repo_name in enumerate(self.config['github']['repos'], 1):
            self._print_progress(f"\nProcessing repository {i}/{total_repos}: ")
            report[repo_name] = self.analyze_repo(repo_name)
            
        return report

def main():
    parser = argparse.ArgumentParser(
        description='Analyze closed PRs in GitHub repositories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Basic usage (last 28 days):
    python closed_pr_analyzer.py

  Specify number of days:
    python closed_pr_analyzer.py --days 14

  Use a different config file:
    python closed_pr_analyzer.py --config custom_config.yaml

  Track PRs by specific user:
    python closed_pr_analyzer.py --user githubusername

  Show detailed PR information:
    python closed_pr_analyzer.py --debug
'''
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=28,
        help='Number of days to look back (default: 28)'
    )
    parser.add_argument(
        '--user',
        help='GitHub username to track PRs for'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show detailed PR information'
    )
    args = parser.parse_args()

    if args.days < 1:
        parser.error("Number of days must be positive")

    config_path = os.getenv('CONFIG_PATH', args.config)
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print("Error: Invalid YAML format in config file.")
        print(f"\nYAML Error details: {e}")
        sys.exit(1)

    try:
        # Validate required fields
        if not isinstance(config, dict) or 'github' not in config:
            raise KeyError("Missing 'github' section")
        
        github_config = config['github']
        required_fields = ['org', 'auth_token', 'repos']
        missing_fields = [field for field in required_fields if field not in github_config]
        if missing_fields:
            raise KeyError(f"Missing required fields: {', '.join(missing_fields)}")
        
        if not isinstance(github_config['repos'], list):
            raise ValueError("'repos' must be a list of repository names")
        
        if not github_config['repos']:
            raise ValueError("'repos' list cannot be empty")

        analyzer = ClosedPRAnalyzer(config, days=args.days, user_login=args.user, debug=args.debug)
        report = analyzer.generate_report()

        if not args.debug:
            print("\nClosed PR Analysis Report")
            print("=" * 50)
            print(f"Period: Last {args.days} days")
            if args.user:
                print(f"Tracking user: {args.user}")
            print("=" * 50)
            
            total_closed = 0
            all_days = []
            user_total_closed = 0
            user_all_days = []
            
            for repo_name, stats in report.items():
                print(f"\nRepository: {repo_name}")
                print(f"Total Closed PRs: {stats['total_closed']}")
                if stats['total_closed'] > 0:
                    print(f"Average Days Open: {stats['avg_days_open']:.1f}")
                    print(f"Standard Deviation: {stats['std_dev_days']:.1f}")
                
                if args.user:
                    print(f"\nStatistics for {args.user}:")
                    print(f"Closed PRs: {stats['user_total_closed']}")
                    if stats['user_total_closed'] > 0:
                        print(f"Average Days Open: {stats['user_avg_days_open']:.1f}")
                        print(f"Standard Deviation: {stats['user_std_dev_days']:.1f}")
                
                total_closed += stats['total_closed']
                if stats['total_closed'] > 0:
                    all_days.extend([stats['avg_days_open']] * stats['total_closed'])
                
                user_total_closed += stats['user_total_closed']
                if stats['user_total_closed'] > 0:
                    user_all_days.extend([stats['user_avg_days_open']] * stats['user_total_closed'])
            
            print("\nOverall Statistics")
            print("-" * 50)
            print(f"Total Closed PRs: {total_closed}")
            if all_days:
                print(f"Overall Average Days Open: {mean(all_days):.1f}")
                print(f"Overall Standard Deviation: {stdev(all_days):.1f}")
            
            if args.user:
                print(f"\nOverall Statistics for {args.user}")
                print(f"Total Closed PRs: {user_total_closed}")
                if user_all_days:
                    print(f"Average Days Open: {mean(user_all_days):.1f}")
                    print(f"Standard Deviation: {stdev(user_all_days):.1f}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 