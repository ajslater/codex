#!/usr/bin/env bash
# Lint checks
set -euxo pipefail

# Javascript, JSON, Markdown, YAML #####
npm run lint

bin/lint-darwin.sh

bin/roman.sh -i .prettierignore .
