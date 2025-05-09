# GitHub PR Reporter

A Python tool that generates reports for open Pull Requests across multiple GitHub repositories in an organization.

## Features

- Reports on multiple repositories in a GitHub organization
- Shows statistics for each repository:
  - Number of open PRs
  - Average age of open PRs
  - Average number of comments per PR
  - Number of approved PRs

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the example config file and update it with your settings:
   ```bash
   cp config.example.yaml config.yaml
   ```

## Configuration

Edit `config.yaml` with your GitHub settings:
- `url`: GitHub API URL (usually https://api.github.com)
- `org`: Your GitHub organization name
- `repos`: List of repository names to monitor
- `auth_token`: Your GitHub personal access token

## Usage

Run the reporter:
```bash
python pr_reporter.py
```

You can also specify a different config file location using the CONFIG_PATH environment variable:
```bash
CONFIG_PATH=/path/to/config.yaml python pr_reporter.py
```

## Running Tests

Run the test suite with pytest:
```bash
pytest
```

## Requirements

- Python 3.6+
- PyGithub
- PyYAML
- python-dotenv
- pytest (for testing) 