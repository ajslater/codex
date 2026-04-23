#!/usr/bin/env bash
# Update bun dependencies
set -euo pipefail
bun update
bun outdated || true
