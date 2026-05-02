#!/usr/bin/env bash
# Delete alpha-tagged container versions from ghcr.io/ajslater/codex.
# Alphas match a trailing aN like 1.11.0a4 or 1.11.0a10.
#
# Requires the gh CLI authenticated with the delete:packages scope:
#   gh auth refresh -h github.com -s delete:packages
#
# Dry-run by default. Pass --execute to actually delete.
set -euo pipefail

OWNER="ajslater"
PACKAGE="codex"
ALPHA_REGEX='^[0-9]+\.[0-9]+\.[0-9]+a[0-9]+$'

EXECUTE=0
for arg in "$@"; do
  case "$arg" in
  --execute) EXECUTE=1 ;;
  -h | --help)
    cat <<EOF
Usage: $0 [--execute]

Lists alpha-tagged versions of ghcr.io/${OWNER}/${PACKAGE} and (with
--execute) deletes them. Without --execute, prints what would be removed.
EOF
    exit 0
    ;;
  *)
    echo "Unknown argument: $arg" >&2
    exit 2
    ;;
  esac
done

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI is required" >&2
  exit 1
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required" >&2
  exit 1
fi

mode="DRY RUN"
if [[ "$EXECUTE" -eq 1 ]]; then
  mode="EXECUTE"
fi
echo "[$mode] Scanning ghcr.io/${OWNER}/${PACKAGE} for alpha versions..."

# Paginate all container versions for the user package.
versions_json=$(
  gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    --paginate \
    "/users/${OWNER}/packages/container/${PACKAGE}/versions" \
    --jq '.[] | {id: .id, tags: .metadata.container.tags}'
)

# Pick versions whose tag list contains at least one alpha tag.
matches=$(
  echo "$versions_json" |
    jq -c --arg re "$ALPHA_REGEX" \
      'select(.tags | map(test($re)) | any)'
)

if [[ -z "$matches" ]]; then
  echo "No alpha versions found."
  exit 0
fi

count=$(echo "$matches" | wc -l | tr -d ' ')
echo "Found $count alpha version(s):"
echo "$matches" | jq -r '"  id=\(.id) tags=\(.tags | join(","))"'

if [[ "$EXECUTE" -ne 1 ]]; then
  echo
  echo "Dry run only. Re-run with --execute to delete."
  exit 0
fi

echo
echo "Deleting..."
fail=0
while IFS= read -r row; do
  id=$(echo "$row" | jq -r '.id')
  tags=$(echo "$row" | jq -r '.tags | join(",")')
  echo "  deleting id=$id tags=$tags"
  if ! gh api \
    --method DELETE \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/users/${OWNER}/packages/container/${PACKAGE}/versions/${id}"; then
    echo "    FAILED" >&2
    fail=1
  fi
done <<<"$matches"

if [[ "$fail" -ne 0 ]]; then
  echo "One or more deletions failed." >&2
  exit 1
fi
echo "Done."
