#!/usr/bin/env bash
# Tag a release, publish its GitHub Release and merge main into develop.
#
# Usage: bin/release-tag.sh [--dry-run] [preflight|tag|publish|merge-back|all] [VERSION]
#
# One engine for the CI release job, the CI Release Preflight step and a
# local run. The default subcommand is all.
#
#   preflight   Read-only. A final version has a NEWS.md section, and the
#               tag is absent or already at the release commit.
#   tag         Push the lightweight tag vX.Y.Z at the release commit. An
#               existing tag is never moved or forced.
#   publish     Create the GitHub Release, titled and described by the
#               version's NEWS.md section. An existing release is never edited.
#   merge-back  Merge the release commit into develop and push develop.
#   all         preflight, tag, publish, merge-back.
#
# The release commit is $RELEASE_SHA in CI, and $RELEASE_REMOTE/main after a
# fetch when run locally. The version, title and notes come from
# pyproject.toml and NEWS.md at that commit, never from the working tree.
# merge-back works in a temporary worktree, so the caller's checkout, branch
# and local tags are never touched.
#
# VERSION is only an assertion: the run fails unless pyproject.toml at the
# release commit has that version. It used to be the tag itself.
#
# Every step checks before it writes, so a re-run finishes a partial release
# and is otherwise a no-op.
#
# Environment:
#   RELEASE_SHA      the release commit (CI passes github.sha)
#   RELEASE_REMOTE   the remote to read and push (default origin)
#   RELEASE_DRY_RUN  1 prints each remote write instead of running it,
#                    the same as --dry-run
set -euo pipefail

REMOTE=${RELEASE_REMOTE:-origin}
DRY_RUN=${RELEASE_DRY_RUN:-0}
MAIN=main
DEVELOP=develop
MERGE_MSG="Merge branch '$MAIN' into $DEVELOP"
WORKFLOWS=.github/workflows
PUSH_ATTEMPTS=3
BIN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RELEASE_INFO="$BIN_DIR/release_info.py"

usage() {
  echo "Usage: bin/release-tag.sh [--dry-run] [preflight|tag|publish|merge-back|all] [VERSION]"
}

in_actions() {
  [ "${GITHUB_ACTIONS:-}" = true ]
}

die() {
  if in_actions; then
    echo "::error::$*" >&2
  else
    echo "ERROR: $*" >&2
  fi
  exit 1
}

warn() {
  if in_actions; then
    echo "::warning::$*" >&2
  else
    echo "WARNING: $*" >&2
  fi
}

notice() {
  if in_actions; then
    echo "::notice::$*"
  else
    echo "$*"
  fi
}

summary() {
  if [ "${GITHUB_STEP_SUMMARY:-}" != "" ]; then
    echo "$*" >>"$GITHUB_STEP_SUMMARY"
  fi
}

# Every remote write goes through run, so --dry-run can skip it.
run() {
  printf '+'
  printf ' %q' "$@"
  printf '\n'
  if [ "$DRY_RUN" = 1 ]; then
    echo "  (dry run: not run)"
    return 0
  fi
  "$@"
}

# Update remote-tracking branches only. --no-tags keeps tag auto-following
# from creating local tags.
fetch_branches() {
  local name refspecs
  refspecs=()
  for name in "$@"; do
    refspecs+=("+refs/heads/$name:refs/remotes/$REMOTE/$name")
  done
  git fetch --quiet --no-tags "$REMOTE" "${refspecs[@]}"
}

###############################################################################
# Arguments
###############################################################################
CMD=all
EXPECTED=""
while [ $# -gt 0 ]; do
  case "$1" in
  --dry-run) DRY_RUN=1 ;;
  -h | --help)
    usage
    exit 0
    ;;
  preflight | tag | publish | merge-back | all) CMD=$1 ;;
  -*)
    usage >&2
    die "unknown option $1"
    ;;
  *)
    [ "$EXPECTED" = "" ] || die "more than one VERSION given"
    EXPECTED=$1
    ;;
  esac
  shift
done

###############################################################################
# The release: commit, version, tag, title and notes
###############################################################################
TMP=$(mktemp -d)
WT="$TMP/wt"

remove_worktree() {
  if [ -e "$WT" ]; then
    git worktree remove --force "$WT"
  fi
}

cleanup() {
  remove_worktree >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

if [ "${RELEASE_SHA:-}" != "" ]; then
  SHA=$(git rev-parse --verify --quiet "$RELEASE_SHA^{commit}") ||
    die "RELEASE_SHA $RELEASE_SHA is not a commit in this repository"
else
  fetch_branches "$MAIN" "$DEVELOP"
  SHA=$(git rev-parse --verify "$REMOTE/$MAIN^{commit}")
fi
SHORT=${SHA:0:7}

git show "$SHA:pyproject.toml" >"$TMP/pyproject.toml" ||
  die "no pyproject.toml at $SHORT"
git show "$SHA:NEWS.md" >"$TMP/NEWS.md" || die "no NEWS.md at $SHORT"
INFO_ARGS=(info --pyproject "$TMP/pyproject.toml" --news "$TMP/NEWS.md"
  --notes-file "$TMP/notes.md")
if [ "$EXPECTED" != "" ]; then
  INFO_ARGS+=(--version "$EXPECTED")
fi
python3 "$RELEASE_INFO" "${INFO_ARGS[@]}" >"$TMP/info"

VERSION=""
TAG=""
FINAL=""
TITLE=""
while IFS='=' read -r key value; do
  case "$key" in
  version) VERSION=$value ;;
  tag) TAG=$value ;;
  final) FINAL=$value ;;
  title) TITLE=$value ;;
  esac
done <"$TMP/info"
[ "$TAG" != "" ] || die "release_info.py reported no tag"

if [ "$DRY_RUN" = 1 ]; then
  echo "DRY RUN: remote writes are printed, not run."
fi
echo "Release $TAG \"$TITLE\" at $SHORT (final: $FINAL) on $REMOTE"

###############################################################################
# preflight
###############################################################################
TAG_AT=""

# The commit the remote tag points at, or nothing. A hand-made annotated tag
# lists its commit on the peeled ^{} line, so that line wins.
remote_tag_sha() {
  local lines
  lines=$(git ls-remote --tags "$REMOTE" "refs/tags/$TAG" "refs/tags/$TAG^{}") ||
    return 1
  printf '%s\n' "$lines" | awk -v ref="refs/tags/$TAG" '
    $2 == ref "^{}" { peeled = $1 }
    $2 == ref { direct = $1 }
    END { print (peeled != "" ? peeled : direct) }'
}

check_tag() {
  TAG_AT=$(remote_tag_sha) || die "could not list tags on $REMOTE"
  if [ "$TAG_AT" != "" ] && [ "$TAG_AT" != "$SHA" ]; then
    die "$TAG already released at ${TAG_AT:0:7}; bump the version (bin/version-python.sh) on the PR branch"
  fi
}

cmd_preflight() {
  check_tag
  if [ "$TAG_AT" != "" ]; then
    echo "preflight: $TAG is already tagged at $SHORT"
  else
    echo "preflight: $TAG is not tagged yet"
  fi
  echo "preflight: ok"
}

###############################################################################
# tag
###############################################################################
cmd_tag() {
  local main_at
  check_tag
  if [ "$TAG_AT" = "$SHA" ]; then
    echo "tag: $TAG already at $SHORT; skip"
    summary "- Tag \`$TAG\` was already at \`$SHORT\`."
    return 0
  fi
  main_at=$(git ls-remote "$REMOTE" "refs/heads/$MAIN" | awk '{ print $1 }')
  if [ "$main_at" != "$SHA" ]; then
    fetch_branches "$MAIN"
    if ! git diff --quiet "$SHA" "$REMOTE/$MAIN" -- "$WORKFLOWS"; then
      warn "$MAIN moved past $SHORT and $WORKFLOWS differ; the GITHUB_TOKEN may be refused the $TAG push"
    fi
  fi
  run git push "$REMOTE" "$SHA:refs/tags/$TAG" ||
    die "could not push $TAG; tag it locally: RELEASE_SHA=$SHA bin/release-tag.sh tag"
  summary "- Tag \`$TAG\` pushed at \`$SHORT\`."
}

###############################################################################
# publish
###############################################################################

# Print missing, draft or published.
release_state() {
  local draft
  if draft=$(gh release view "$TAG" --json isDraft --jq .isDraft 2>"$TMP/gh.err"); then
    if [ "$draft" = true ]; then
      echo draft
    else
      echo published
    fi
  elif grep -q 'release not found' "$TMP/gh.err"; then
    echo missing
  else
    cat "$TMP/gh.err" >&2
    return 1
  fi
}

cmd_publish() {
  local state latest flags
  state=$(release_state) || die "gh release view $TAG failed"
  case "$state" in
  published)
    notice "publish: GitHub Release $TAG already exists; left untouched"
    summary "- GitHub Release \`$TAG\` already existed; left untouched."
    return 0
    ;;
  draft)
    warn "publish: GitHub Release $TAG exists as a draft; left untouched"
    summary "- GitHub Release \`$TAG\` is a draft; left untouched."
    return 0
    ;;
  esac
  latest=$(git ls-remote --tags --refs "$REMOTE" 'v*' |
    python3 "$RELEASE_INFO" is-latest --version "$VERSION") ||
    die "could not work out whether $TAG is the latest release"
  if [ "$FINAL" != true ]; then
    flags=(--prerelease --latest=false)
  elif [ "$latest" = true ]; then
    flags=(--latest)
  else
    flags=(--latest=false)
  fi
  if ! run gh release create "$TAG" --verify-tag --title "$TITLE" \
    --notes-file "$TMP/notes.md" "${flags[@]}"; then
    # Another run may have created it in the meantime.
    state=$(release_state) || die "gh release create $TAG failed"
    [ "$state" != missing ] ||
      die "gh release create $TAG failed; is the tag pushed? (bin/release-tag.sh tag)"
    echo "publish: GitHub Release $TAG exists now; ok"
  fi
  summary "- GitHub Release \`$TAG\`: $TITLE (${flags[*]})."
}

###############################################################################
# merge-back
###############################################################################
WF_CHANGED=""

# Merge the release commit into a fresh worktree of the remote develop.
merge_into_develop() {
  local sha_tree conflicts
  remove_worktree
  git worktree add --quiet --detach "$WT" "$REMOTE/$DEVELOP"
  WF_CHANGED=""
  sha_tree=$(git rev-parse "$SHA^{tree}")
  git log --format=%T "$SHA..$REMOTE/$DEVELOP" >"$TMP/develop-trees"
  if grep -qxF "$sha_tree" "$TMP/develop-trees"; then
    # A squash release: develop already has main's exact tree. Record the
    # ancestry and keep develop's tree, so this cannot conflict and leaves
    # develop's workflow files alone.
    echo "merge-back: $DEVELOP already has $SHORT's tree; merging with -s ours"
    git -C "$WT" merge --quiet --no-verify -s ours -m "$MERGE_MSG" "$SHA"
    return 0
  fi
  echo "merge-back: $MAIN has changes $DEVELOP lacks; merging normally"
  if ! git -C "$WT" merge --quiet --no-verify --no-edit -m "$MERGE_MSG" "$SHA"; then
    conflicts=$(git -C "$WT" diff --name-only --diff-filter=U | tr '\n' ' ')
    git -C "$WT" merge --abort || true
    echo "Finish by hand: git switch $DEVELOP && git pull && git merge $REMOTE/$MAIN," \
      "resolve, push, then re-run (a no-op once $DEVELOP contains $SHORT)." >&2
    die "merging $SHORT into $DEVELOP conflicts in: ${conflicts% }"
  fi
  WF_CHANGED=$(git -C "$WT" diff --name-only "$REMOTE/$DEVELOP" HEAD -- "$WORKFLOWS" | tr '\n' ' ')
  WF_CHANGED=${WF_CHANGED% }
  if [ "$WF_CHANGED" != "" ]; then
    warn "the merge changes $DEVELOP's workflow files ($WF_CHANGED); the GITHUB_TOKEN may be refused the push"
  fi
}

# Push the merge. Returns 1 when develop moved and the merge should be redone.
push_develop() {
  if run git -C "$WT" push --quiet "$REMOTE" "HEAD:refs/heads/$DEVELOP" 2>"$TMP/push.err"; then
    return 0
  fi
  cat "$TMP/push.err" >&2
  if grep -qE 'GH006|GH013|protected branch' "$TMP/push.err"; then
    die "$DEVELOP is protected against this push; allow it or run bin/release-tag.sh merge-back locally"
  fi
  if grep -qE 'non-fast-forward|fetch first' "$TMP/push.err"; then
    return 1
  fi
  if [ "$WF_CHANGED" != "" ]; then
    die "the GITHUB_TOKEN cannot push workflow changes ($WF_CHANGED); run bin/release-tag.sh merge-back locally or configure RELEASE_TOKEN"
  fi
  die "could not push $DEVELOP"
}

cmd_merge_back() {
  local attempt=1
  while [ "$attempt" -le "$PUSH_ATTEMPTS" ]; do
    fetch_branches "$DEVELOP"
    if git merge-base --is-ancestor "$SHA" "$REMOTE/$DEVELOP"; then
      echo "merge-back: $DEVELOP already contains $SHORT; skip"
      summary "- \`$DEVELOP\` already contained \`$SHORT\`."
      return 0
    fi
    merge_into_develop
    if push_develop; then
      summary "- Merged \`$SHORT\` into \`$DEVELOP\`."
      return 0
    fi
    echo "merge-back: $DEVELOP moved during the push; retrying ($attempt/$PUSH_ATTEMPTS)"
    attempt=$((attempt + 1))
  done
  die "could not push $DEVELOP after $PUSH_ATTEMPTS attempts"
}

###############################################################################
# Main
###############################################################################
case "$CMD" in
preflight) cmd_preflight ;;
tag) cmd_tag ;;
publish) cmd_publish ;;
merge-back) cmd_merge_back ;;
all)
  cmd_preflight
  cmd_tag
  cmd_publish
  cmd_merge_back
  ;;
esac
