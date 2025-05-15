#!/usr/bin/env python3

import argparse
import os
import sys
import yaml
from github import Github, Auth
from github.GithubException import UnknownObjectException, BadCredentialsException

def get_org_user_emails(config_path: str):
    """
    Fetches and prints the login and public email for all users in a GitHub organization.
    """
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML format in config file: {config_path}")
        print(f"YAML Error details: {e}")
        sys.exit(1)

    if not isinstance(config, dict) or 'github' not in config:
        print("Error: Config file must be a dictionary and contain a 'github' section.")
        sys.exit(1)

    github_config = config['github']
    required_fields = ['org', 'auth_token']
    missing_fields = [field for field in required_fields if field not in github_config]
    if missing_fields:
        print(f"Error: Missing required fields in github config: {', '.join(missing_fields)}")
        sys.exit(1)

    org_name = github_config['org']
    auth_token = github_config['auth_token']

    try:
        auth = Auth.Token(auth_token)
        g = Github(auth=auth)
        org = g.get_organization(org_name)
    except BadCredentialsException:
        print("Error: Invalid GitHub authentication token. Please check your config file.")
        sys.exit(1)
    except UnknownObjectException:
        print(f"Error: GitHub organization '{org_name}' not found or access denied.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while connecting to GitHub: {e}")
        sys.exit(1)

    print(f"Fetching members for organization: {org_name}...")
    print("\n{:<30} {:<40}".format("GitHub Login", "Public Email"))
    print("-" * 70)

    try:
        members = org.get_members()
        print(f"Found {members.totalCount} member(s) in the organization.")

        if members.totalCount == 0:
            print("No members were listed by the API.")
            print("This could be due to a few reasons:")
            print("  1. The GitHub token used may lack the necessary 'read:org' permission to list organization members.")
            print("  2. Members of the organization may have their membership visibility set to private.")
            print("  3. The organization might genuinely have no members visible to this token.")
            print("Please check your token scopes and organization settings.")
            sys.exit(0)

        for member in members:
            user = g.get_user(member.login) # We need to fetch the full user object for the email
            email = user.email if user.email else "Not publicly available"
            print("{:<30} {:<40}".format(user.login, email))
    except Exception as e:
        print(f"Error fetching members or member details: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='List all users in a GitHub organization and their public emails.',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
Example:
  python get_org_user_emails.py
  python get_org_user_emails.py --config /path/to/your/custom_config.yaml
'''
    )
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to the configuration file (default: config.yaml)'
    )
    args = parser.parse_args()

    config_file_path = os.getenv('CONFIG_PATH', args.config)
    get_org_user_emails(config_file_path)

if __name__ == "__main__":
    main() 