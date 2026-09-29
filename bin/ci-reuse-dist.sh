#!/usr/bin/env bash
# Reuse python-dist from an earlier CI run that passed on this exact tree.
#
# devenv-check's result job uploads a ci-passed-<tree> marker artifact when
# lint, test and build all pass. Find the newest live marker for HEAD's tree
# and download that run's python-dist into dist/. On a pull request run the
# tree is the merge ref's, which is what a squash merge onto an unchanged
# base produces, so a main push reuses the dist its PR already tested.
#
# Runs from fork pull requests are ignored: a fork controls its own workflow
# and could upload a forged marker for a tree it can predict.
#
# Any failure falls through to a full lint, test and build.
#
# Environment: GH_REPO, GH_TOKEN, GITHUB_OUTPUT, GITHUB_RUN_ID
# Outputs: dist_found=true and source_run_id=<run id> on reuse.
set -euo pipefail

TREE=$(git rev-parse 'HEAD^{tree}')
MARKER="ci-passed-$TREE"
CONTINUE="Continue with Lint, Test & Build."

if ! ARTIFACTS=$(gh api "repos/$GH_REPO/actions/artifacts?name=$MARKER&per_page=100"); then
  echo "::warning::Could not list artifacts for tree $TREE. $CONTINUE"
  exit 0
fi

RUN_ID=$(jq -r --argjson run "${GITHUB_RUN_ID:-0}" '
  [.artifacts[]
    | select(.expired | not)
    | select(.workflow_run.head_repository_id == .workflow_run.repository_id)
    | select(.workflow_run.id != $run)]
  | max_by(.created_at)
  | .workflow_run.id // empty' <<<"$ARTIFACTS")

if [[ -z $RUN_ID ]]; then
  echo "No earlier run passed on tree $TREE. $CONTINUE"
  exit 0
fi

echo "Tree $TREE passed in CI run $RUN_ID"
if gh run download "$RUN_ID" --name python-dist --dir dist; then
  echo "dist_found=true" >>"$GITHUB_OUTPUT"
  echo "source_run_id=$RUN_ID" >>"$GITHUB_OUTPUT"
  echo "Reusing python-dist from run $RUN_ID"
else
  echo "Could not download python-dist from run $RUN_ID. $CONTINUE"
fi
