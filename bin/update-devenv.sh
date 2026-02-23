#!/usr/bin/env bash
# Update a project by merging the devenv templates
set -euo pipefail

DEVENV_SRC=../devenv

# Prepare
mkdir -pv bin cfg

# Update
bin/copy-new-files.sh "$DEVENV_SRC"/bin bin
bin/copy-new-files.sh "$DEVENV_SRC"/cfg cfg
bin/merge-dotfiles.sh "$DEVENV_SRC"/templates .
uv run bin/merge_package_json.py "$DEVENV_SRC"/templates/package.json package.json -o package.json
fix_files=(package.json)
if [ "${MERGE_PYTHON:-}" != "" ]; then
  uv run bin/merge_toml.py "$DEVENV_SRC"/templates/pyproject-template.toml pyproject.toml -o pyproject.toml
  fix_files+=(pyproject.toml)
fi
if [ "${MERGE_DOCS:-}" != "" ]; then
  uv run bin/merge_yaml.py "$DEVENV_SRC"/templates/.readthedocs.yaml .readthedocs.yaml -o .readthedocs.yaml
  uv run bin/merge_yaml.py "$DEVENV_SRC"/templates/mkdocs.yml mkdocs.yml -o mkdocs.yml
  fix_files+=(.readthedocs.yaml mkdocs.yml)
fi

# Fix Merged
npm update
npx eslint_d --cache --fix "${fix_files[@]}"
npx prettier --write "${fix_files[@]}"

# Report
git status --short "${fix_files[@]}"
