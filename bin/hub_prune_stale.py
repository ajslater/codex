#!/usr/bin/env python3
"""
Delete stale images and image indexes from a Docker Hub repository.

Stale means debris: a manifest no tag reaches, which is what an old digest
becomes when a tag is overwritten, along with the per-architecture images
that hung beneath it. Deleting those cannot break a pull.

Untagged is not the same as stale, and that difference is the whole job. The
per-arch images and attestations under a live multi-arch tag carry no tags of
their own; delete those and the tag breaks. So this works out what every tag
actually reaches -- the tagged digest, the architectures the tag list names,
and the attestation manifests only the index itself knows about -- and treats
that set as untouchable.

The repository's manifests come from
/v2/namespaces/{ns}/repositories/{repo}/manifests, which is what Docker Hub's
Image Management page reads. It is undocumented: absent from the current Hub
API spec, its currently_tagged and status parameters are ignored, page numbers
do nothing, and paging runs off a last_evaluated_key cursor at 100 per page.

Deletion goes through the registry API, which independently refuses (403)
anything still referenced, so every delete gets a second opinion. Registry
tokens expire after about five minutes, which a long prune outlives, so the
token is reissued before it lapses and again on any 401.

Credentials, the same env vars as the rest of the Docker tooling here:
  DOCKER_USER   Docker Hub username
  DOCKER_PASS   Docker Hub password or personal access token
A personal access token needs the "Read, Write, Delete" scope.

Dry run by default. Pass --execute to actually delete.
"""

from __future__ import annotations

import os
import sys
import time
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import requests
from requests.auth import HTTPBasicAuth

if TYPE_CHECKING:
    from collections.abc import Iterator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Overridable so the test harness can point at a local fake registry.
HUB_API: str = os.environ.get("HUB_API_URL", "https://hub.docker.com/v2")
REGISTRY_API: str = os.environ.get(
    "REGISTRY_API_URL", "https://registry-1.docker.io/v2"
)
REGISTRY_AUTH: str = os.environ.get("REGISTRY_AUTH_URL", "https://auth.docker.io/token")

TIMEOUT: int = 30
PAGE_SIZE: int = 100  # The listing returns nothing at all above 100.
MAX_PAGES: int = 500  # A cursor that never ends is a bug, not a big repo.
TOKEN_LEEWAY: int = 30  # Reissue this many seconds before expiry.
DEFAULT_TOKEN_LIFETIME: int = 300
MAX_ATTEMPTS: int = 3
RETRY_WAIT: int = 2

ACCEPT_MANIFESTS: str = (
    "application/vnd.oci.image.index.v1+json"
    ", application/vnd.docker.distribution.manifest.list.v2+json"
    ", application/vnd.oci.image.manifest.v1+json"
    ", application/vnd.docker.distribution.manifest.v2+json"
)

DELETED_STATUSES: frozenset[int] = frozenset(
    (HTTPStatus.OK, HTTPStatus.ACCEPTED, HTTPStatus.NOT_FOUND)
)
RETRY_STATUSES: frozenset[int] = frozenset(
    (
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
    )
)


class PruneError(RuntimeError):
    """Something went wrong that must stop the prune."""


@dataclass(frozen=True)
class Manifest:
    """One manifest in a repository, as Docker Hub describes it."""

    digest: str
    media_type: str
    tags: tuple[str, ...]
    platform: str
    size: int
    last_pushed: str
    last_pulled: str

    @property
    def is_index(self) -> bool:
        """Whether this is an image index rather than a single image."""
        return "index" in self.media_type or "list" in self.media_type

    @property
    def kind(self) -> str:
        """Human label for the manifest's type."""
        return "image index" if self.is_index else "image      "

    @classmethod
    def from_hub(cls, data: dict[str, Any]) -> Manifest:
        """Build a manifest from a Hub listing entry."""
        # Every field can arrive as JSON null, hence the empty defaults.
        arch = str(data.get("arch") or "")
        return cls(
            digest=str(data.get("manifest_digest") or ""),
            media_type=str(data.get("media_type") or ""),
            tags=tuple(_tag_names(data.get("tags"))),
            platform=f"{data.get('os') or 'linux'}/{arch}" if arch else "",
            size=int(data.get("total_size") or 0),
            last_pushed=str(data.get("last_pushed") or ""),
            last_pulled=str(data.get("last_pulled") or ""),
        )


def _tag_names(tags: Any) -> Iterator[str]:
    """Read tag names, whether the listing gives strings or objects."""
    for tag in tags or ():
        if isinstance(tag, dict):
            name = tag.get("tag")
            if name:
                yield str(name)
        else:
            yield str(tag)


# ---------------------------------------------------------------------------
# Docker Hub
# ---------------------------------------------------------------------------


class HubSession:
    """Authenticated client for the Docker Hub API."""

    def __init__(self, user: str, secret: str) -> None:
        """Log in and keep the bearer token on the session."""
        self._session = requests.Session()
        response = self._session.post(
            f"{HUB_API}/auth/token",
            json={"identifier": user, "secret": secret},
            timeout=TIMEOUT,
        )
        if not response.ok:
            reason = f"Docker Hub login failed (HTTP {response.status_code})"
            raise PruneError(reason)
        token = response.json().get("access_token")
        if not token:
            reason = "Docker Hub returned no access token"
            raise PruneError(reason)
        self._session.headers["Authorization"] = f"Bearer {token}"

    def get(self, url: str, params: dict[str, str | int]) -> dict[str, Any]:
        """GET a Hub endpoint that answers with JSON."""
        response = self._session.get(url, params=params, timeout=TIMEOUT)
        if not response.ok:
            reason = f"{url} failed (HTTP {response.status_code})"
            raise PruneError(reason)
        return response.json()

    def manifests(self, repo: str) -> list[Manifest]:
        """Every manifest in the repository, tagged or not."""
        url = f"{HUB_API}/namespaces/{_namespace(repo)}/repositories/{_name(repo)}/manifests"
        params: dict[str, str | int] = {"page_size": PAGE_SIZE}
        manifests: list[Manifest] = []
        for page in range(MAX_PAGES):
            body = self.get(url, params)
            entries = body.get("manifests") or body.get("results") or []
            manifests.extend(Manifest.from_hub(entry) for entry in entries)
            cursor = body.get("last_evaluated_key")
            # Page numbers are ignored here; the cursor is the only way on.
            if not cursor or len(entries) < PAGE_SIZE:
                return manifests
            params = {"page_size": PAGE_SIZE, "last_evaluated_key": cursor}
            if page == MAX_PAGES - 1:
                reason = (
                    f"the manifest listing did not end after {MAX_PAGES} pages; "
                    "refusing to work from a partial view of the repository"
                )
                raise PruneError(reason)
        return manifests

    def tags(self, repo: str) -> Iterator[dict[str, Any]]:
        """Every current tag in the repository."""
        url = f"{HUB_API}/namespaces/{_namespace(repo)}/repositories/{_name(repo)}/tags"
        page = 1
        while True:
            body = self.get(url, {"page_size": PAGE_SIZE, "page": page})
            yield from body.get("results") or ()
            if not body.get("next"):
                return
            page += 1


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class RegistrySession:
    """Registry client that keeps its short-lived token fresh."""

    def __init__(self, repo: str, user: str, secret: str) -> None:
        """Prepare a session; the token is fetched on first use."""
        self._repo = repo
        self._auth = HTTPBasicAuth(user, secret)
        self._session = requests.Session()
        self._expires = datetime.now(tz=UTC)
        self._token = ""

    def _reissue(self) -> None:
        """Get a fresh pull/delete token for this repository."""
        response = self._session.get(
            REGISTRY_AUTH,
            params={
                "service": "registry.docker.io",
                "scope": f"repository:{self._repo}:pull,delete",
            },
            auth=self._auth,
            timeout=TIMEOUT,
        )
        if not response.ok:
            reason = f"registry auth failed (HTTP {response.status_code})"
            raise PruneError(reason)
        body = response.json()
        self._token = body.get("token") or body.get("access_token") or ""
        if not self._token:
            reason = "registry returned no token"
            raise PruneError(reason)
        lifetime = int(body.get("expires_in") or DEFAULT_TOKEN_LIFETIME)
        self._expires = datetime.now(tz=UTC) + timedelta(
            seconds=max(lifetime - TOKEN_LEEWAY, 1)
        )

    def _request(self, method: str, digest: str, accept: str = "") -> requests.Response:
        """Call the registry, reissuing the token before and after it lapses."""
        if datetime.now(tz=UTC) >= self._expires:
            self._reissue()
        url = f"{REGISTRY_API}/{self._repo}/manifests/{digest}"
        headers = {"Accept": accept} if accept else {}
        response = requests.Response()
        for attempt in range(MAX_ATTEMPTS):
            headers["Authorization"] = f"Bearer {self._token}"
            response = self._session.request(
                method, url, headers=headers, timeout=TIMEOUT
            )
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                # A long prune outlives its token even with the leeway.
                self._reissue()
                continue
            if response.status_code in RETRY_STATUSES:
                time.sleep(RETRY_WAIT * (attempt + 1))
                continue
            break
        return response

    def manifest(self, digest: str) -> dict[str, Any] | None:
        """Read the manifest at this digest, or None when it is already gone."""
        response = self._request("GET", digest, accept=ACCEPT_MANIFESTS)
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        if not response.ok:
            reason = f"could not read manifest {digest} (HTTP {response.status_code})"
            raise PruneError(reason)
        return response.json()

    def delete(self, digest: str) -> int:
        """Delete the manifest at this digest, returning the status code."""
        return self._request("DELETE", digest).status_code


# ---------------------------------------------------------------------------
# The prune
# ---------------------------------------------------------------------------


def _namespace(repo: str) -> str:
    return repo.split("/", 1)[0]


def _name(repo: str) -> str:
    return repo.split("/", 1)[1]


def _tag_reach(hub: HubSession, repo: str) -> tuple[set[str], set[str]]:
    """Read the tag list: the tagged digests, and the architectures beneath them."""
    tagged: set[str] = set()
    children: set[str] = set()
    for tag in hub.tags(repo):
        digest = tag.get("digest")
        if digest:
            tagged.add(digest)
        # The tag list names each architecture but omits attestations.
        for image in tag.get("images") or ():
            child = image.get("digest")
            if child:
                children.add(child)
    return tagged, children


def live_digests(hub: HubSession, registry: RegistrySession, repo: str) -> set[str]:
    """Every digest a tag reaches, directly or through an index."""
    tagged, live = _tag_reach(hub, repo)
    if not tagged:
        reason = (
            f"{repo} has no tags; refusing to prune a repository whose live set "
            "cannot be established -- every manifest would look stale"
        )
        raise PruneError(reason)
    live |= tagged
    for digest in sorted(tagged):
        index = registry.manifest(digest)
        if index is None:
            reason = (
                f"tagged manifest {digest} is missing from the registry; "
                "aborting rather than mistaking its children for stale"
            )
            raise PruneError(reason)
        live.update(
            child["digest"]
            for child in index.get("manifests") or ()
            if child.get("digest")
        )
    return live


def select_stale(
    manifests: list[Manifest], live: set[str], cutoff: str
) -> list[Manifest]:
    """Pick the debris: manifests untagged, unreachable, and old enough."""
    return [
        manifest
        for manifest in manifests
        if not manifest.tags
        and manifest.digest not in live
        and (
            not cutoff
            or (manifest.last_pushed < cutoff and manifest.last_pulled < cutoff)
        )
    ]


def human_size(size: float) -> str:
    """Bytes in units a person reads."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:  # noqa: PLR2004
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _day(stamp: str) -> str:
    return stamp[:10] if stamp else "never     "


def report(stale: list[Manifest]) -> None:
    """Print what would go, and roughly how much room it frees."""
    total = sum(manifest.size for manifest in stale)
    print(f"  {len(stale)} stale manifest(s), up to {human_size(total)} reclaimable:")
    for manifest in stale:
        pushed = _day(manifest.last_pushed)
        pulled = _day(manifest.last_pulled)
        digest = manifest.digest[:19]
        print(
            f"    {manifest.kind} {digest}  {manifest.platform:<12}  pushed={pushed}  pulled={pulled}"
        )


def delete_stale(registry: RegistrySession, stale: list[Manifest]) -> int:
    """Delete the debris, indexes first. Returns the number that failed."""
    # While an index stands its children are still referenced, and the
    # registry would rightly refuse to delete them.
    ordered = [m for m in stale if m.is_index] + [m for m in stale if not m.is_index]
    failed = 0
    for number, manifest in enumerate(ordered, start=1):
        status = registry.delete(manifest.digest)
        prefix = f"    [{number}/{len(ordered)}]"
        if status in DELETED_STATUSES:
            print(f"{prefix} deleted {manifest.digest[:19]}")
        elif status == HTTPStatus.FORBIDDEN:
            note = "the registry says it is still referenced"
            print(f"{prefix} refused {manifest.digest[:19]}: {note}", file=sys.stderr)
            failed += 1
        else:
            print(
                f"{prefix} FAILED  {manifest.digest[:19]}: HTTP {status}",
                file=sys.stderr,
            )
            failed += 1
    return failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> ArgumentParser:
    """Build cli arg parser."""
    parser = ArgumentParser(
        description=(
            "Delete the stale images and image indexes from a Docker Hub "
            "repository: the manifests no tag reaches, directly or through an "
            "index. Everything a tag reaches is left alone, including the "
            "per-architecture images and attestations that sit untagged "
            "beneath a multi-arch tag."
        ),
        formatter_class=RawDescriptionHelpFormatter,
        epilog=(
            "Credentials come from DOCKER_USER and DOCKER_PASS. A personal\n"
            "access token needs the Read, Write, Delete scope.\n"
            "Dry run unless --execute is given."
        ),
    )
    parser.add_argument(
        "repository",
        metavar="NAMESPACE/REPOSITORY",
        help="e.g. ajslater/codex. A bare name uses $DOCKER_USER as the namespace.",
    )
    parser.add_argument(
        "--min-age",
        type=int,
        default=0,
        metavar="DAYS",
        help=(
            "Only delete manifests whose last push and last pull are both older "
            "than DAYS. Keeps a push that is still in flight out of the blast radius."
        ),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete. Without it, only report.",
    )
    return parser


def _credentials() -> tuple[str, str]:
    user = os.environ.get("DOCKER_USER", "")
    secret = os.environ.get("DOCKER_PASS", "")
    if not user or not secret:
        reason = "DOCKER_USER and DOCKER_PASS must be set"
        raise PruneError(reason)
    return user, secret


def prune(repo: str, min_age: int, *, execute: bool) -> int:
    """Find the stale manifests and, when told to, delete them."""
    user, secret = _credentials()
    if "/" not in repo:
        repo = f"{user}/{repo}"
    print(f"[{'EXECUTE' if execute else 'DRY RUN'}] {repo}")

    hub = HubSession(user, secret)
    registry = RegistrySession(repo, user, secret)
    manifests = hub.manifests(repo)
    if not manifests:
        print("  Repository holds no manifests. Nothing to do.")
        return 0
    live = live_digests(hub, registry, repo)

    cutoff = ""
    if min_age:
        moment = datetime.now(tz=UTC) - timedelta(days=min_age)
        cutoff = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"  Age filter: last push and last pull both before {cutoff}")

    print(
        f"  {len(manifests)} manifest(s) in the repository, {len(live)} reachable from a tag."
    )
    stale = select_stale(manifests, live, cutoff)
    if not stale:
        print("  No stale manifests. Nothing to delete.")
        return 0
    report(stale)

    if not execute:
        print("\nDry run only. Re-run with --execute to delete.")
        return 0

    print("  Deleting...")
    failed = delete_stale(registry, stale)
    print(f"  Deleted {len(stale) - failed} manifest(s).")
    if failed:
        print(f"  {failed} deletion(s) did not succeed.", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    """Run program."""
    args = build_parser().parse_args()
    try:
        sys.exit(prune(args.repository, args.min_age, execute=args.execute))
    except PruneError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
