#!/bin/bash
# Update python and npm dependencies
set -euo pipefail
poetry update
poetry show --outdated
npm update
bash -c "cd frontend && npm update"
npm outdated
bash -c "cd frontend && npm outdated"
