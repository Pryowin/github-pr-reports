# GitHub PR Reports

This project provides tools to analyze GitHub Pull Requests (PRs) in your repositories.

## Tools

### 1. PR Reporter (`pr_reporter.py`)

Analyzes open PRs in your repositories and provides statistics about their age, comments, and approval status.

#### Features:
- Counts total open PRs
- Calculates average PR age
- Tracks PRs with no comments
- Shows approved PRs
- Generates trend graphs
- Supports database-only mode for quick reporting

#### Usage:
```bash
# Basic usage
python pr_reporter.py

# Show all PRs with no comments
python pr_reporter.py -v

# Show PRs with no comments that are at least 5 days old
python pr_reporter.py -v --min-age 5

# Compare with stats from 7 days ago
python pr_reporter.py --compare

# Generate a line graph showing PR trends
python pr_reporter.py --graph

# Use database-only mode
python pr_reporter.py --dbonly
```

### 2. Closed PR Analyzer (`closed_pr_analyzer.py`)

Analyzes closed PRs in your repositories over a specified time period.

#### Features:
- Counts total closed PRs
- Calculates average time PRs were open
- Computes standard deviation of PR open times
- Provides per-repository and overall statistics

#### Usage:
```bash
# Basic usage (last 28 days)
python closed_pr_analyzer.py

# Specify number of days
python closed_pr_analyzer.py --days 14

# Use a different config file
python closed_pr_analyzer.py --config custom_config.yaml
```

## Configuration

Both tools use the same configuration file (`config.yaml`):

```yaml
github:
  org: your-org-name
  auth_token: your-github-token
  repos:
    - repo1
    - repo2
```

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Create a `config.yaml` file with your GitHub settings
4. Run the tools as shown in the usage examples

## Development

### Running Tests
```bash
pytest
```

### Adding New Features
1. Create a new branch
2. Add your changes
3. Add tests
4. Submit a PR

## License

MIT License 