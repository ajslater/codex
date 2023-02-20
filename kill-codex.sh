#!/bin/bash
# kill all codex processes
set -euo pipefail
pkill -9 -f 'codex/run.py'
