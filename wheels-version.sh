#!/bin/bash
set -euo pipefail
poetry export --without-hashes --extras wheel | md5sum | awk '{print $1}'
