#!/bin/bash
set -euo pipefail
./frontend/test.sh
./test-backend.sh
