import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from pr_reporter import PRReporter, PRStats

@pytest.fixture
def mock_config():
    return {
        'github': {
            'url': 'https://api.github.com',
            'org': 'test-org',
            'repos': ['repo1', 'repo2'],
            'auth_token': 'fake-token'
        }
    }

@pytest.fixture
def mock_pr():
    pr = Mock()
    pr.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    pr.comments = 3
    pr.get_reviews.return_value = []
    return pr

@pytest.fixture
def mock_approved_pr():
    pr = Mock()
    pr.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    pr.comments = 5
    review = Mock()
    review.state = 'APPROVED'
    pr.get_reviews.return_value = [review]
    return pr

@pytest.fixture
def mock_github():
    mock_github = Mock()
    mock_org = Mock()
    mock_github.get_organization.return_value = mock_org
    return mock_github, mock_org

def test_empty_repo(mock_config, mock_github):
    github_client, mock_org = mock_github
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = []
    mock_org.get_repo.return_value = mock_repo

    reporter = PRReporter(mock_config, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    assert stats.total_prs == 0
    assert stats.avg_age_days == 0
    assert stats.avg_comments == 0
    assert stats.approved_prs == 0

def test_repo_with_prs(mock_config, mock_github, mock_pr, mock_approved_pr):
    github_client, mock_org = mock_github
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = [mock_pr, mock_approved_pr]
    mock_org.get_repo.return_value = mock_repo

    reporter = PRReporter(mock_config, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    assert stats.total_prs == 2
    assert 3 <= stats.avg_age_days <= 4  # Average of 5 and 2 days
    assert stats.avg_comments == 4  # Average of 3 and 5 comments
    assert stats.approved_prs == 1

def test_generate_report(mock_config, mock_github, mock_pr):
    github_client, mock_org = mock_github
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = [mock_pr]
    mock_org.get_repo.return_value = mock_repo

    reporter = PRReporter(mock_config, github_client=github_client)
    report = reporter.generate_report()

    assert len(report) == 2  # Two repos in config
    assert all(isinstance(stats, PRStats) for stats in report.values())
    assert all(stats.total_prs == 1 for stats in report.values()) 