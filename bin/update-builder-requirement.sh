#!/bin/bash
# Update the builder-requirements.txt with installed versions.
set -euo pipefail
version=$(poetry --version)
version=${version#"Poetry (version "}
version=${version%?}
echo "poetry>=$version" > builder-requirements.txt
