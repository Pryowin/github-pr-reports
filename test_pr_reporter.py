import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from pr_reporter import PRReporter, PRStats, PRDetail, PRNoUpdateDetail
from pr_reporter import PRStats as ReporterPRStats
from db_manager import PRStats as DBPRStats
import os

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
    pr.labels = []  # Ensure labels is always a list
    return pr

@pytest.fixture
def mock_approved_pr():
    pr = Mock()
    pr.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    pr.comments = 5
    review = Mock()
    review.state = 'APPROVED'
    pr.get_reviews.return_value = [review]
    pr.labels = []  # Ensure labels is always a list
    return pr

@pytest.fixture
def mock_github():
    with patch('pr_reporter.Github') as mock_github:
        mock_github.return_value = Mock()
        mock_org = Mock()
        mock_github.return_value.get_organization.return_value = mock_org
        yield mock_github.return_value, mock_org

@pytest.fixture
def mock_db():
    with patch('pr_reporter.DatabaseManager') as mock:
        yield mock

# Helper for label mocks
def label_mock(label_name):
    mock = Mock()
    mock.name = label_name
    return mock

def create_mock_pr(title, created_at, comments=0, labels=None, is_approved=False):
    mock_pr = Mock()
    mock_pr.title = title
    mock_pr.created_at = created_at
    mock_pr.comments = comments
    mock_pr.labels = labels or []
    mock_pr.html_url = f"https://github.com/test-org/test-repo/pull/1"
    
    # Mock reviews
    mock_review = Mock()
    mock_review.state = 'APPROVED' if is_approved else 'COMMENTED'
    mock_pr.get_reviews.return_value = [mock_review] if is_approved else []
    
    return mock_pr

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
    # Ensure labels attribute is present
    mock_pr.labels = []
    mock_approved_pr.labels = []
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
    mock_pr.labels = []
    mock_repo1.get_pulls.return_value = [mock_pr]  # 1 PR
    
    # Create two PRs with different ages and comment counts
    mock_pr_old = Mock()
    mock_pr_old.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    mock_pr_old.comments = 0  # No comments
    mock_pr_old.get_reviews.return_value = []
    mock_pr_old.title = "Old PR"
    mock_pr_old.html_url = "https://github.com/test-org/repo2/pull/1"
    mock_pr_old.labels = [label_mock("Ready for Review")]

    mock_pr_new = Mock()
    mock_pr_new.created_at = datetime.now(timezone.utc) - timedelta(days=3)
    mock_pr_new.comments = 6  # 6 comments
    mock_pr_new.get_reviews.return_value = []
    mock_pr_new.title = "New PR"
    mock_pr_new.html_url = "https://github.com/test-org/repo2/pull/2"
    mock_pr_new.labels = [label_mock("Ready for Review")]
    
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

    assert len(report) == 2  # Two repos in config
    assert isinstance(report['repo1'], ReporterPRStats)
    assert isinstance(report['repo2'], ReporterPRStats)
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
    mock_pr.labels = []
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
    mock_pr_old.labels = [label_mock("Ready for Review")]

    mock_pr_medium = Mock()
    mock_pr_medium.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    mock_pr_medium.comments = 0
    mock_pr_medium.get_reviews.return_value = []
    mock_pr_medium.title = "Medium PR"
    mock_pr_medium.html_url = "https://github.com/test-org/repo/pull/2"
    mock_pr_medium.labels = [label_mock("Ready for Review")]

    mock_pr_new = Mock()
    mock_pr_new.created_at = datetime.now(timezone.utc) - timedelta(days=2)
    mock_pr_new.comments = 0
    mock_pr_new.get_reviews.return_value = []
    mock_pr_new.title = "New PR"
    mock_pr_new.html_url = "https://github.com/test-org/repo/pull/3"
    mock_pr_new.labels = [label_mock("Ready for Review")]
    
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

    print("Debug: PR labels:")
    for pr in [mock_pr_old, mock_pr_medium, mock_pr_new]:
        print(f"PR {pr.title} labels: {[label.name for label in pr.labels]}")

def test_get_repo_stats_no_prs(mock_config):
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = []
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    org.get_repo.return_value = mock_repo
    reporter = PRReporter(mock_config, github_client=github_client)
    stats = reporter.get_repo_stats('test-repo')
    
    assert stats.total_prs == 0
    assert stats.avg_age_days == 0
    assert stats.avg_comments == 0
    assert stats.prs_with_zero_comments == 0
    assert stats.zero_comment_prs == []

def test_get_repo_stats_with_prs(mock_config):
    now = datetime.now(timezone.utc)
    prs = [
        create_mock_pr("PR 1", now - timedelta(days=5), comments=2, labels=[label_mock("Ready for Review")]),
        create_mock_pr("PR 2", now - timedelta(days=10), comments=0, labels=[label_mock("Ready for Review")]),
        create_mock_pr("PR 3", now - timedelta(days=15), comments=3, labels=[label_mock("Ready for Review")], is_approved=True)
    ]
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = prs
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    org.get_repo.return_value = mock_repo
    reporter = PRReporter(mock_config, verbose=True, github_client=github_client)
    stats = reporter.get_repo_stats('test-repo')
    
    assert stats.total_prs == 3
    assert stats.avg_age_days == 10.0
    assert abs(stats.avg_comments - 1.67) < 0.01  # Allow for floating point imprecision
    assert stats.prs_with_zero_comments == 1
    assert stats.approved_prs == 1
    assert len(stats.zero_comment_prs) == 1
    assert stats.zero_comment_prs[0].title == "PR 2"

def test_get_repo_stats_without_ready_label(mock_config):
    now = datetime.now(timezone.utc)
    prs = [
        create_mock_pr("PR 1", now - timedelta(days=5), comments=0, labels=[label_mock("WIP")]),
        create_mock_pr("PR 2", now - timedelta(days=10), comments=0, labels=[label_mock("Ready for Review")]),
    ]
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = prs
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    org.get_repo.return_value = mock_repo
    reporter = PRReporter(mock_config, verbose=True, github_client=github_client)
    stats = reporter.get_repo_stats('test-repo')
    
    assert stats.total_prs == 2
    assert stats.prs_with_zero_comments == 2  # Still counts all PRs with zero comments
    assert len(stats.zero_comment_prs) == 1  # But only shows the one with "Ready for Review" label
    assert stats.zero_comment_prs[0].title == "PR 2"

def test_get_repo_stats_with_min_age(mock_config):
    now = datetime.now(timezone.utc)
    prs = [
        create_mock_pr("PR 1", now - timedelta(days=3), comments=0, labels=[label_mock("Ready for Review")]),
        create_mock_pr("PR 2", now - timedelta(days=7), comments=0, labels=[label_mock("Ready for Review")]),
    ]
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = prs
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    org.get_repo.return_value = mock_repo
    reporter = PRReporter(mock_config, verbose=True, min_age_days=5, github_client=github_client)
    stats = reporter.get_repo_stats('test-repo')
    
    assert stats.total_prs == 2
    assert stats.prs_with_zero_comments == 2
    assert len(stats.zero_comment_prs) == 1  # Only shows PRs older than 5 days
    assert stats.zero_comment_prs[0].title == "PR 2"

def test_get_repo_stats_with_multiple_labels(mock_config):
    now = datetime.now(timezone.utc)
    prs = [
        create_mock_pr("PR 1", now - timedelta(days=5), comments=0, 
                      labels=[label_mock("Ready for Review"), label_mock("Enhancement")]),
        create_mock_pr("PR 2", now - timedelta(days=7), comments=0, 
                      labels=[label_mock("WIP"), label_mock("Bug")]),
    ]
    mock_repo = Mock()
    mock_repo.get_pulls.return_value = prs
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    org.get_repo.return_value = mock_repo
    reporter = PRReporter(mock_config, verbose=True, github_client=github_client)
    stats = reporter.get_repo_stats('test-repo')
    
    assert stats.total_prs == 2
    assert stats.prs_with_zero_comments == 2
    assert len(stats.zero_comment_prs) == 1  # Only shows PR with "Ready for Review" label
    assert stats.zero_comment_prs[0].title == "PR 1"

def test_format_comparison(mock_config):
    with patch('pr_reporter.Github') as mock_github:
        mock_github.return_value = Mock()
        mock_org = Mock()
        mock_github.return_value.get_organization.return_value = mock_org
        
        reporter = PRReporter(mock_config, github_client=mock_github.return_value)
        
        # Test higher value (should be red)
        result = reporter._format_comparison(10, 5)
        assert '\033[91m' in result  # Red color code
        assert '10' in result
        assert '(5.0)' in result
        
        # Test lower value (should be green)
        result = reporter._format_comparison(5, 10)
        assert '\033[92m' in result  # Green color code
        assert '5' in result
        assert '(10.0)' in result
        
        # Test equal value (no color)
        result = reporter._format_comparison(5, 5)
        assert '\033[91m' not in result  # No red
        assert '\033[92m' not in result  # No green
        assert '5' in result
        assert '(5.0)' not in result  # No parentheses for equal values

def test_get_comparison_stats(mock_config):
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    reporter = PRReporter(mock_config, compare_days=7, github_client=github_client)
    # Mock database response
    mock_stats = {
        'date': '2024-03-19',
        'total_prs': 5,
        'avg_age_days': 7.2,
        'avg_age_days_excluding_oldest': 5.1,
        'avg_comments': 3.4,
        'avg_comments_with_comments': 4.2,
        'approved_prs': 1,
        'oldest_pr_age': 15,
        'oldest_pr_title': 'Test PR',
        'prs_with_zero_comments': 2
    }
    with patch.object(reporter.db, 'get_stats_before_date', return_value=mock_stats):
        stats = reporter._get_comparison_stats('test-repo')
        assert stats == mock_stats
        assert stats['date'] == '2024-03-19'

def test_get_comparison_stats_no_data(mock_config):
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    reporter = PRReporter(mock_config, compare_days=7, github_client=github_client)
    # Mock database response for no data
    with patch.object(reporter.db, 'get_stats_before_date', return_value=None):
        with patch.object(reporter.db, 'get_earliest_stats', return_value=None):
            stats = reporter._get_comparison_stats('test-repo')
            assert stats is None

def test_graph_generation_single_repo(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    reporter = PRReporter(mock_config, github_client=github_client)
    
    # Mock database response for a single repository
    mock_stats = [
        {
            'date': '2024-03-19',
            'total_prs': 5,
            'avg_age_days': 7.2,
            'avg_age_days_excluding_oldest': 5.1,
            'avg_comments': 3.4,
            'avg_comments_with_comments': 4.2,
            'approved_prs': 1,
            'oldest_pr_age': 15,
            'oldest_pr_title': 'Test PR',
            'prs_with_zero_comments': 2
        },
        {
            'date': '2024-03-20',
            'total_prs': 6,
            'avg_age_days': 7.5,
            'avg_age_days_excluding_oldest': 5.3,
            'avg_comments': 3.6,
            'avg_comments_with_comments': 4.4,
            'approved_prs': 2,
            'oldest_pr_age': 16,
            'oldest_pr_title': 'Test PR 2',
            'prs_with_zero_comments': 1
        }
    ]
    
    with patch.object(reporter.db, 'get_stats_in_date_range', return_value=mock_stats):
        reporter.generate_graph(days=2, repo_name='repo1')
        
        # Verify database was queried with correct parameters
        reporter.db.get_stats_in_date_range.assert_called_once()
        call_args = reporter.db.get_stats_in_date_range.call_args[0]
        assert call_args[0] == 'repo1'  # repo_name
        assert isinstance(call_args[1], datetime)  # start_date
        assert isinstance(call_args[2], datetime)  # end_date

def test_graph_generation_all_repos(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    reporter = PRReporter(mock_config, github_client=github_client)
    
    # Mock database response for multiple repositories
    mock_stats = {
        'repo1': [
            {'date': '2024-03-19', 'total_prs': 5},
            {'date': '2024-03-20', 'total_prs': 6}
        ],
        'repo2': [
            {'date': '2024-03-19', 'total_prs': 3},
            {'date': '2024-03-20', 'total_prs': 4}
        ]
    }
    
    def mock_get_stats(repo_name, start_date, end_date):
        return mock_stats.get(repo_name, [])
    
    with patch.object(reporter.db, 'get_stats_in_date_range', side_effect=mock_get_stats):
        reporter.generate_graph(days=2)
        
        # Verify database was queried for each repository
        assert reporter.db.get_stats_in_date_range.call_count == 2
        calls = reporter.db.get_stats_in_date_range.call_args_list
        assert calls[0][0][0] == 'repo1'  # First call for repo1
        assert calls[1][0][0] == 'repo2'  # Second call for repo2

def test_graph_generation_invalid_repo(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    reporter = PRReporter(mock_config, github_client=github_client)
    
    # Test with non-existent repository
    with pytest.raises(ValueError):
        reporter.generate_graph(days=2, repo_name='nonexistent-repo')

def test_graph_generation_filename_format(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    reporter = PRReporter(mock_config, github_client=github_client)
    
    # Mock database response
    mock_stats = [
        {
            'date': '2024-03-19',
            'total_prs': 5,
            'avg_age_days': 7.2,
            'avg_age_days_excluding_oldest': 5.1,
            'avg_comments': 3.4,
            'avg_comments_with_comments': 4.2,
            'approved_prs': 1,
            'oldest_pr_age': 15,
            'oldest_pr_title': 'Test PR',
            'prs_with_zero_comments': 2
        }
    ]
    
    # Mock datetime.now to return a fixed date
    with patch('pr_reporter.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 3, 21, tzinfo=timezone.utc)
        mock_datetime.strptime = datetime.strptime  # Keep the original strptime
        
        with patch.object(reporter.db, 'get_stats_in_date_range', return_value=mock_stats):
            # Test single repo graph
            filepath = reporter.generate_graph(days=2, repo_name='repo1')
            assert filepath == 'graphs/repo1_pr_trends_2024-03-21.png'
            
            # Test all repos graph
            filepath = reporter.generate_graph(days=2)
            assert filepath == 'graphs/all_repos_pr_trends_2024-03-21.png'
            
            # Verify the graphs directory was created
            assert os.path.exists('graphs')
            
            # Clean up
            if os.path.exists('graphs'):
                for file in os.listdir('graphs'):
                    os.remove(os.path.join('graphs', file))
                os.rmdir('graphs')

def test_dbonly_mode_with_data(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    reporter = PRReporter(mock_config, github_client=github_client, dbonly=True)
    
    # Mock database response
    mock_stats = {
        'date': '2024-03-21',
        'total_prs': 5,
        'avg_age_days': 7.2,
        'avg_age_days_excluding_oldest': 5.1,
        'avg_comments': 3.4,
        'avg_comments_with_comments': 4.2,
        'approved_prs': 1,
        'oldest_pr_age': 15,
        'oldest_pr_title': 'Test PR',
        'prs_with_zero_comments': 2
    }
    
    with patch.object(reporter.db, 'get_stats_for_date', return_value=mock_stats):
        stats = reporter.get_repo_stats('repo1')
        
        # Verify stats were loaded from database
        assert stats.total_prs == 5
        assert stats.avg_age_days == 7.2
        assert stats.avg_comments == 3.4
        assert stats.approved_prs == 1
        
        # Verify no API calls were made
        mock_org.get_repo.assert_not_called()

def test_dbonly_mode_no_data(mock_config, mock_github, mock_db):
    github_client, mock_org = mock_github
    reporter = PRReporter(mock_config, github_client=github_client, dbonly=True)
    
    # Mock database response for no data
    with patch.object(reporter.db, 'get_stats_for_date', return_value=None):
        with pytest.raises(ValueError) as exc_info:
            reporter.get_repo_stats('repo1')
        
        assert "No data found in database" in str(exc_info.value)
        
        # Verify no API calls were made
        mock_org.get_repo.assert_not_called()

def test_dbonly_mode_github_not_initialized(mock_config, mock_github, mock_db):
    # Test that GitHub client is not initialized in dbonly mode
    reporter = PRReporter(mock_config, dbonly=True)
    assert not hasattr(reporter, 'github')
    assert not hasattr(reporter, 'org') 

def test_no_update_functionality(mock_config, mock_github, mock_db):
    """Test the new no-update functionality that finds PRs with no recent comments."""
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create PRs with different comment histories
    now = datetime.now(timezone.utc)
    
    # PR with recent comment (2 days ago)
    mock_pr_recent = Mock()
    mock_pr_recent.created_at = now - timedelta(days=10)
    mock_pr_recent.comments = 5
    mock_pr_recent.title = "Recent Comment PR"
    mock_pr_recent.html_url = "https://github.com/test-org/repo/pull/1"
    mock_pr_recent.labels = []
    mock_pr_recent.get_reviews.return_value = []
    
    # PR with old comment (15 days ago)
    mock_pr_old_comment = Mock()
    mock_pr_old_comment.created_at = now - timedelta(days=20)
    mock_pr_old_comment.comments = 3
    mock_pr_old_comment.title = "Old Comment PR"
    mock_pr_old_comment.html_url = "https://github.com/test-org/repo/pull/2"
    mock_pr_old_comment.labels = []
    mock_pr_old_comment.get_reviews.return_value = []
    
    # PR with no comments
    mock_pr_no_comments = Mock()
    mock_pr_no_comments.created_at = now - timedelta(days=5)
    mock_pr_no_comments.comments = 0
    mock_pr_no_comments.title = "No Comments PR"
    mock_pr_no_comments.html_url = "https://github.com/test-org/repo/pull/3"
    mock_pr_no_comments.labels = []
    mock_pr_no_comments.get_reviews.return_value = []
    
    mock_repo.get_pulls.return_value = [mock_pr_recent, mock_pr_old_comment, mock_pr_no_comments]
    mock_org.get_repo.return_value = mock_repo
    
    # Mock the comment dates
    def mock_get_issue_comments():
        if mock_pr_recent:
            # Recent comment (2 days ago)
            comment1 = Mock()
            comment1.created_at = now - timedelta(days=2)
            comment2 = Mock()
            comment2.created_at = now - timedelta(days=5)
            return [comment1, comment2]
        elif mock_pr_old_comment:
            # Old comment (15 days ago)
            comment = Mock()
            comment.created_at = now - timedelta(days=15)
            return [comment]
        else:
            # No comments
            return []
    
    # Set up the mock for get_issue_comments
    mock_pr_recent.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=2)),
        Mock(created_at=now - timedelta(days=5))
    ]
    mock_pr_old_comment.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    mock_pr_no_comments.get_issue_comments.return_value = []
    
    # Set up review mocks
    mock_pr_recent.get_reviews.return_value = []
    mock_pr_old_comment.get_reviews.return_value = []
    mock_pr_no_comments.get_reviews.return_value = []
    
    # Set up draft status
    mock_pr_recent.draft = False
    mock_pr_old_comment.draft = False
    mock_pr_no_comments.draft = False
    
    # Test with no-update threshold of 10 days
    reporter = PRReporter(mock_config, verbose=True, no_update_days=10, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')

    print(f"Debug: Total PRs: {stats.total_prs}")
    print(f"Debug: No update PRs: {stats.no_update_prs}")
    print(f"Debug: Zero comment PRs: {stats.zero_comment_prs}")

    assert stats.total_prs == 3
    assert len(stats.no_update_prs) == 1  # Only one PR with no recent comments (old comment)
    assert stats.no_update_prs[0].title == "Old Comment PR"
    assert stats.no_update_prs[0].last_comment_days == 15  # Days since last comment
    assert stats.no_update_prs[0].is_approved == False  # Not approved

def test_no_update_functionality_disabled(mock_config, mock_github, mock_db):
    """Test that no-update functionality is disabled when not specified."""
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create a PR with old comments
    now = datetime.now(timezone.utc)
    mock_pr = Mock()
    mock_pr.created_at = now - timedelta(days=20)
    mock_pr.comments = 3
    mock_pr.title = "Old Comment PR"
    mock_pr.html_url = "https://github.com/test-org/repo/pull/1"
    mock_pr.labels = []
    mock_pr.get_reviews.return_value = []
    mock_pr.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    mock_repo.get_pulls.return_value = [mock_pr]
    mock_org.get_repo.return_value = mock_repo
    
    # Test without no-update parameter
    reporter = PRReporter(mock_config, verbose=True, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')
    
    assert stats.total_prs == 1
    assert stats.no_update_prs is None  # Should be None when not enabled

def test_no_update_with_exception_handling(mock_config, mock_github, mock_db):
    """Test that no-update functionality handles API exceptions gracefully."""
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create a PR that will raise an exception when getting comments
    now = datetime.now(timezone.utc)
    mock_pr = Mock()
    mock_pr.created_at = now - timedelta(days=10)
    mock_pr.comments = 2
    mock_pr.title = "Exception PR"
    mock_pr.html_url = "https://github.com/test-org/repo/pull/1"
    mock_pr.labels = []
    mock_pr.get_reviews.return_value = []
    mock_pr.get_issue_comments.side_effect = Exception("API Error")
    
    mock_repo.get_pulls.return_value = [mock_pr]
    mock_org.get_repo.return_value = mock_repo
    
    # Test with no-update parameter - should fall back to PR creation date
    reporter = PRReporter(mock_config, verbose=True, no_update_days=5, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')
    
    assert stats.total_prs == 1
    assert len(stats.no_update_prs) == 1
    assert stats.no_update_prs[0].title == "Exception PR"
    assert stats.no_update_prs[0].last_comment_days == 10  # Should use PR creation date

def test_no_update_constructor_parameter(mock_config):
    """Test that the no_update_days parameter is properly passed to the constructor."""
    reporter = PRReporter(mock_config, no_update_days=30)
    assert reporter.no_update_days == 30
    
    reporter2 = PRReporter(mock_config)
    assert reporter2.no_update_days is None 

def test_no_update_auto_verbose(mock_config):
    """Test that verbose mode is automatically enabled when --noupdate is used."""
    # Test without --noupdate
    reporter1 = PRReporter(mock_config, verbose=False)
    assert reporter1.verbose == False
    
    # Test with --noupdate (should auto-enable verbose)
    reporter2 = PRReporter(mock_config, verbose=False, no_update_days=30)
    assert reporter2.verbose == True
    
    # Test with both --noupdate and explicit verbose
    reporter3 = PRReporter(mock_config, verbose=True, no_update_days=30)
    assert reporter3.verbose == True 

def test_no_update_ignore_do_not_merge(mock_config, mock_github, mock_db):
    """Test that PRs with 'DO NOT MERGE' tag are ignored in no-update functionality."""
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create PRs with different scenarios
    now = datetime.now(timezone.utc)
    
    # PR with old comments but no DO NOT MERGE tag
    mock_pr_old = Mock()
    mock_pr_old.created_at = now - timedelta(days=20)
    mock_pr_old.comments = 3
    mock_pr_old.title = "Old Comment PR"
    mock_pr_old.html_url = "https://github.com/test-org/repo/pull/1"
    mock_pr_old.labels = []
    mock_pr_old.get_reviews.return_value = []
    mock_pr_old.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    # PR with old comments AND DO NOT MERGE tag (should be ignored)
    mock_pr_do_not_merge = Mock()
    mock_pr_do_not_merge.created_at = now - timedelta(days=20)
    mock_pr_do_not_merge.comments = 2
    mock_pr_do_not_merge.title = "DO NOT MERGE PR"
    mock_pr_do_not_merge.html_url = "https://github.com/test-org/repo/pull/2"
    mock_pr_do_not_merge.labels = [label_mock("DO NOT MERGE")]
    mock_pr_do_not_merge.get_reviews.return_value = []
    mock_pr_do_not_merge.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    mock_repo.get_pulls.return_value = [mock_pr_old, mock_pr_do_not_merge]
    mock_org.get_repo.return_value = mock_repo
    
    # Set up updated_at dates for the PRs
    mock_pr_old.updated_at = now - timedelta(days=15)  # Old push
    mock_pr_do_not_merge.updated_at = now - timedelta(days=15)  # Old push
    
    # Set up draft status
    mock_pr_old.draft = False
    mock_pr_do_not_merge.draft = False
    
    # Test with no-update threshold of 10 days
    reporter = PRReporter(mock_config, verbose=True, no_update_days=10, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')
    
    assert stats.total_prs == 2
    assert len(stats.no_update_prs) == 1  # Only the PR without DO NOT MERGE tag
    assert stats.no_update_prs[0].title == "Old Comment PR"
    assert stats.no_update_prs[0].is_draft == False  # Not draft
    assert "DO NOT MERGE" not in [pr.title for pr in stats.no_update_prs] 

def test_no_update_exclude_recent_pushes(mock_config, mock_github, mock_db):
    """Test that PRs with recent pushes are excluded from no-update functionality."""
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create PRs with different scenarios
    now = datetime.now(timezone.utc)
    
    # PR with old comments and old push (should be included)
    mock_pr_old_all = Mock()
    mock_pr_old_all.created_at = now - timedelta(days=20)
    mock_pr_old_all.updated_at = now - timedelta(days=15)  # Old push
    mock_pr_old_all.comments = 3
    mock_pr_old_all.title = "Old Comment and Push PR"
    mock_pr_old_all.html_url = "https://github.com/test-org/repo/pull/1"
    mock_pr_old_all.labels = []
    mock_pr_old_all.get_reviews.return_value = []
    mock_pr_old_all.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    # PR with old comments but recent push (should be excluded)
    mock_pr_recent_push = Mock()
    mock_pr_recent_push.created_at = now - timedelta(days=20)
    mock_pr_recent_push.updated_at = now - timedelta(days=3)  # Recent push
    mock_pr_recent_push.comments = 2
    mock_pr_recent_push.title = "Recent Push PR"
    mock_pr_recent_push.html_url = "https://github.com/test-org/repo/pull/2"
    mock_pr_recent_push.labels = []
    mock_pr_recent_push.get_reviews.return_value = []
    mock_pr_recent_push.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    mock_repo.get_pulls.return_value = [mock_pr_old_all, mock_pr_recent_push]
    mock_org.get_repo.return_value = mock_repo
    
    # Set up draft status
    mock_pr_old_all.draft = False
    mock_pr_recent_push.draft = False
    
    # Test with no-update threshold of 10 days
    reporter = PRReporter(mock_config, verbose=True, no_update_days=10, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')
    
    assert stats.total_prs == 2
    assert len(stats.no_update_prs) == 1  # Only the PR with old push
    assert stats.no_update_prs[0].title == "Old Comment and Push PR"
    assert "Recent Push" not in [pr.title for pr in stats.no_update_prs] 

def test_no_update_draft_prs(mock_config, mock_github, mock_db):
    """Test that draft PRs are correctly identified and can be displayed in yellow."""
    github_client, mock_org = mock_github
    mock_repo = Mock()
    
    # Create PRs with different scenarios
    now = datetime.now(timezone.utc)
    
    # Regular PR with old comments and push
    mock_pr_regular = Mock()
    mock_pr_regular.created_at = now - timedelta(days=20)
    mock_pr_regular.updated_at = now - timedelta(days=15)  # Old push
    mock_pr_regular.comments = 3
    mock_pr_regular.title = "Regular PR"
    mock_pr_regular.html_url = "https://github.com/test-org/repo/pull/1"
    mock_pr_regular.labels = []
    mock_pr_regular.draft = False
    mock_pr_regular.get_reviews.return_value = []
    mock_pr_regular.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    # Draft PR with old comments and push
    mock_pr_draft = Mock()
    mock_pr_draft.created_at = now - timedelta(days=20)
    mock_pr_draft.updated_at = now - timedelta(days=15)  # Old push
    mock_pr_draft.comments = 2
    mock_pr_draft.title = "Draft PR"
    mock_pr_draft.html_url = "https://github.com/test-org/repo/pull/2"
    mock_pr_draft.labels = []
    mock_pr_draft.draft = True
    mock_pr_draft.get_reviews.return_value = []
    mock_pr_draft.get_issue_comments.return_value = [
        Mock(created_at=now - timedelta(days=15))
    ]
    
    mock_repo.get_pulls.return_value = [mock_pr_regular, mock_pr_draft]
    mock_org.get_repo.return_value = mock_repo
    
    # Test with no-update threshold of 10 days
    reporter = PRReporter(mock_config, verbose=True, no_update_days=10, github_client=github_client)
    stats = reporter.get_repo_stats('repo1')
    
    assert stats.total_prs == 2
    assert len(stats.no_update_prs) == 2  # Both PRs should be included
    
    # Find the draft PR
    draft_pr = next(pr for pr in stats.no_update_prs if pr.title == "Draft PR")
    regular_pr = next(pr for pr in stats.no_update_prs if pr.title == "Regular PR")
    
    assert draft_pr.is_draft == True
    assert regular_pr.is_draft == False 