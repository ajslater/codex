#!/bin/bash
# Update the builder-requirements.txt with installed versions.
set -euo pipefail
pip3 freeze | grep poetry== | sed 's/==/>=/' >builder-requirements.txt
