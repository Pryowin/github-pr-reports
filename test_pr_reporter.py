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

    reporter = PRReporter(mock_config, verbose=True, min_age_days=5, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    assert stats.total_prs == 0
    assert stats.avg_age_days == 0
    assert stats.avg_comments == 0
    assert stats.avg_comments_with_comments == 0
    assert stats.approved_prs == 0
    assert stats.prs_with_zero_comments == 0
    assert stats.zero_comment_prs == []

    # Verify database save was called
    mock_db.return_value.save_stats.assert_called_once_with('repo1', stats)

def test_repo_with_prs(mock_config, mock_github, mock_db, mock_pr, mock_approved_pr):
    github_client, mock_org = mock_github
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = [mock_pr, mock_approved_pr]
    mock_org.get_repo.return_value = mock_repo

    reporter = PRReporter(mock_config, verbose=True, min_age_days=5, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    assert stats.total_prs == 2
    assert 3 <= stats.avg_age_days <= 4  # Average of 5 and 2 days
    assert stats.avg_age_days_excluding_oldest == 2  # Only the 2-day old PR
    assert stats.avg_comments == 4  # Average of 3 and 5 comments
    assert stats.avg_comments_with_comments == 4  # Average of 3 and 5 comments (both have comments)
    assert stats.approved_prs == 1
    assert stats.oldest_pr_age == 5  # The older PR is 5 days old
    assert stats.oldest_pr_title == mock_pr.title
    assert stats.prs_with_zero_comments == 0  # Both PRs have comments
    assert stats.zero_comment_prs == []  # No PRs without comments

    # Verify database save was called
    mock_db.return_value.save_stats.assert_called_once_with('repo1', stats)

def test_generate_report(mock_config, mock_github, mock_db, mock_pr):
    github_client, mock_org = mock_github
    
    # Create different mock repositories with different PR counts
    mock_repo1 = Mock()
    mock_repo1.get_pulls.return_value = [mock_pr]  # 1 PR
    
    # Create two PRs with different ages and comment counts
    mock_pr_old = Mock()
    mock_pr_old.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    mock_pr_old.comments = 0  # No comments
    mock_pr_old.get_reviews.return_value = []
    mock_pr_old.title = "Old PR"
    mock_pr_old.html_url = "https://github.com/test-org/repo2/pull/1"

    mock_pr_new = Mock()
    mock_pr_new.created_at = datetime.now(timezone.utc) - timedelta(days=3)
    mock_pr_new.comments = 6  # 6 comments
    mock_pr_new.get_reviews.return_value = []
    mock_pr_new.title = "New PR"
    mock_pr_new.html_url = "https://github.com/test-org/repo2/pull/2"
    
    mock_repo2 = Mock()
    mock_repo2.get_pulls.return_value = [mock_pr_old, mock_pr_new]  # 2 PRs with different ages
    
    # Return different repos based on the repo name
    def get_repo(name):
        if name == 'repo1':
            return mock_repo1
        return mock_repo2
    
    mock_org.get_repo.side_effect = get_repo

    reporter = PRReporter(mock_config, verbose=True, min_age_days=5, github_client=github_client)
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
    assert report['repo1'].oldest_pr_age == 5  # The PR is 5 days old
    assert report['repo2'].oldest_pr_age == 10  # The older PR is 10 days old
    assert report['repo1'].oldest_pr_title == mock_pr.title
    assert report['repo2'].oldest_pr_title == "Old PR"
    assert report['repo1'].avg_age_days_excluding_oldest == 0  # No other PRs
    assert report['repo2'].avg_age_days_excluding_oldest == 3  # Only the 3-day old PR
    assert report['repo2'].avg_age_days == 6.5  # Average of 10 and 3 days
    assert report['repo1'].prs_with_zero_comments == 0  # PR has comments
    assert report['repo2'].prs_with_zero_comments == 1  # One PR has no comments
    assert report['repo1'].avg_comments == 3  # One PR with 3 comments
    assert report['repo2'].avg_comments == 3  # Average of 0 and 6 comments
    assert report['repo1'].avg_comments_with_comments == 3  # One PR with 3 comments
    assert report['repo2'].avg_comments_with_comments == 6  # Only counting the PR with 6 comments
    
    # Verify verbose mode details with minimum age
    assert len(report['repo1'].zero_comment_prs) == 0  # No PRs without comments
    assert len(report['repo2'].zero_comment_prs) == 1  # One PR without comments and older than 5 days
    zero_comment_pr = report['repo2'].zero_comment_prs[0]
    assert zero_comment_pr.title == "Old PR"
    assert zero_comment_pr.age_days == 10
    assert zero_comment_pr.url == "https://github.com/test-org/repo2/pull/1"
    
    # Verify database save was called for each repo
    assert mock_db.return_value.save_stats.call_count == 2

def test_non_verbose_mode(mock_config, mock_github, mock_db, mock_pr):
    github_client, mock_org = mock_github
    mock_repo = Mock()
    mock_pr.comments = 0  # Make the PR have no comments
    mock_repo.get_pulls.return_value = [mock_pr]
    mock_org.get_repo.return_value = mock_repo

    reporter = PRReporter(mock_config, verbose=False, min_age_days=5, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    assert stats.total_prs == 1
    assert stats.prs_with_zero_comments == 1
    assert stats.zero_comment_prs is None  # Should be None in non-verbose mode

def test_min_age_filter(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create PRs with different ages and no comments
    mock_pr_old = Mock()
    mock_pr_old.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    mock_pr_old.comments = 0
    mock_pr_old.get_reviews.return_value = []
    mock_pr_old.title = "Old PR"
    mock_pr_old.html_url = "https://github.com/test-org/repo/pull/1"

    mock_pr_medium = Mock()
    mock_pr_medium.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    mock_pr_medium.comments = 0
    mock_pr_medium.get_reviews.return_value = []
    mock_pr_medium.title = "Medium PR"
    mock_pr_medium.html_url = "https://github.com/test-org/repo/pull/2"

    mock_pr_new = Mock()
    mock_pr_new.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    mock_pr_new.comments = 0
    mock_pr_new.get_reviews.return_value = []
    mock_pr_new.title = "New PR"
    mock_pr_new.html_url = "https://github.com/test-org/repo/pull/3"
    
    mock_repo.get_pulls.return_value = [mock_pr_old, mock_pr_medium, mock_pr_new]
    mock_org.get_repo.return_value = mock_repo

    # Test with minimum age of 5 days
    reporter = PRReporter(mock_config, verbose=True, min_age_days=5, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    assert stats.total_prs == 3
    assert stats.prs_with_zero_comments == 3
    assert len(stats.zero_comment_prs) == 2  # Only PRs older than 5 days
    assert stats.zero_comment_prs[0].title == "Old PR"  # 10 days old
    assert stats.zero_comment_prs[1].title == "Medium PR"  # 5 days old
    assert "New PR" not in [pr.title for pr in stats.zero_comment_prs]  # 2 days old, should be filtered out 