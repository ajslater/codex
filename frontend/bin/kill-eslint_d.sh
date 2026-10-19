#!/usr/bin/env bash
# eslint_d can get into a bad state if git switches branches underneath it
set -euo pipefail
# The project's own eslint_d only: bunx would download one just to stop it.
# A daemon in a bad state may not stop cleanly; pkill gets it then.
if [[ -x node_modules/.bin/eslint_d ]]; then
  node_modules/.bin/eslint_d stop || true
fi
# Any daemon left, by the title eslint_d gives itself or by its script's path.
# A bare -f eslint_d would also match this script and make kill-eslint_d.
pkill -f '^eslint_d - |node_modules/eslint_d/' || true
rm -f .eslintcache
