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

def test_analyze_repo_with_prs(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    
    pr2 = Mock()
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    
    pr3 = Mock()
    pr3.closed_at = now - timedelta(days=30)  # Outside our window
    pr3.created_at = now - timedelta(days=35)
    
    repo.get_pulls.return_value = [pr1, pr2, pr3]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, github_client=github_client)
    stats = analyzer.analyze_repo('repo1')
    
    assert stats['repo_name'] == 'repo1'
    assert stats['total_closed'] == 2
    assert stats['avg_days_open'] == 6.0  # (4 + 8) / 2
    assert stats['std_dev_days'] == 2.0  # Standard deviation of [4, 8]

def test_generate_report(mock_config, mock_github):
    github_client, mock_org = mock_github
    repo = Mock()
    mock_org.get_repo.return_value = repo
    
    # Create mock PRs
    now = datetime.now(timezone.utc)
    pr1 = Mock()
    pr1.closed_at = now - timedelta(days=1)
    pr1.created_at = now - timedelta(days=5)
    
    pr2 = Mock()
    pr2.closed_at = now - timedelta(days=2)
    pr2.created_at = now - timedelta(days=8)
    
    repo.get_pulls.return_value = [pr1, pr2]
    
    analyzer = ClosedPRAnalyzer(mock_config, days=28, github_client=github_client)
    report = analyzer.generate_report()
    
    assert len(report) == 2
    assert 'repo1' in report
    assert 'repo2' in report
    assert report['repo1']['total_closed'] == 2
    assert report['repo2']['total_closed'] == 2

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