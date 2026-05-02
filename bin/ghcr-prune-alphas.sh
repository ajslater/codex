#!/usr/bin/env bash
# Prune container versions from ghcr.io/ajslater/codex.
#
# Two modes (combinable):
#   - alphas (default): delete versions tagged like 1.11.0a4, 1.11.0a10,
#     and their per-arch siblings 1.11.0a4-amd64 / 1.11.0a4-arm64.
#   - --orphans: also delete untagged versions whose digest is not
#     referenced by any currently-tagged manifest list (e.g. old
#     manifests left behind when a tag was overwritten, or attestation
#     manifests whose parent was deleted).
#   - --orphans-only: skip alphas, only prune orphans.
#
# Requires the gh CLI authenticated with delete:packages:
#   gh auth refresh -h github.com -s delete:packages
#
# Dry-run by default. Pass --execute to actually delete.
set -euo pipefail

OWNER="ajslater"
PACKAGE="codex"
ALPHA_REGEX='^[0-9]+\.[0-9]+\.[0-9]+a[0-9]+(-(amd64|arm64))?$'

EXECUTE=0
DO_ALPHAS=1
DO_ORPHANS=0
for arg in "$@"; do
  case "$arg" in
  --execute) EXECUTE=1 ;;
  --orphans) DO_ORPHANS=1 ;;
  --orphans-only)
    DO_ORPHANS=1
    DO_ALPHAS=0
    ;;
  -h | --help)
    cat <<EOF
Usage: $0 [--orphans|--orphans-only] [--execute]

Prunes container versions from ghcr.io/${OWNER}/${PACKAGE}.

Modes (default: alphas only):
  (default)        Delete alpha-tagged versions, including
                   1.11.0aN-amd64 and 1.11.0aN-arm64 siblings.
  --orphans        Also delete untagged orphan versions.
  --orphans-only   Skip alphas; only delete orphans.

Without --execute, prints what would be removed.
EOF
    exit 0
    ;;
  *)
    echo "Unknown argument: $arg" >&2
    exit 2
    ;;
  esac
done

for cmd in gh jq curl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "error: $cmd is required" >&2
    exit 1
  fi
done

mode_label="DRY RUN"
if [[ "$EXECUTE" -eq 1 ]]; then
  mode_label="EXECUTE"
fi

api_versions() {
  gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    --paginate \
    "/users/${OWNER}/packages/container/${PACKAGE}/versions" \
    --jq '.[] | {id: .id, name: .name, tags: .metadata.container.tags}'
}

delete_version() {
  gh api \
    --method DELETE \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/users/${OWNER}/packages/container/${PACKAGE}/versions/$1"
}

prune_alphas() {
  echo "[$mode_label] Scanning for alpha versions (incl. -amd64/-arm64 siblings)..."
  local versions matches count fail row id tags
  versions=$(api_versions)
  matches=$(
    echo "$versions" |
      jq -c --arg re "$ALPHA_REGEX" \
        'select(.tags | map(test($re)) | any)'
  )
  if [[ -z "$matches" ]]; then
    echo "  No alpha versions found."
    return 0
  fi
  count=$(echo "$matches" | wc -l | tr -d ' ')
  echo "  Found $count alpha version(s):"
  echo "$matches" | jq -r '"    id=\(.id) tags=\(.tags | join(","))"'
  if [[ "$EXECUTE" -ne 1 ]]; then
    return 0
  fi
  echo "  Deleting..."
  fail=0
  while IFS= read -r row; do
    id=$(echo "$row" | jq -r '.id')
    tags=$(echo "$row" | jq -r '.tags | join(",")')
    echo "    deleting id=$id tags=$tags"
    if ! delete_version "$id" >/dev/null; then
      echo "      FAILED" >&2
      fail=1
    fi
  done <<<"$matches"
  if [[ "$fail" -ne 0 ]]; then
    echo "  Some alpha deletions failed." >&2
    return 1
  fi
}

prune_orphans() {
  echo "[$mode_label] Scanning for untagged orphan versions..."

  # Anonymous registry pull token (the package is public).
  local token
  token=$(
    curl -fsSL "https://ghcr.io/token?scope=repository:${OWNER}/${PACKAGE}:pull" |
      jq -r '.token // .access_token // empty'
  )
  if [[ -z "$token" ]]; then
    echo "  error: failed to obtain ghcr.io registry token" >&2
    return 1
  fi

  local versions tagged_digests
  versions=$(api_versions)
  tagged_digests=$(
    echo "$versions" |
      jq -r 'select(.tags | length > 0) | .name'
  )

  if [[ -z "$tagged_digests" ]]; then
    echo "  error: no tagged versions found; refusing to mass-delete untagged" >&2
    return 1
  fi

  echo "  Walking tagged manifests for child references..."
  local accept_hdr
  accept_hdr="application/vnd.oci.image.index.v1+json"
  accept_hdr="$accept_hdr,application/vnd.docker.distribution.manifest.list.v2+json"
  accept_hdr="$accept_hdr,application/vnd.oci.image.manifest.v1+json"
  accept_hdr="$accept_hdr,application/vnd.docker.distribution.manifest.v2+json"

  local referenced_digests="" digest body children
  while IFS= read -r digest; do
    [[ -z "$digest" ]] && continue
    body=$(
      curl -fsSL \
        -H "Authorization: Bearer $token" \
        -H "Accept: $accept_hdr" \
        "https://ghcr.io/v2/${OWNER}/${PACKAGE}/manifests/${digest}" 2>/dev/null ||
        true
    )
    [[ -z "$body" ]] && continue
    children=$(echo "$body" | jq -r '(.manifests // [])[].digest // empty')
    [[ -n "$children" ]] && referenced_digests+=$'\n'"$children"
  done <<<"$tagged_digests"

  local live_set live_json
  live_set=$(
    printf "%s\n%s\n" "$tagged_digests" "$referenced_digests" |
      grep -E '^sha256:' | sort -u
  )
  if [[ -z "$live_set" ]]; then
    echo "  error: live digest set empty; aborting to avoid mass deletion" >&2
    return 1
  fi
  live_json=$(echo "$live_set" | jq -R . | jq -s .)

  local orphans count fail row id name
  orphans=$(
    echo "$versions" |
      jq -c --argjson live "$live_json" \
        'select((.tags | length) == 0)
         | select(.name as $n | ($live | index($n)) | not)'
  )

  if [[ -z "$orphans" ]]; then
    echo "  No orphan versions found."
    return 0
  fi
  count=$(echo "$orphans" | wc -l | tr -d ' ')
  echo "  Found $count orphan version(s):"
  echo "$orphans" | jq -r '"    id=\(.id) digest=\(.name)"'
  if [[ "$EXECUTE" -ne 1 ]]; then
    return 0
  fi
  echo "  Deleting..."
  fail=0
  while IFS= read -r row; do
    id=$(echo "$row" | jq -r '.id')
    name=$(echo "$row" | jq -r '.name')
    echo "    deleting id=$id digest=$name"
    if ! delete_version "$id" >/dev/null; then
      echo "      FAILED" >&2
      fail=1
    fi
  done <<<"$orphans"
  if [[ "$fail" -ne 0 ]]; then
    echo "  Some orphan deletions failed." >&2
    return 1
  fi
}

ec=0
[[ "$DO_ALPHAS" -eq 1 ]] && { prune_alphas || ec=$?; }
[[ "$DO_ORPHANS" -eq 1 ]] && { prune_orphans || ec=$?; }

if [[ "$EXECUTE" -ne 1 ]]; then
  echo
  echo "Dry run only. Re-run with --execute to delete."
fi
exit "$ec"
