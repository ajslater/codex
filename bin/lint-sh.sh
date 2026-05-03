#!/usr/bin/env bash
# Lint shell scripts
set -euxo pipefail

shellharden --check ./**/*.sh
shellcheck --external-sources ./**/*.sh
