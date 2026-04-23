#!/usr/bin/env bash
# Update npm dependencies
set -euo pipefail
bun update
bun outdated || true
