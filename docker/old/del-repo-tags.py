#!/usr/bin/env python3
"""Delete tags from docker hub."""

import argparse
import getpass
import sys
import time

import requests

DOCKER_HUB_API = "https://hub.docker.com/v2"
TIMEOUT = 10
HTTP_OK = 200
HTTP_NO_CONTENT = 204


def dockerhub_login(username: str, password: str) -> str:
    """Authenticate with Docker Hub and return JWT token."""
    resp = requests.post(
        f"{DOCKER_HUB_API}/users/login/",
        json={
            "username": username,
            "password": password,
        },
        timeout=TIMEOUT,
    )
    if resp.status_code != HTTP_OK:
        reason = f"Login failed: {resp.status_code} - {resp.text}"
        raise RuntimeError(reason)
    return resp.json()["token"]


def delete_tag(
    username: str, repo: str, tag: str, token: str, retries: int = 3, delay: int = 2
):
    """Delete a tag from Docker Hub with retries."""
    url = f"{DOCKER_HUB_API}/repositories/{username}/{repo}/tags/{tag}/"
    headers = {"Authorization": f"JWT {token}"}

    for attempt in range(1, retries + 1):
        resp = requests.delete(url, headers=headers, timeout=TIMEOUT)
        if resp.status_code == HTTP_NO_CONTENT:
            print(f"✅ Deleted tag '{tag}' from {username}/{repo}")
            return True
        print(
            f"⚠️  Attempt {attempt} to delete '{tag}' failed: {resp.status_code} {resp.text}"
        )
        if attempt < retries:
            time.sleep(delay)
        else:
            print(
                f"❌ Failed to delete tag '{tag}' after {retries} attempts",
                file=sys.stderr,
            )
            break
    return False


def get_args():
    """Get arguments."""
    parser = argparse.ArgumentParser(
        description="Delete one or more tags from a Docker Hub repository."
    )

    # Positional arguments
    parser.add_argument("username", help="Docker Hub username or organization name")
    parser.add_argument("repo", help="Repository name (without username prefix)")
    parser.add_argument("tags", nargs="+", help="One or more tag names to delete")

    # Optional arguments
    parser.add_argument(
        "--retries", type=int, default=3, help="Number of retries if delete fails"
    )
    parser.add_argument(
        "--delay", type=int, default=2, help="Delay between retries (seconds)"
    )

    pw_group = parser.add_mutually_exclusive_group(required=True)
    pw_group.add_argument(
        "--password",
        action="store_true",
        help="Prompt for Docker Hub password via secure input",
    )
    pw_group.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read Docker Hub password from stdin",
    )

    return parser.parse_args()


def main():
    """Run main function."""
    args = get_args()
    # Get password
    if args.password:
        password = getpass.getpass("Docker Hub password: ")
    elif args.password_stdin:
        password = sys.stdin.read().strip()
    else:
        password = None  # unreachable due to mutually exclusive required group

    if not password:
        print("❌ Error: No password provided", file=sys.stderr)
        sys.exit(1)

    try:
        token = dockerhub_login(args.username, password)
    except Exception as e:
        print(f"❌ Error logging in: {e}", file=sys.stderr)
        sys.exit(1)

    # Delete multiple tags
    success = True
    for tag in args.tags:
        try:
            ok = delete_tag(
                args.username, args.repo, tag, token, args.retries, args.delay
            )
            if not ok:
                success = False
        except Exception as e:
            print(f"❌ Error deleting tag '{tag}': {e}", file=sys.stderr)
            success = False

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
