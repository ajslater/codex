#!/bin/bash
# If the skip job flag is step. skip this step.
set -euo pipefail
if [ -f ./SKIP_STEPS ]; then
    circleci-agent step halt
fi
