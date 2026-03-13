#!/usr/bin/env bash
# Update npm dependencies
set -euo pipefail
npm update
npm outdated || true
