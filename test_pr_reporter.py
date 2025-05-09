import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from pr_reporter import PRReporter
from pr_reporter import PRStats as ReporterPRStats
from db_manager import PRStats as DBPRStats

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

@pytest.fixture
def mock_db():
    with patch('pr_reporter.DatabaseManager') as mock:
        yield mock

def test_empty_repo(mock_config, mock_github, mock_db):
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

    # Verify database save was called
    mock_db.return_value.save_stats.assert_called_once_with('repo1', stats)

def test_repo_with_prs(mock_config, mock_github, mock_db, mock_pr, mock_approved_pr):
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

    # Verify database save was called
    mock_db.return_value.save_stats.assert_called_once_with('repo1', stats)

def test_generate_report(mock_config, mock_github, mock_db, mock_pr):
    github_client, mock_org = mock_github
    
    # Create different mock repositories with different PR counts
    mock_repo1 = Mock()
    mock_repo1.get_pulls.return_value = [mock_pr]  # 1 PR
    
    mock_repo2 = Mock()
    mock_repo2.get_pulls.return_value = [mock_pr, mock_pr]  # 2 PRs
    
    # Return different repos based on the repo name
    def get_repo(name):
        if name == 'repo1':
            return mock_repo1
        return mock_repo2
    
    mock_org.get_repo.side_effect = get_repo

    reporter = PRReporter(mock_config, github_client=github_client)
    report = reporter.generate_report()

    # Debug assertions
    print("\nReport contents:")
    for repo_name, stats in report.items():
        print(f"{repo_name}: {type(stats)}")
        print(f"Stats: {stats}")

    assert len(report) == 2  # Two repos in config
    assert isinstance(report['repo1'], ReporterPRStats), f"repo1 stats type: {type(report['repo1'])}"
    assert isinstance(report['repo2'], ReporterPRStats), f"repo2 stats type: {type(report['repo2'])}"
    assert report['repo1'].total_prs == 1
    assert report['repo2'].total_prs == 2
    
    # Verify database save was called for each repo
    assert mock_db.return_value.save_stats.call_count == 2 