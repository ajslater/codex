#!/usr/bin/env python3
"""Remove old tags from a docker repo."""

import argparse
import time
from datetime import datetime

import requests

API_BASE = "https://hub.docker.com/v2"
HTTP_NO_CONTENT = 204
API_TIMEOUT = 10


def login(username, password):
    """Docker login."""
    resp = requests.post(
        f"{API_BASE}/users/login/",
        json={"username": username, "password": password},
        timeout=API_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def fetch_all_tags(namespace, repo, token):
    """Get all the tags for a repo."""
    url = f"{API_BASE}/repositories/{namespace}/{repo}/tags?page_size=100"
    headers = {"Authorization": f"JWT {token}"}
    tags = []
    while url:
        r = requests.get(url, headers=headers, timeout=API_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        tags.extend(data["results"])
        url = data.get("next")
    return tags


def delete_tag(namespace, repo, tag, token, retries=3, delay=2):
    """Delete a tag."""
    headers = {"Authorization": f"JWT {token}"}
    url = f"{API_BASE}/repositories/{namespace}/{repo}/tags/{tag}/"
    for attempt in range(1, retries + 1):
        resp = requests.delete(url, headers=headers, timeout=API_TIMEOUT)
        if resp.status_code == HTTP_NO_CONTENT:
            return True
        print(
            f"Attempt {attempt} failed to delete {tag} (HTTP {resp.status_code}). Retrying in {delay}s..."
        )
        time.sleep(delay)
    return False


def get_args():
    """Get Args."""
    parser = argparse.ArgumentParser(description="Cleanup old Docker Hub tags")
    parser.add_argument("username", help="Docker Hub username")
    parser.add_argument("password", help="Docker Hub password or token")
    parser.add_argument("namespace", help="Namespace or user of the repository")
    parser.add_argument("repository", help="Repository name")
    parser.add_argument(
        "--no-confirm",
        type=bool,
        default=False,
        help="Do not confirm deletion with input prompt",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="Number of latest tags to keep (default 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not actually delete, just show what would be deleted",
    )
    return parser.parse_args()


def main():
    """Run the Program."""
    args = get_args()

    token = login(args.username, args.password)
    print(f"Logged in as {args.username}")

    tags = fetch_all_tags(args.namespace, args.repository, token)
    if not tags:
        print("No tags found.")
        return

    # Sort tags by last_updated descending
    tags.sort(
        key=lambda t: datetime.fromisoformat(t["last_updated"].replace("Z", "+00:00")),
        reverse=True,
    )
    to_delete = tags[args.keep :]

    if not to_delete:
        print(f"Nothing to delete (<= {args.keep} tags).")
        return

    print(f"Keeping {args.keep} most recent tags:")
    for t in tags[: args.keep]:
        print(f"  {t['name']}  ({t['last_updated']})")

    print(f"\nTags to delete ({len(to_delete)}):")
    for t in to_delete:
        print(f"  {t['name']}  ({t['last_updated']})")

    if args.dry_run:
        print("\nDry run mode. No tags will be deleted.")
        return

    if not args.yes:
        confirm = input("\nProceed with deletion? (y/N) ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    for t in to_delete:
        success = delete_tag(args.namespace, args.repository, t["name"], token)
        print(f"{'✅ Deleted' if success else '⚠️ Failed'}: {t['name']}")


if __name__ == "__main__":
    main()
