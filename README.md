# GitHub PR Reporter

A tool to generate reports about open pull requests in GitHub repositories.

## Features

- Analyzes open pull requests across multiple repositories
- Calculates statistics including:
  - Total number of open PRs
  - Average age of PRs
  - Average age excluding the oldest PR
  - Average number of comments per PR
  - Average number of comments for PRs that have comments
  - Number of PRs with zero comments
  - Number of approved PRs
  - Details of the oldest PR
- Stores historical data in a SQLite database
- Shows comparison with previous day's stats
- Verbose mode to show details of PRs with no comments
- Optional minimum age filter for PRs in verbose mode
- Graceful error handling for missing or invalid configuration

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `config.yaml` file with your GitHub configuration:
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

Show help and available options:
```bash
python pr_reporter.py --help
```

With verbose mode to show PRs with no comments:
```bash
python pr_reporter.py -v
```

With verbose mode and minimum age filter:
```bash
python pr_reporter.py -v --min-age 5
```

### Command Line Options

- `-h, --help`: Show help message and exit
- `--config`: Path to config file (default: config.yaml)
- `-v, --verbose`: Show detailed information about PRs with no comments, including their titles and URLs
- `--min-age`: Minimum age in days for PRs to show in verbose mode. Only PRs with no comments that have been open for at least this many days will be shown. (default: 0)

### Error Handling

The program provides clear error messages for common issues:

1. Missing config file:
   ```
   Error: Config file not found: config.yaml
   
   Please create a config.yaml file with your GitHub settings:
   github:
     org: your-org-name
     auth_token: your-github-token
     repos:
       - repo1
       - repo2
   ```

2. Invalid YAML format:
   ```
   Error: Invalid YAML format in config file.
   
   Common YAML formatting issues:
   1. Incorrect indentation
   2. Missing colons after keys
   3. Missing dashes for list items
   
   Your config file should look like this:
   github:
     org: your-org-name
     auth_token: your-github-token
     repos:
       - repo1
       - repo2
   
   YAML Error details: <specific error>
   ```

3. Invalid GitHub token:
   ```
   Error: Invalid GitHub authentication token
   
   Please check:
   1. The token is correct and hasn't expired
   2. The token has the necessary permissions:
      - repo (Full control of private repositories)
      - read:org (Read organization data)
   
   You can create a new token at: https://github.com/settings/tokens
   ```

4. Organization not found:
   ```
   Error: Organization 'your-org-name' not found on GitHub
   
   Please check:
   1. The organization name is spelled correctly
   2. You have access to the organization
   3. The organization exists
   ```

5. Repository not found:
   ```
   Error: The following repositories were not found in organization 'your-org-name':
     - repo1
     - repo2
   
   Please check:
   1. The repository names are spelled correctly
   2. The repositories exist in the organization
   3. You have access to these repositories
   ```

6. Missing required configuration:
   ```
   Error: Missing required configuration: <missing field>
   
   Please ensure your config file includes all required fields:
   github:
     org: your-org-name
     auth_token: your-github-token
     repos:
       - repo1
       - repo2
   ```

7. Invalid configuration:
   ```
   Error: Invalid configuration: <error details>
   ```

### Example Output

```
GitHub PR Report
==================================================

Repository: example-repo
Total Open PRs: 5
Average PR Age: 7.2 days
Average PR Age (excluding oldest): 5.1 days
Average Comments per PR: 3.4
Average Comments (PRs with comments): 4.2
PRs with Zero Comments: 2
Approved PRs: 1
Oldest PR: Fix database connection timeout (15 days old)

PRs with no comments:
(showing only PRs open for at least 5 days)
  - [15 days] Fix database connection timeout
    https://github.com/org/repo/pull/123
  - [7 days] Update documentation
    https://github.com/org/repo/pull/124

Previous Stats (from 2024-03-19)
Total Open PRs: 4
Average PR Age: 6.8 days
Average PR Age (excluding oldest): 4.9 days
Average Comments per PR: 3.2
Average Comments (PRs with comments): 4.0
PRs with Zero Comments: 1
Approved PRs: 1
Oldest PR: Fix database connection timeout (14 days old)
```

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