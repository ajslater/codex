#!/bin/bash
# Update npm dependencies
set -euo pipefail
npm update
npm outdated
