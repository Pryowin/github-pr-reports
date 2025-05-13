# GitHub PR Reporter

A tool to generate reports about open Pull Requests in GitHub repositories.

## Features

- Track open PRs across multiple repositories
- Calculate statistics like average PR age, comment counts, and more
- Compare current stats with historical data
- Generate line graphs showing PR trends over time
- Store historical data in a SQLite database

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Create a `config.yaml` file with your GitHub settings:

```yaml
github:
  org: your-org-name
  auth_token: your-github-token
  repos:
    - repo1
    - repo2
```

## Usage

Basic usage:
```bash
python pr_reporter.py
```

Show all PRs with no comments:
```bash
python pr_reporter.py -v
```

Show PRs with no comments that are at least 5 days old:
```bash
python pr_reporter.py -v --min-age 5
```

Compare with stats from 7 days ago:
```bash
python pr_reporter.py --compare
```

Compare with stats from specific number of days ago:
```bash
python pr_reporter.py --compare 14
```

Generate a line graph showing PR trends:
```bash
python pr_reporter.py --graph
```

Generate a line graph for a specific repository:
```bash
python pr_reporter.py --graph --repo repo1
```

Generate a line graph for the last 60 days:
```bash
python pr_reporter.py --graph --days 60
```

Generate a line graph for a specific repository over the last 60 days:
```bash
python pr_reporter.py --graph --repo repo1 --days 60
```

Use a different config file:
```bash
python pr_reporter.py --config custom_config.yaml
```

## Graph Generation

The `--graph` option generates a line graph showing the trend of open PRs over time. The graph:
- Shows a separate line for each repository (or just one line if `--repo` is specified)
- Displays the number of open PRs on the y-axis
- Shows dates on the x-axis
- Includes markers for each data point
- Has a grid for better readability
- Includes a legend identifying each repository
- Saves the output as 'pr_trends.png' in the current directory

Options for graph generation:
- `--graph`: Generate a graph showing all repositories
- `--repo REPO`: Generate a graph for a specific repository only
- `--days N`: Show the last N days of data (default: 30)

The graph uses only historical data from the database and does not make any new API calls.

## Output

The tool generates a report showing:
- Total number of open PRs
- Average PR age
- Average PR age (excluding oldest)
- Average comments per PR
- Average comments (for PRs with comments)
- Number of PRs with zero comments
- Number of approved PRs
- Details of the oldest PR
- Comparison with previous stats (if --compare is used)

In verbose mode (-v), it also shows:
- List of PRs with no comments
- PR titles and URLs
- Age of each PR

## Database

The tool stores historical data in a SQLite database (`pr_stats.db`). This allows for:
- Tracking trends over time
- Comparing current stats with historical data
- Generating graphs of PR trends
- Avoiding unnecessary API calls when generating graphs

## Development

### Running Tests

```bash
pytest
```

### Database Schema

The tool uses SQLite to store historical data. The database schema includes:

- Repository name
- Date
- Total PRs
- Average PR age
- Average PR age (excluding oldest)
- Average comments
- Average comments (PRs with comments)
- Number of approved PRs
- Oldest PR age
- Oldest PR title
- Number of PRs with zero comments 