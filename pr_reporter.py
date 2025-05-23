#!/usr/bin/env python3

import os
import argparse
from datetime import datetime, timezone, timedelta
import yaml
from github import Github, Auth
from typing import Dict, List, Any, Union, NamedTuple
from dataclasses import dataclass
from statistics import mean
from db_manager import DatabaseManager, PRStats
import sys
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates

# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    WHITE = '\033[0m'
    RESET = '\033[0m'

class PRDetail(NamedTuple):
    title: str
    age_days: int
    url: str

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
    reopened_prs: int
    # Not stored in DB, only used in verbose mode
    zero_comment_prs: List[PRDetail] = None

class PRReporter:
    def __init__(self, config: Union[str, Dict], verbose: bool = False, min_age_days: int = 0, compare_days: int = None, github_client=None, dbonly: bool = False):
        if isinstance(config, str):
            with open(config, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config
        
        self.verbose = verbose
        self.min_age_days = min_age_days
        self.compare_days = compare_days
        self.dbonly = dbonly
        
        if not dbonly:
            if github_client is None:
                auth = Auth.Token(self.config['github']['auth_token'])
                self.github = Github(auth=auth)
            else:
                self.github = github_client
                
            self.org = self.github.get_organization(self.config['github']['org'])
        
        self.db = DatabaseManager()

    def _print_progress(self, message: str):
        """Print a progress message and flush to ensure immediate display."""
        print(message, end='', flush=True)

    def _format_comparison(self, current: float, previous: float, format_str: str = "{:.1f}") -> str:
        """Format a value with comparison to previous value, using color coding."""
        # Ensure both values are float for comparison
        current = float(current)
        previous = float(previous)
        
        if current > previous:
            return f"{Colors.RED}{format_str.format(current)}{Colors.RESET} ({format_str.format(previous)})"
        elif current < previous:
            return f"{Colors.GREEN}{format_str.format(current)}{Colors.RESET} ({format_str.format(previous)})"
        else:
            return format_str.format(current)

    def _get_comparison_stats(self, repo_name: str) -> Dict:
        """Get stats from the specified number of days ago."""
        if not self.compare_days:
            return None

        target_date = datetime.now(timezone.utc) - timedelta(days=self.compare_days)
        stats = self.db.get_stats_before_date(repo_name, target_date)
        
        if not stats:
            # If no stats found before target date, get the earliest stats
            stats = self.db.get_earliest_stats(repo_name)
            
        if stats:
            # Convert numeric values to float
            for key in ['total_prs', 'avg_age_days', 'avg_age_days_excluding_oldest', 
                       'avg_comments', 'avg_comments_with_comments', 'approved_prs', 
                       'oldest_pr_age', 'prs_with_zero_comments', 'reopened_prs']:
                if key in stats:
                    stats[key] = float(stats[key])
            
        return stats

    def get_repo_stats(self, repo_name: str) -> PRStats:
        """Get statistics for a repository, either from API or database."""
        self._print_progress(f"\nAnalyzing {repo_name}... ")
        
        if self.dbonly:
            # Get today's stats from database
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            stats = self.db.get_stats_for_date(repo_name, today)
            if not stats:
                raise ValueError(f"No data found in database for {repo_name} on {today}. Please run without --dbonly to fetch fresh data.")
            return PRStats(
                total_prs=int(stats['total_prs']),
                avg_age_days=float(stats['avg_age_days']),
                avg_age_days_excluding_oldest=float(stats['avg_age_days_excluding_oldest']),
                avg_comments=float(stats['avg_comments']),
                avg_comments_with_comments=float(stats['avg_comments_with_comments']),
                approved_prs=int(stats['approved_prs']),
                oldest_pr_age=int(stats['oldest_pr_age']),
                oldest_pr_title=str(stats['oldest_pr_title']),
                prs_with_zero_comments=int(stats['prs_with_zero_comments']),
                reopened_prs=int(stats.get('reopened_prs', 0)),
                zero_comment_prs=[]  # Not stored in DB
            )

        # Regular API-based flow
        repo = self.org.get_repo(repo_name)
        prs = list(repo.get_pulls(state='open'))
        
        if not prs:
            self._print_progress("No open PRs found.\n")
            stats = PRStats(
                total_prs=0,
                avg_age_days=0,
                avg_age_days_excluding_oldest=0,
                avg_comments=0,
                avg_comments_with_comments=0,
                approved_prs=0,
                oldest_pr_age=0,
                oldest_pr_title="",
                prs_with_zero_comments=0,
                reopened_prs=0,
                zero_comment_prs=[]
            )
            self.db.save_stats(repo_name, stats)
            return stats

        self._print_progress(f"Found {len(prs)} PRs. Analyzing...\n")
        ages = []
        comments = []
        comments_with_comments = []  # Only PRs that have comments
        approved = 0
        oldest_pr_age = 0
        oldest_pr_title = ""
        prs_with_zero_comments = 0
        zero_comment_prs = []
        reopened_count = 0

        for i, pr in enumerate(prs, 1):
            self._print_progress(f"\rProcessing PR {i}/{len(prs)}... ")
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
            comment_count = pr.comments
            comments.append(comment_count)
            
            # Check if PR has "Ready for Review" label
            has_ready_label = any(label.name == "Ready for Review" for label in pr.labels)
            
            if comment_count == 0:
                prs_with_zero_comments += 1
                if self.verbose and age_days >= self.min_age_days and has_ready_label:
                    zero_comment_prs.append(PRDetail(pr.title, age_days, pr.html_url))
            else:
                comments_with_comments.append(comment_count)
            
            # Check if PR is approved
            reviews = pr.get_reviews()
            if any(review.state == 'APPROVED' for review in reviews):
                approved += 1
            
            # Check if PR has been reopened by looking at timeline events
            try:
                timeline = pr.get_issue_events()
                for event in timeline:
                    if hasattr(event, 'event') and event.event == 'reopened':
                        reopened_count += 1
                        break  # Only count once per PR
            except Exception:
                # If we can't get timeline events, skip reopened count for this PR
                pass

        # Calculate average excluding oldest PR
        if len(ages) > 1:
            # If we have multiple PRs, exclude the oldest one
            ages_excluding_oldest = [age for age in ages if age < oldest_pr_age]
            avg_age_excluding_oldest = mean(ages_excluding_oldest) if ages_excluding_oldest else 0
        else:
            # If we only have one PR, it's both the oldest and the only one
            avg_age_excluding_oldest = 0

        stats = PRStats(
            total_prs=len(prs),
            avg_age_days=mean(ages) if ages else 0,
            avg_age_days_excluding_oldest=avg_age_excluding_oldest,
            avg_comments=mean(comments) if comments else 0,
            avg_comments_with_comments=mean(comments_with_comments) if comments_with_comments else 0,
            approved_prs=approved,
            oldest_pr_age=oldest_pr_age,
            oldest_pr_title=oldest_pr_title,
            prs_with_zero_comments=prs_with_zero_comments,
            reopened_prs=reopened_count,
            zero_comment_prs=sorted(zero_comment_prs, key=lambda x: x.age_days, reverse=True) if self.verbose else None
        )
        self.db.save_stats(repo_name, stats)
        self._print_progress("Done!\n")
        return stats

    def generate_report(self) -> Dict[str, PRStats]:
        report = {}
        total_repos = len(self.config['github']['repos'])
        for i, repo_name in enumerate(self.config['github']['repos'], 1):
            self._print_progress(f"\nProcessing repository {i}/{total_repos}: ")
            report[repo_name] = self.get_repo_stats(repo_name)
        return report

    def generate_graph(self, days: int = 30, repo_name: str = None) -> None:
        """Generate a line graph showing PR trends for each repository."""
        if repo_name and repo_name not in self.config['github']['repos']:
            raise ValueError(f"Repository '{repo_name}' not found in config. Available repositories: {', '.join(self.config['github']['repos'])}")

        plt.figure(figsize=(12, 6))
        
        # Get the date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Get data for each repository
        repos_to_graph = [repo_name] if repo_name else self.config['github']['repos']
        
        for repo in repos_to_graph:
            # Get all stats for this repo within the date range
            stats = self.db.get_stats_in_date_range(repo, start_date, end_date)
            
            if not stats:
                continue
                
            # Extract dates and PR counts
            dates = [datetime.strptime(stat['date'], '%Y-%m-%d') for stat in stats]
            pr_counts = [stat['total_prs'] for stat in stats]
            
            # Plot the line
            plt.plot(dates, pr_counts, marker='o', label=repo)
        
        # Customize the graph
        title = f'Open PRs Trend for {repo_name}' if repo_name else 'Open PRs Trend'
        plt.title(title)
        plt.xlabel('Date')
        plt.ylabel('Number of Open PRs')
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
        plt.gcf().autofmt_xdate()  # Rotate date labels
        
        # Add legend
        plt.legend()
        
        # Adjust layout
        plt.tight_layout()
        
        # Create graphs directory if it doesn't exist
        graphs_dir = 'graphs'
        os.makedirs(graphs_dir, exist_ok=True)
        
        # Generate filename based on repo, date range, and current date
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        base_name = f"{repo_name}_pr_trends" if repo_name else "all_repos_pr_trends"
        filename = f"{base_name}_{current_date}.png"
        filepath = os.path.join(graphs_dir, filename)
        
        # Save the graph
        plt.savefig(filepath)
        plt.close()
        
        return filepath  # Return the path where the graph was saved

def main():
    # Clear console
    # Note: Windows console clearing functionality (cls) is untested
    os.system('cls' if os.name == 'nt' else 'clear')
    
    parser = argparse.ArgumentParser(
        description='Generate GitHub PR statistics report',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Basic usage:
    python pr_reporter.py

  Show all PRs with no comments:
    python pr_reporter.py -v

  Show PRs with no comments that are at least 5 days old:
    python pr_reporter.py -v --min-age 5

  Compare with stats from 7 days ago:
    python pr_reporter.py --compare

  Compare with stats from specific number of days ago:
    python pr_reporter.py --compare 14

  Generate a line graph showing PR trends:
    python pr_reporter.py --graph

  Generate a line graph for the last 60 days:
    python pr_reporter.py --graph --days 60

  Use a different config file:
    python pr_reporter.py --config custom_config.yaml
'''
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed information about PRs with no comments, including their titles and URLs'
    )
    parser.add_argument(
        '--min-age',
        type=int,
        default=0,
        help='Minimum age in days for PRs to show in verbose mode. Only PRs with no comments that have been open for at least this many days will be shown. (default: 0)'
    )
    parser.add_argument(
        '--compare',
        nargs='?',
        const=7,
        type=int,
        help='Compare current stats with stats from specified number of days ago (default: 7)'
    )
    parser.add_argument(
        '--graph',
        action='store_true',
        help='Generate a line graph showing PR trends over time. Uses only historical data from the database.'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to show in the graph (default: 30). Only used with --graph option.'
    )
    parser.add_argument(
        '--repo',
        type=str,
        help='Specific repository to graph. Only used with --graph option. If not specified, all repositories will be graphed.'
    )
    parser.add_argument(
        '--dbonly',
        action='store_true',
        help='Use only database values, do not make API calls. Will show an error if no data exists for current date.'
    )
    args = parser.parse_args()

    if args.min_age < 0:
        parser.error("Minimum age must be a non-negative integer")

    if args.compare is not None and args.compare < 0:
        parser.error("Comparison days must be a non-negative integer")

    if args.repo and not args.graph:
        parser.error("--repo can only be used with --graph")

    config_path = os.getenv('CONFIG_PATH', args.config)
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        print("\nPlease create a config.yaml file with your GitHub settings:")
        print("""
github:
  org: your-org-name
  auth_token: your-github-token
  repos:
    - repo1
    - repo2
""")
        sys.exit(1)

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print("Error: Invalid YAML format in config file.")
        print("\nCommon YAML formatting issues:")
        print("1. Incorrect indentation")
        print("2. Missing colons after keys")
        print("3. Missing dashes for list items")
        print("\nYour config file should look like this:")
        print("""
github:
  org: your-org-name
  auth_token: your-github-token
  repos:
    - repo1
    - repo2
""")
        print(f"\nYAML Error details: {e}")
        sys.exit(1)

    # Move repository validation here, after config is loaded
    if args.repo and args.repo not in config['github']['repos']:
        parser.error(f"Repository '{args.repo}' not found in config. Available repositories: {', '.join(config['github']['repos'])}")

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

        # Initialize GitHub client to validate token and org
        auth = Auth.Token(github_config['auth_token'])
        github = Github(auth=auth)
        
        try:
            org = github.get_organization(github_config['org'])
        except Exception as e:
            if "Not Found" in str(e):
                print(f"Error: Organization '{github_config['org']}' not found on GitHub")
                print("\nPlease check:")
                print("1. The organization name is spelled correctly")
                print("2. You have access to the organization")
                print("3. The organization exists")
                sys.exit(1)
            elif "Bad credentials" in str(e):
                print("Error: Invalid GitHub authentication token")
                print("\nPlease check:")
                print("1. The token is correct and hasn't expired")
                print("2. The token has the necessary permissions:")
                print("   - repo (Full control of private repositories)")
                print("   - read:org (Read organization data)")
                print("\nYou can create a new token at: https://github.com/settings/tokens")
                sys.exit(1)
            else:
                raise

        # Validate repositories
        invalid_repos = []
        for repo_name in github_config['repos']:
            try:
                org.get_repo(repo_name)
            except Exception:
                invalid_repos.append(repo_name)
        
        if invalid_repos:
            print(f"Error: The following repositories were not found in organization '{github_config['org']}':")
            for repo in invalid_repos:
                print(f"  - {repo}")
            print("\nPlease check:")
            print("1. The repository names are spelled correctly")
            print("2. The repositories exist in the organization")
            print("3. You have access to these repositories")
            sys.exit(1)

        reporter = PRReporter(config, verbose=args.verbose, min_age_days=args.min_age, compare_days=args.compare, dbonly=args.dbonly)
        
        if args.graph:
            # Generate graph without running API queries
            graph_path = reporter.generate_graph(days=args.days, repo_name=args.repo)
            print(f"\nGraph has been saved as '{graph_path}'")
            return  # Exit after generating graph
        
        # Generate report as usual
        report = reporter.generate_report()

        print("\nGitHub PR Report")
        print("=" * 50)
        
        for repo_name, stats in report.items():
            print(f"\nRepository: {repo_name}")
            
            # Get comparison stats if compare is enabled
            comparison_stats = reporter._get_comparison_stats(repo_name) if args.compare is not None else None
            
            # Print stats with comparison if available
            if comparison_stats:
                print(f"Total Open PRs: {reporter._format_comparison(stats.total_prs, comparison_stats['total_prs'], '{:.0f}')}")
                print(f"Average PR Age: {reporter._format_comparison(stats.avg_age_days, comparison_stats['avg_age_days'])} days")
                print(f"Average PR Age (excluding oldest): {reporter._format_comparison(stats.avg_age_days_excluding_oldest, comparison_stats['avg_age_days_excluding_oldest'])} days")
                print(f"Average Comments per PR: {reporter._format_comparison(stats.avg_comments, comparison_stats['avg_comments'])}")
                print(f"Average Comments (PRs with comments): {reporter._format_comparison(stats.avg_comments_with_comments, comparison_stats['avg_comments_with_comments'])}")
                print(f"PRs with Zero Comments: {reporter._format_comparison(stats.prs_with_zero_comments, comparison_stats['prs_with_zero_comments'], '{:.0f}')}")
                print(f"Approved PRs: {reporter._format_comparison(stats.approved_prs, comparison_stats['approved_prs'], '{:.0f}')}")
                print(f"Reopened PRs: {reporter._format_comparison(stats.reopened_prs, comparison_stats.get('reopened_prs', 0), '{:.0f}')}")
                print(f"\nComparison date: {comparison_stats['date']}")
            else:
                print(f"Total Open PRs: {stats.total_prs}")
                print(f"Average PR Age: {stats.avg_age_days:.1f} days")
                print(f"Average PR Age (excluding oldest): {stats.avg_age_days_excluding_oldest:.1f} days")
                print(f"Average Comments per PR: {stats.avg_comments:.1f}")
                print(f"Average Comments (PRs with comments): {stats.avg_comments_with_comments:.1f}")
                print(f"PRs with Zero Comments: {stats.prs_with_zero_comments}")
                print(f"Approved PRs: {stats.approved_prs}")
                print(f"Reopened PRs: {stats.reopened_prs}")

            if stats.oldest_pr_age > 0:
                print(f"Oldest PR: {stats.oldest_pr_title} ({stats.oldest_pr_age} days old)")

            # In verbose mode, show details of PRs with no comments
            if args.verbose and stats.zero_comment_prs:
                print("\nPRs with no comments:")
                if args.min_age > 0:
                    print(f"(showing only PRs open for at least {args.min_age} days)")
                for pr in stats.zero_comment_prs:
                    print(f"  - [{pr.age_days} days] {pr.title}")
                    print(f"    {pr.url}")

            # Show previous stats if available
            prev_stats = reporter.db.get_latest_stats(repo_name)
            if prev_stats and prev_stats['date'] != datetime.now(timezone.utc).strftime('%Y-%m-%d'):
                print("\nPrevious Stats (from {})".format(prev_stats['date']))
                print(f"Total Open PRs: {prev_stats['total_prs']}")
                print(f"Average PR Age: {prev_stats['avg_age_days']:.1f} days")
                print(f"Average PR Age (excluding oldest): {prev_stats['avg_age_days_excluding_oldest']:.1f} days")
                print(f"Average Comments per PR: {prev_stats['avg_comments']:.1f}")
                print(f"Average Comments (PRs with comments): {prev_stats['avg_comments_with_comments']:.1f}")
                print(f"PRs with Zero Comments: {prev_stats['prs_with_zero_comments']}")
                print(f"Approved PRs: {prev_stats['approved_prs']}")
                print(f"Reopened PRs: {prev_stats.get('reopened_prs', 0)}")
                if prev_stats['oldest_pr_age'] > 0:
                    print(f"Oldest PR: {prev_stats['oldest_pr_title']} ({prev_stats['oldest_pr_age']} days old)")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 