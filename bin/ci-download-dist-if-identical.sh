#!/usr/bin/env bash
# Download last dist artifacts if current code is identical to the merge source.
set -euo pipefail

PR_DATA=$(gh pr list --state merged --limit 1 --json headRefName,headRefOid \
  --template '{{range .}}{{.headRefName}},{{.headRefOid}}{{end}}')

if [[ -z "$PR_DATA" ]]; then
  echo "No merge detected. Continue with Lint, Test, & Build."
  exit 0
fi

SOURCE_BRANCH="${PR_DATA%,*}"
SOURCE_SHA="${PR_DATA#*,}"
echo "A merge just happened from $SOURCE_BRANCH."

git fetch origin "$SOURCE_BRANCH" --depth=1
if ! git diff --quiet HEAD "origin/$SOURCE_BRANCH"; then
  echo "Code differs from $SOURCE_BRANCH. Continue with Lint, Test, & Build."
  exit 0
fi
echo "Code is identical to $SOURCE_BRANCH"

RUN_ID=$(gh api "repos/${GH_REPO}/actions/runs?head_sha=$SOURCE_SHA&status=success" \
  --jq '[.workflow_runs[] | select(.name=="CI")] | .[0].id')

if [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]]; then
  echo "No successful CI run found for commit $SOURCE_SHA"
  exit 0
fi

echo "Found CI run $RUN_ID for commit $SOURCE_SHA"
if gh run download "$RUN_ID" --name python-dist --dir dist; then
  echo "dist_found=true" >> "$GITHUB_OUTPUT"
  echo "Successfully retrieved dist from run $RUN_ID"
else
  echo "Failed to download python-dist artifact from run $RUN_ID"
fi
