#!/bin/bash
set -euo pipefail
EXT=.cjs,.js,.json,.md,.vue
bash -c "cd frontend && npx eslint --ext $EXT ."
prettier --check .
