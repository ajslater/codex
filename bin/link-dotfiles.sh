#!/usr/bin/env bash
# Merge development environment dotfiles
set -euo pipefail
DEVENV_PATH=.

FNS=(.readthedocs.yaml .shellcheckrc)

for f in "${FNS[@]}"; do
  ln -si "$DEVENV_PATH/$f" .
done
