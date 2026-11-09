#!/usr/bin/env bash
# Delete local git branches except main, master, develop, pre-release, those
# named in .keep-branches and those checked out in a worktree
#
# Usage: bin/prune-branches.sh [-n] [-f]
#   -n  list the branches it would delete and delete none
#   -f  delete unmerged branches too, with git branch -D
#
# Without -f, git branch -d keeps each branch not merged into its upstream or,
# lacking one, HEAD, and the run fails after deleting the rest.
#
# .keep-branches, at the project root, holds one branch name per line:
#   - Blank lines and lines starting with # are ignored.
#   - * ? and [...] are glob characters: release/* keeps every release branch.
#
# A branch checked out in any worktree, which git branch marks with * or +,
# is always kept.
set -euo pipefail

usage() {
  echo "usage: $0 [-n] [-f]" >&2
  exit 2
}

dry_run=false
delete=-d
while getopts nf opt; do
  case $opt in
  n) dry_run=true ;;
  f) delete=-D ;;
  *) usage ;;
  esac
done
shift $((OPTIND - 1))
if (($#)); then
  usage
fi

# Read .keep-branches from the root even when run from a subdirectory.
root=$(git rev-parse --show-toplevel)
cd "$root"

keep=(main master develop pre-release)
if [[ -f .keep-branches ]]; then
  # Branch names hold no whitespace, so only the first word counts.
  while read -r name _ || [[ -n $name ]]; do
    name=${name//$'\r'/}
    case $name in
    '' | '#'*) continue ;;
    esac
    keep+=("$name")
  done <.keep-branches
fi

is_kept() {
  local pattern
  for pattern in "${keep[@]}"; do
    # Unquoted, so the pattern is a glob.
    # shellcheck disable=SC2053
    if [[ $1 == $pattern ]]; then
      return 0
    fi
  done
  return 1
}

# worktreepath is set for a branch checked out in any worktree.
refs=$(git for-each-ref --format='%(refname:lstrip=2)%09%(worktreepath)' refs/heads)
branches=()
while IFS=$'\t' read -r branch worktree; do
  if [[ -n $branch && -z $worktree ]] && ! is_kept "$branch"; then
    branches+=("$branch")
  fi
done <<<"$refs"

# Bash 3.2 takes an empty "${branches[@]}" for unbound under set -u.
if ((${#branches[@]} == 0)); then
  echo "No branches to delete."
  exit 0
fi

if [[ $dry_run == true ]]; then
  printf 'Would delete %s\n' "${branches[@]}"
  exit 0
fi

if ! git branch "$delete" -- "${branches[@]}"; then
  echo "Kept the unmerged branches above. -f deletes them too." >&2
  exit 1
fi
