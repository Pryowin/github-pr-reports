import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from closed_pr_analyzer import ClosedPRAnalyzer

@pytest.fixture
def mock_config():
    return {
        'github': {
            'org': 'test-org',
            'auth_token': 'test-token',
            'repos': ['repo1', 'repo2']
        }
    }

@pytest.fixture
def mock_github():
    github_client = Mock()
    org = Mock()
    github_client.get_organization.return_value = org
    return github_client, org

def test_analyze_repo_no_prs(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    repo.get_pulls.return_value = []
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, github_client=github_client)
    stats = analyzer.analyze_repo('repo1')
    
    assert stats['repo_name'] == 'repo1'
    assert stats['total_closed'] == 0
    assert stats['avg_days_open'] == 0
    assert stats['std_dev_days'] == 0
    assert stats['user_total_closed'] == 0
    assert stats['user_avg_days_open'] == 0
    assert stats['user_std_dev_days'] == 0

def test_analyze_repo_with_prs(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    pr1.user.email = 'user1@example.com'
    
    pr2 = Mock()
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    pr2.user.email = 'user2@example.com'
    
    pr3 = Mock()
    pr3.closed_at = now - timedelta(days=30)  # Outside our window
    pr3.created_at = now - timedelta(days=35)
    pr3.user.email = 'user1@example.com'
    
    repo.get_pulls.return_value = [pr1, pr2, pr3]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, github_client=github_client)
    stats = analyzer.analyze_repo('repo1')
    
    assert stats['repo_name'] == 'repo1'
    assert stats['total_closed'] == 2
    assert stats['avg_days_open'] == 6.0  # (4 + 8) / 2
    assert stats['std_dev_days'] == 2.0  # Standard deviation of [4, 8]
    assert stats['user_total_closed'] == 0  # No user email specified
    assert stats['user_avg_days_open'] == 0
    assert stats['user_std_dev_days'] == 0

def test_analyze_repo_with_user_tracking(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    pr1.user.email = 'user1@example.com'
    
    pr2 = Mock()
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    pr2.user.email = 'user2@example.com'
    
    pr3 = Mock()
    pr3.closed_at = now - timedelta(days=3)
    pr3.created_at = now - timedelta(days=10)
    pr3.user.email = 'user1@example.com'
    
    repo.get_pulls.return_value = [pr1, pr2, pr3]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, user_email='user1@example.com', github_client=github_client)
    stats = analyzer.analyze_repo('repo1')
    
    assert stats['repo_name'] == 'repo1'
    assert stats['total_closed'] == 3
    assert stats['avg_days_open'] == pytest.approx(7.67, 0.01)  # (4 + 8 + 10) / 3
    assert stats['user_total_closed'] == 2  # Two PRs from user1@example.com
    assert stats['user_avg_days_open'] == 7.0  # (4 + 10) / 2
    assert stats['user_std_dev_days'] == 3.0  # Standard deviation of [4, 10]

def test_generate_report(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    pr1.user.email = 'user1@example.com'
    
    pr2 = Mock()
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    pr2.user.email = 'user2@example.com'
    
    repo.get_pulls.return_value = [pr1, pr2]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, github_client=github_client)
    report = analyzer.generate_report()
    
    assert len(report) == 2
    assert 'repo1' in report
    assert 'repo2' in report
    assert report['repo1']['total_closed'] == 2
    assert report['repo2']['total_closed'] == 2

def test_generate_report_with_user_tracking(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    pr1.user.email = 'user1@example.com'
    
    pr2 = Mock()
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    pr2.user.email = 'user2@example.com'
    
    repo.get_pulls.return_value = [pr1, pr2]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, user_email='user1@example.com', github_client=github_client)
    report = analyzer.generate_report()
    
    assert len(report) == 2
    assert 'repo1' in report
    assert 'repo2' in report
    assert report['repo1']['total_closed'] == 2
    assert report['repo1']['user_total_closed'] == 1
    assert report['repo2']['total_closed'] == 2
    assert report['repo2']['user_total_closed'] == 1

def test_invalid_days():
    with pytest.raises(SystemExit):
        with patch('sys.argv', ['closed_pr_analyzer.py', '--days', '0']):
            from closed_pr_analyzer import main
            main()

def test_missing_config():
    with pytest.raises(SystemExit):
        with patch('sys.argv', ['closed_pr_analyzer.py', '--config', 'nonexistent.yaml']):
            from closed_pr_analyzer import main
            main()

def test_invalid_config():
    with pytest.raises(SystemExit):
        with patch('sys.argv', ['closed_pr_analyzer.py']):
            with patch('builtins.open', Mock(side_effect=Exception("Invalid YAML"))):
                from closed_pr_analyzer import main
                main()

def test_analyze_repo_with_debug_mode(mock_config, mock_github, capsys):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.number = 123
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    pr1.user.email = 'user1@example.com'
    
    pr2 = Mock()
    pr2.number = 124
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    pr2.user.email = 'user2@example.com'
    
    repo.get_pulls.return_value = [pr1, pr2]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, debug=True, github_client=github_client)
    stats = analyzer.analyze_repo('repo1')
    
    # Capture the output
    captured = capsys.readouterr()
    
    # Verify the debug output format
    assert "Detailed PR Information for repo1:" in captured.out
    assert "PR #" in captured.out
    assert "Opened" in captured.out
    assert "Closed" in captured.out
    assert "Days Open" in captured.out
    assert "Author Email" in captured.out
    assert "123" in captured.out
    assert "124" in captured.out
    assert "user1@example.com" in captured.out
    assert "user2@example.com" in captured.out
    
    # Verify the stats are still correct
    assert stats['repo_name'] == 'repo1'
    assert stats['total_closed'] == 2
    assert stats['avg_days_open'] == 6.0
    assert stats['std_dev_days'] == 2.0

def test_generate_report_with_debug_mode(mock_config, mock_github, capsys):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.number = 123
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    pr1.user.email = 'user1@example.com'
    
    pr2 = Mock()
    pr2.number = 124
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    pr2.user.email = 'user2@example.com'
    
    repo.get_pulls.return_value = [pr1, pr2]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, debug=True, github_client=github_client)
    report = analyzer.generate_report()
    
    # Capture the output
    captured = capsys.readouterr()
    
    # Verify debug output for both repositories
    assert "Detailed PR Information for repo1:" in captured.out
    assert "Detailed PR Information for repo2:" in captured.out
    
    # Verify the report data
    assert len(report) == 2
    assert 'repo1' in report
    assert 'repo2' in report
    assert report['repo1']['total_closed'] == 2
    assert report['repo2']['total_closed'] == 2 