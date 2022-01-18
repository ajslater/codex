#!/bin/bash
# Fix lints in js files
set -euo pipefail
EXT=.cjs,.js,.json,.md,.vue
bash -c "cd frontend && npx eslint --ext $EXT --fix '**'"
prettier --write .
